"""Tests for the YAML config layer added in Milestone 7."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import RISK_WEIGHTS as BUILTIN_WEIGHTS
from app.services.config_loader import (
    ConfigError,
    RISK_WEIGHTS_PATH,
    KPI_TARGETS_PATH,
    KpiTargetsConfig,
    RiskConfig,
    load_kpi_targets,
    load_risk_config,
)


# ---------------------------------------------------------------------------
# Risk weights
# ---------------------------------------------------------------------------


def test_default_risk_weights_yaml_loads():
    cfg = load_risk_config()
    assert isinstance(cfg, RiskConfig)
    # The default YAML must use the same keys as the in-code RISK_WEIGHTS dict.
    assert set(cfg.weights.keys()) == set(BUILTIN_WEIGHTS.keys())


def test_default_risk_weights_sum_to_one():
    cfg = load_risk_config()
    total = sum(cfg.weights.values())
    assert abs(total - 1.0) < 1e-6, f"weights summed to {total}, not 1.0"


def test_default_risk_weights_match_builtin_constants():
    """Drift between YAML and in-code defaults would be silent and dangerous."""
    cfg = load_risk_config()
    for key, builtin in BUILTIN_WEIGHTS.items():
        assert cfg.weights[key] == pytest.approx(builtin), (
            f"weight {key!r} drifted: YAML={cfg.weights[key]} vs RISK_WEIGHTS={builtin}"
        )


def test_default_risk_config_source_is_yaml():
    cfg = load_risk_config()
    assert cfg.source_kind == "yaml"
    assert cfg.source_path == str(RISK_WEIGHTS_PATH)


def test_risk_config_falls_back_to_builtin_when_yaml_missing(tmp_path):
    missing = tmp_path / "absent.yaml"
    cfg = load_risk_config(missing)
    assert cfg.source_kind == "builtin"
    assert cfg.weights == BUILTIN_WEIGHTS


# ---- invalid YAML paths ---------------------------------------------------


def _write_yaml(tmp: Path, body: str) -> Path:
    p = tmp / "risk_weights.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_risk_config_rejects_weights_not_summing_to_one(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
version: "1.0"
weights:
  learning_outcome: 0.5
  digital_usage: 0.5
  teacher_training: 0.5
  infrastructure: 0.0
  field_issues: 0.0
  data_availability: 0.0
  data_quality: 0.0
""",
    )
    with pytest.raises(ConfigError, match="sum to 1.0"):
        load_risk_config(path)


def test_risk_config_rejects_missing_component(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
version: "1.0"
weights:
  learning_outcome: 1.0
""",
    )
    with pytest.raises(ConfigError, match="missing components"):
        load_risk_config(path)


def test_risk_config_rejects_unknown_component(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
version: "1.0"
weights:
  learning_outcome: 0.25
  digital_usage: 0.20
  teacher_training: 0.15
  infrastructure: 0.15
  field_issues: 0.10
  data_availability: 0.10
  data_quality: 0.05
  vibes: 0.00
""",
    )
    with pytest.raises(ConfigError, match="unknown components"):
        load_risk_config(path)


def test_risk_config_rejects_negative_weight(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
version: "1.0"
weights:
  learning_outcome: -0.1
  digital_usage: 0.30
  teacher_training: 0.15
  infrastructure: 0.15
  field_issues: 0.10
  data_availability: 0.10
  data_quality: 0.05
""",
    )
    # The negative one is detected before the sum check.
    with pytest.raises(ConfigError, match=r"outside \[0, 1\]"):
        load_risk_config(path)


def test_risk_config_rejects_non_numeric_weight(tmp_path):
    path = _write_yaml(
        tmp_path,
        """
version: "1.0"
weights:
  learning_outcome: "high"
  digital_usage: 0.20
  teacher_training: 0.15
  infrastructure: 0.15
  field_issues: 0.10
  data_availability: 0.10
  data_quality: 0.05
""",
    )
    with pytest.raises(ConfigError, match="not numeric"):
        load_risk_config(path)


def test_risk_config_accepts_field_issue_singular_alias(tmp_path):
    """`field_issue` (singular, in-code) and `field_issues` (plural, in YAML) are aliased."""
    path = _write_yaml(
        tmp_path,
        """
version: "1.0"
weights:
  learning_outcome: 0.25
  digital_usage: 0.20
  teacher_training: 0.15
  infrastructure: 0.15
  field_issue: 0.10
  data_availability: 0.10
  data_quality: 0.05
""",
    )
    cfg = load_risk_config(path)
    assert "field_issue" in cfg.weights
    assert cfg.weights["field_issue"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# KPI targets
# ---------------------------------------------------------------------------


def test_kpi_targets_yaml_loads():
    cfg = load_kpi_targets()
    assert isinstance(cfg, KpiTargetsConfig)
    assert cfg.targets, "kpi targets should not be empty"
    assert cfg.source_kind in {"yaml", "legacy"}


def test_kpi_targets_has_required_keys():
    cfg = load_kpi_targets()
    # The exact set of KPIs the review compiler expects.
    expected = {
        "diksha_sessions_per_school_weekly",
        "teacher_training_completion_pct",
        "fln_proficiency_pct",
        "fln_gain_points",
        "open_critical_issues",
        "usage_coverage_pct",
    }
    assert expected.issubset(set(cfg.targets.keys()))


def test_kpi_targets_every_row_has_required_fields():
    cfg = load_kpi_targets()
    for kpi, row in cfg.targets.items():
        for k in ("label", "target", "direction", "source"):
            assert k in row, f"KPI {kpi!r} missing field {k!r}"


def test_kpi_targets_prefers_config_dir_over_legacy():
    """When both files exist, config/kpi_targets.yaml should win."""
    cfg = load_kpi_targets()
    if cfg.source_kind == "yaml":
        assert cfg.source_path.endswith("kpi_targets.yaml")


def test_kpi_targets_empty_when_no_files(tmp_path):
    """load_kpi_targets accepts an explicit override; a non-existent path yields empty."""
    cfg = load_kpi_targets(tmp_path / "no.yaml")
    assert cfg.targets == {}
    assert cfg.source_kind == "empty"


# ---------------------------------------------------------------------------
# Audit log records the active risk config
# ---------------------------------------------------------------------------


def test_audit_log_records_risk_config_path_and_source(tmp_path, gen_dir):
    """End-to-end: a review run captures which YAML produced the weights."""
    from app.review import run_review

    arts = run_review(
        district="District Alpha", period="2026-05",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    import json

    audit = json.loads(arts.audit_log_json.read_text(encoding="utf-8"))
    assert "risk_config_path" in audit
    assert "risk_config_source" in audit
    assert audit["risk_config_source"] in {"yaml", "builtin"}
    if audit["risk_config_source"] == "yaml":
        assert audit["risk_config_path"].endswith("risk_weights.yaml")
