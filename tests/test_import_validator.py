"""Tests for the import validator (``python -m app.tools.import_validator``)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.tools.import_validator import (
    VERDICT_NOT_READY,
    VERDICT_READY,
    VERDICT_READY_WITH_WARNINGS,
    ValidationReport,
    main as validator_main,
    validate,
    write_report,
)


# ---------------------------------------------------------------------------
# Synthetic dataset — the validator should catch the *planted* pathologies
# ---------------------------------------------------------------------------


def test_validate_on_synthetic_data_returns_report(gen_dir):
    report = validate(gen_dir)
    assert isinstance(report, ValidationReport)
    assert {r.file for r in report.files} == {
        "schools", "diksha_usage", "assessments", "teacher_training", "field_issues",
    }
    assert report.summary["files_present"] == 5
    assert report.summary["files_missing"] == 0


def test_validator_catches_planted_pathologies(gen_dir):
    """The generator plants ~5-8% deliberately broken rows; the validator must see them."""
    report = validate(gen_dir)

    # Map (file -> set of error codes) for assertion clarity.
    errors_by_file: dict[str, set[str]] = {}
    for r in report.files:
        for f in r.findings:
            if f.severity == "error":
                errors_by_file.setdefault(r.file, set()).add(f.code)

    # The duplicate school_id is planted in schools.csv.
    assert "duplicate_primary_key" in errors_by_file.get("schools", set())
    # The invalid completion_percent (>100) is planted in teacher_training.csv.
    assert "value_above_max" in errors_by_file.get("teacher_training", set())
    # Future-dated issues are planted in field_issues.csv (REFERENCE_DATE check).
    assert "future_dated_value" in errors_by_file.get("field_issues", set())
    # Orphan school_ids are planted in at least one fact table.
    assert any(
        "unmatched_foreign_key" in errors_by_file.get(f, set())
        for f in ("diksha_usage", "assessments", "teacher_training", "field_issues")
    )


def test_synthetic_dataset_verdict_is_not_ready(gen_dir):
    """Synthetic data has DELIBERATE errors, so honest reporting = Not ready."""
    report = validate(gen_dir)
    assert report.verdict == VERDICT_NOT_READY


# ---------------------------------------------------------------------------
# Clean dataset — should produce the Ready verdict
# ---------------------------------------------------------------------------


def _write_clean_dataset(target: Path) -> None:
    """Minimal but schema-compliant CSV set so the validator returns Ready."""
    target.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {
            "school_id": "S1", "school_name": "GPS A", "state": "X", "district": "D",
            "block": "B1", "cluster": "C1", "school_type": "primary",
            "lowest_grade": 1, "highest_grade": 5,
            "enrollment": 100, "teachers_count": 5,
            "internet_available": True, "device_available": True,
            "infrastructure_score": 75.0,
        }
    ]).to_csv(target / "schools.csv", index=False)

    pd.DataFrame([
        {"school_id": "S1", "week": "2026-W18", "qr_scans": 1, "sessions": 10,
         "learning_minutes": 30, "active_teachers": 2, "active_students_proxy": 30}
    ]).to_csv(target / "diksha_usage.csv", index=False)

    pd.DataFrame([
        {"school_id": "S1", "grade": 3, "subject": "Literacy",
         "assessment_round": "endline",
         "baseline_score": 40.0, "current_score": 55.0,
         "district_average": 50.0, "proficiency_band": "meets"}
    ]).to_csv(target / "assessments.csv", index=False)

    pd.DataFrame([
        {"teacher_id": "T1", "school_id": "S1", "course_name": "NIPUN",
         "status": "completed", "completion_percent": 100.0,
         "assessment_score": 80.0, "last_activity_date": "2026-05-01"}
    ]).to_csv(target / "teacher_training.csv", index=False)

    pd.DataFrame([
        {"issue_id": "I1", "school_id": "S1", "issue_type": "infra", "severity": "low",
         "status": "resolved", "reported_by": "BRC", "description": "ok",
         "created_at": "2026-03-15", "resolved_at": "2026-03-20"}
    ]).to_csv(target / "field_issues.csv", index=False)


def test_clean_dataset_verdict_is_ready(tmp_path):
    src = tmp_path / "clean"
    _write_clean_dataset(src)
    report = validate(src)
    # Filter to errors only — we expect zero.
    errors = [f for r in report.files for f in r.findings if f.severity == "error"]
    assert errors == []
    assert report.verdict in {VERDICT_READY, VERDICT_READY_WITH_WARNINGS}


# ---------------------------------------------------------------------------
# Missing-file handling
# ---------------------------------------------------------------------------


def test_validator_does_not_crash_on_missing_files(tmp_path):
    """Run against an empty source dir — every file should be reported missing."""
    empty = tmp_path / "no_data"
    empty.mkdir()
    report = validate(empty)
    assert report.summary["files_missing"] == 5
    assert report.summary["files_present"] == 0
    assert report.verdict == VERDICT_NOT_READY
    # Every per-file report shows the `missing_file` error.
    assert all(
        any(f.code == "missing_file" for f in r.findings)
        for r in report.files
    )


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def test_write_report_creates_markdown_and_json(tmp_path, gen_dir):
    report = validate(gen_dir)
    paths = write_report(report, tmp_path)
    assert paths["markdown"].exists() and paths["markdown"].stat().st_size > 0
    assert paths["json"].exists() and paths["json"].stat().st_size > 0


def test_markdown_report_contains_required_sections(tmp_path, gen_dir):
    report = validate(gen_dir)
    paths = write_report(report, tmp_path)
    md = paths["markdown"].read_text(encoding="utf-8")
    for section in (
        "# Import Validation Report",
        "**Verdict:**",
        "## Summary",
        "## Per-file results",
        "## Findings",
        "## Recommended fixes",
        "SYNTHETIC DATA",
    ):
        assert section in md, f"markdown report missing section: {section}"


def test_json_report_has_expected_keys(tmp_path, gen_dir):
    report = validate(gen_dir)
    paths = write_report(report, tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    for k in ("verdict", "summary", "schema_source", "source_dir", "reference_date", "files"):
        assert k in payload
    assert payload["files"], "files list should not be empty"
    # First file row carries its own contract.
    f0 = payload["files"][0]
    for k in (
        "file", "path", "present", "rows",
        "required_columns_present", "required_columns_missing",
        "unexpected_columns", "primary_key_unique", "foreign_key_match_rate",
        "findings",
    ):
        assert k in f0, f"per-file payload missing key: {k}"


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_returns_nonzero_for_not_ready(tmp_path, gen_dir):
    """The validator returns exit code 1 only when verdict == Not ready."""
    out_dir = tmp_path / "outs"
    rc = validator_main([
        "--source-dir", str(gen_dir),
        "--outputs-dir", str(out_dir),
    ])
    assert rc == 1   # planted pathologies -> Not ready
    assert (out_dir / "import_validation_report.md").exists()
    assert (out_dir / "import_validation_report.json").exists()


def test_cli_returns_zero_for_clean_dataset(tmp_path):
    src = tmp_path / "clean"
    _write_clean_dataset(src)
    rc = validator_main([
        "--source-dir", str(src),
        "--outputs-dir", str(tmp_path / "out"),
    ])
    assert rc == 0
