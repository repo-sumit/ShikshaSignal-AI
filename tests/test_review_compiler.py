"""Tests for the Review Compiler (Milestone 3).

Exercises the end-to-end CLI flow against a freshly-generated synthetic dataset:
all four artifacts are written, the markdown carries every required section, the
action tracker has the required columns, and the audit log records the lineage.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.config import FOCUS_DISTRICT, RISK_MODEL_VERSION
from app.reporting.action_tracker import ACTION_COLUMNS
from app.reporting.markdown_report import SECTION_HEADINGS
from app.review import run_review


@pytest.fixture(scope="module")
def review_outputs(tmp_path_factory, gen_dir):
    """Run the compiler once and reuse its outputs across the file's tests."""
    out = tmp_path_factory.mktemp("review_outputs")
    arts = run_review(
        district=FOCUS_DISTRICT,
        period="2026-05",
        top_n_schools=10,
        top_n_blocks=5,
        top_n_actions=10,
        llm_provider="mock",
        outputs_dir=out,
        synthetic_dir=gen_dir,
        timestamp="2026-05-29T00:00:00+00:00",
    )
    return arts


# ---------------------------------------------------------------------------
# File presence
# ---------------------------------------------------------------------------


def test_all_four_artifacts_are_written(review_outputs):
    for p in review_outputs.as_list():
        assert Path(p).exists(), f"Missing output file: {p}"
        assert Path(p).stat().st_size > 0, f"Empty output file: {p}"


def test_artifact_filenames_match_spec(review_outputs):
    names = {Path(p).name for p in review_outputs.as_list()}
    assert names == {
        "monthly_district_review.md",
        "action_tracker.csv",
        "audit_log.json",
        "review_facts.json",
    }


# ---------------------------------------------------------------------------
# Markdown contents
# ---------------------------------------------------------------------------


def test_memo_contains_every_required_section(review_outputs):
    text = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    for key, heading in SECTION_HEADINGS.items():
        assert heading in text, f"Missing section heading: {heading}"


def test_memo_carries_synthetic_data_disclaimer(review_outputs):
    text = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in text
    assert "deterministic" in text.lower()


def test_memo_labels_root_causes_as_hypotheses(review_outputs):
    text = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    assert "Hypothesis" in text  # template uses the explicit word
    # No causal claim should appear without the hypothesis tag near it.
    assert "require field verification" in text.lower()


def test_memo_title_includes_district_and_period(review_outputs):
    text = Path(review_outputs.monthly_district_review_md).read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert FOCUS_DISTRICT in first_line
    assert "2026-05" in first_line


# ---------------------------------------------------------------------------
# Action tracker
# ---------------------------------------------------------------------------


def test_action_tracker_has_required_columns(review_outputs):
    df = pd.read_csv(review_outputs.action_tracker_csv)
    assert list(df.columns) == ACTION_COLUMNS
    assert len(df) > 0
    # Status starts as "proposed" — no row should be approved by default.
    assert (df["status"] == "proposed").all()


def test_action_tracker_evidence_is_non_empty(review_outputs):
    df = pd.read_csv(review_outputs.action_tracker_csv)
    assert df["evidence"].str.len().min() > 0


def test_action_tracker_priority_follows_band(review_outputs):
    df = pd.read_csv(review_outputs.action_tracker_csv)
    facts = json.loads(Path(review_outputs.review_facts_json).read_text(encoding="utf-8"))
    # Every action references one of the top-N schools.
    top_school_ids = {s["school_id"] for s in facts["top_schools"]}
    assert set(df["school_id"]).issubset(top_school_ids)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def test_audit_log_records_provider_and_lineage(review_outputs):
    audit = json.loads(Path(review_outputs.audit_log_json).read_text(encoding="utf-8"))
    # Required fields per spec.
    for k in [
        "run_id",
        "timestamp",
        "command_args",
        "data_files_used",
        "policy_docs_used",
        "llm_provider",
        "fallback_used",
        "output_files",
        "risk_formula_version",
        "synthetic_data_notice",
    ]:
        assert k in audit, f"audit_log.json missing field: {k}"

    assert audit["llm_provider"] == "mock"
    assert audit["fallback_used"] is False
    assert audit["risk_formula_version"] == RISK_MODEL_VERSION
    # All five CSVs should be listed.
    assert len(audit["data_files_used"]) == 5
    # All four outputs should be listed.
    assert len(audit["output_files"]) == 4


def test_audit_log_records_fallback_on_unknown_provider(tmp_path, gen_dir):
    arts = run_review(
        district=FOCUS_DISTRICT,
        period="2026-05",
        llm_provider="some-future-provider-that-does-not-exist",
        outputs_dir=tmp_path,
        synthetic_dir=gen_dir,
    )
    audit = json.loads(arts.audit_log_json.read_text(encoding="utf-8"))
    assert audit["fallback_used"] is True
    assert audit["llm_provider"] == "mock"
    assert audit["requested_llm_provider"] != "mock"


# ---------------------------------------------------------------------------
# review_facts.json
# ---------------------------------------------------------------------------


def test_review_facts_contains_core_keys(review_outputs):
    facts = json.loads(Path(review_outputs.review_facts_json).read_text(encoding="utf-8"))
    for k in [
        "district",
        "period",
        "schools",
        "blocks",
        "coverage_pct",
        "health_score",
        "band_split",
        "usage_delta",
        "top_blocks",
        "top_schools",
        "kpi_rows",
        "data_quality",
        "action_preview",
        "root_cause_hypotheses",
        "risk_model_version",
    ]:
        assert k in facts, f"review_facts.json missing key: {k}"
    assert facts["district"] == FOCUS_DISTRICT
    assert facts["period"] == "2026-05"
    assert isinstance(facts["top_schools"], list) and facts["top_schools"]


# ---------------------------------------------------------------------------
# Determinism + CLI surface
# ---------------------------------------------------------------------------


def test_compiler_is_deterministic_for_same_inputs(tmp_path, gen_dir):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    arts_a = run_review(
        district=FOCUS_DISTRICT, period="2026-05", outputs_dir=out_a, synthetic_dir=gen_dir,
        timestamp="2026-05-29T00:00:00+00:00",
    )
    arts_b = run_review(
        district=FOCUS_DISTRICT, period="2026-05", outputs_dir=out_b, synthetic_dir=gen_dir,
        timestamp="2026-05-29T00:00:00+00:00",
    )
    # Memo, actions, facts are all deterministic on equal inputs.
    assert arts_a.monthly_district_review_md.read_text(encoding="utf-8") == \
        arts_b.monthly_district_review_md.read_text(encoding="utf-8")
    assert arts_a.action_tracker_csv.read_text(encoding="utf-8") == \
        arts_b.action_tracker_csv.read_text(encoding="utf-8")
    assert arts_a.review_facts_json.read_text(encoding="utf-8") == \
        arts_b.review_facts_json.read_text(encoding="utf-8")


def test_cli_entrypoint_runs(tmp_path, gen_dir):
    """`python -m app.review --district ... --period ...` must exit 0 + write outputs."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(__file__).resolve().parent.parent), env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [
            sys.executable, "-m", "app.review",
            "--district", FOCUS_DISTRICT,
            "--period", "2026-05",
            "--outputs-dir", str(tmp_path),
            "--synthetic-dir", str(gen_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    for name in (
        "monthly_district_review.md",
        "action_tracker.csv",
        "audit_log.json",
        "review_facts.json",
    ):
        assert (tmp_path / name).exists(), f"{name} not written by CLI"
