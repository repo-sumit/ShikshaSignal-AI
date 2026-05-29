"""Tests for `scripts/run_local_demo.py` and `scripts/ingest_policy_docs.py`.

We exercise the cheap, dependency-light bits (CLI parsing, helper functions,
policy-YAML validation) and one end-to-end happy-path with `--skip-data` so
the existing seeded synthetic dataset is reused — keeping the suite fast.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# File presence + import safety
# ---------------------------------------------------------------------------


def test_local_demo_script_exists():
    assert (_REPO_ROOT / "scripts" / "run_local_demo.py").exists()


def test_policy_ingest_script_exists():
    assert (_REPO_ROOT / "scripts" / "ingest_policy_docs.py").exists()


def test_local_demo_script_imports_cleanly():
    import importlib

    mod = importlib.import_module("run_local_demo")
    for fn_name in (
        "main",
        "step_generate_synthetic_data",
        "step_ingest_policy_docs",
        "step_run_review",
        "print_next_steps",
    ):
        assert hasattr(mod, fn_name), f"missing function: {fn_name}"


def test_ingest_policy_docs_imports_cleanly():
    import importlib

    mod = importlib.import_module("ingest_policy_docs")
    for fn_name in ("main", "load_policy_map", "validate"):
        assert hasattr(mod, fn_name), f"missing function: {fn_name}"


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_local_demo_cli_defaults():
    import run_local_demo as demo

    args = demo._parse_args([])
    assert args.district == "District Alpha"
    assert args.period == "2026-05"
    assert args.seed == 42
    assert args.llm_provider == "mock"
    assert args.skip_data is False
    assert args.skip_policy is False


def test_local_demo_cli_overrides():
    import run_local_demo as demo

    args = demo._parse_args(
        ["--district", "District Beta", "--period", "2026-04",
         "--seed", "7", "--llm-provider", "groq", "--skip-data", "--skip-policy"]
    )
    assert args.district == "District Beta"
    assert args.period == "2026-04"
    assert args.seed == 7
    assert args.llm_provider == "groq"
    assert args.skip_data is True
    assert args.skip_policy is True


def test_local_demo_rejects_unknown_provider():
    import run_local_demo as demo

    with pytest.raises(SystemExit):
        demo._parse_args(["--llm-provider", "claude"])


# ---------------------------------------------------------------------------
# policy_map.yaml validator
# ---------------------------------------------------------------------------


def test_validate_accepts_well_formed_map():
    from ingest_policy_docs import validate

    payload = {
        "targets": {
            "diksha_sessions_per_school_weekly": {
                "label": "weekly sessions",
                "target": 50,
                "direction": "higher_is_better",
                "source": "Digital Learning Adoption Guideline",
            }
        }
    }
    assert validate(payload) == []


def test_validate_flags_missing_keys():
    from ingest_policy_docs import validate

    payload = {"targets": {"x": {"label": "x"}}}
    errors = validate(payload)
    assert any("target" in e for e in errors)
    assert any("direction" in e for e in errors)
    assert any("source" in e for e in errors)


def test_validate_flags_bad_direction():
    from ingest_policy_docs import validate

    payload = {
        "targets": {
            "x": {
                "label": "x",
                "target": 1,
                "direction": "sideways",
                "source": "made up",
            }
        }
    }
    errors = validate(payload)
    assert any("direction" in e for e in errors)


def test_validate_flags_empty_targets():
    from ingest_policy_docs import validate

    assert validate({}) and "targets" in validate({})[0]
    assert validate({"targets": {}})


def test_ingest_main_returns_zero_for_real_yaml(capsys):
    from ingest_policy_docs import main as ingest_main

    rc = ingest_main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "policy target(s) validated" in out


def test_ingest_main_returns_nonzero_for_missing_path(capsys, tmp_path):
    from ingest_policy_docs import main as ingest_main

    missing = tmp_path / "absent.yaml"
    rc = ingest_main(["--path", str(missing)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "ERROR" in err


# ---------------------------------------------------------------------------
# End-to-end happy path (re-uses the seeded fixture data, skips regeneration)
# ---------------------------------------------------------------------------


def test_local_demo_end_to_end_with_skipped_data(tmp_path, gen_dir, monkeypatch, capsys):
    """Run the full demo against the conftest's seeded data, no paid API."""
    import run_local_demo as demo

    # Point the demo at the conftest fixture's data + a tmp outputs dir.
    monkeypatch.setattr("run_local_demo._REPO_ROOT", _REPO_ROOT)

    # The orchestrator reads SYNTHETIC_DIR/OUTPUTS_DIR from app.config; redirect
    # outputs to a tmp dir so the test never writes into outputs/.
    monkeypatch.setattr("app.config.OUTPUTS_DIR", tmp_path)

    # Run with --skip-data and --skip-policy so we only exercise the review step.
    rc = demo.main(
        [
            "--skip-data",
            "--skip-policy",
            "--district", "District Alpha",
            "--period", "2026-05",
            "--llm-provider", "mock",
        ]
    )
    assert rc == 0

    out = capsys.readouterr().out
    # Demo prints reach each of the four expected artifacts by label.
    for label in ("Monthly review memo", "Action tracker", "Audit log", "Review facts"):
        assert label in out, f"expected '{label}' in demo output"
    # Demo prints the Streamlit launch hint.
    assert "streamlit run frontend/streamlit_app.py" in out
    # Demo reaffirms the synthetic-data disclaimer.
    assert "SYNTHETIC" in out


def test_local_demo_does_not_require_paid_api_keys(monkeypatch, tmp_path, capsys):
    """Sanity: no real API key in env, mock provider, demo must still finish OK."""
    for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    import run_local_demo as demo

    monkeypatch.setattr("app.config.OUTPUTS_DIR", tmp_path)

    rc = demo.main(["--skip-data", "--skip-policy", "--llm-provider", "mock"])
    assert rc == 0
