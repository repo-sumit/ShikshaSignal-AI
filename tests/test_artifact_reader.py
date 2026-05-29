"""Tests for app.services.artifact_reader (Milestone 5).

The reader is the only seam between the Streamlit viewer and the file system, so it
must be **defensive**: missing files / unparseable JSON / empty CSVs all return safe
defaults (empty string, empty DataFrame, empty dict) rather than raising.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.services.artifact_reader import (
    all_outputs_present,
    list_available_districts,
    list_available_periods,
    output_paths,
    read_csv,
    read_json,
    read_markdown,
    synthetic_data_present,
)


# ---------------------------------------------------------------------------
# Per-file readers — happy paths
# ---------------------------------------------------------------------------


def test_read_markdown_happy_path(tmp_path: Path):
    p = tmp_path / "memo.md"
    p.write_text("# hello\n\nsome prose", encoding="utf-8")
    assert read_markdown(p).startswith("# hello")


def test_read_csv_happy_path(tmp_path: Path):
    p = tmp_path / "rows.csv"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(p, index=False)
    df = read_csv(p)
    assert not df.empty
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_read_json_happy_path(tmp_path: Path):
    p = tmp_path / "facts.json"
    p.write_text(json.dumps({"district": "Alpha", "schools": 120}), encoding="utf-8")
    out = read_json(p)
    assert out == {"district": "Alpha", "schools": 120}


# ---------------------------------------------------------------------------
# Per-file readers — defensive paths
# ---------------------------------------------------------------------------


def test_read_markdown_missing_returns_empty(tmp_path: Path):
    assert read_markdown(tmp_path / "absent.md") == ""


def test_read_csv_missing_returns_empty_dataframe(tmp_path: Path):
    df = read_csv(tmp_path / "absent.csv")
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_read_csv_empty_file_does_not_raise(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    assert read_csv(p).empty


def test_read_json_missing_returns_empty_dict(tmp_path: Path):
    assert read_json(tmp_path / "absent.json") == {}


def test_read_json_invalid_returns_empty_dict(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert read_json(p) == {}


def test_read_json_non_object_returns_empty_dict(tmp_path: Path):
    """Lists at the root would break callers that expect dict semantics."""
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert read_json(p) == {}


def test_read_helpers_handle_directories_gracefully(tmp_path: Path):
    """Passing a directory path must not crash; returns empty defaults."""
    d = tmp_path / "subdir"
    d.mkdir()
    assert read_markdown(d) == ""
    assert read_csv(d).empty
    assert read_json(d) == {}


# ---------------------------------------------------------------------------
# Output paths + presence check
# ---------------------------------------------------------------------------


def test_output_paths_includes_all_artifacts(tmp_path: Path):
    paths = output_paths(tmp_path)
    assert "review_md" in paths
    assert "action_tracker_csv" in paths
    assert "audit_log_json" in paths
    assert "review_facts_json" in paths
    assert paths["review_md"].name == "monthly_district_review.md"
    assert paths["action_tracker_csv"].name == "action_tracker.csv"
    assert paths["audit_log_json"].name == "audit_log.json"
    assert paths["review_facts_json"].name == "review_facts.json"


def test_all_outputs_present_false_when_dir_empty(tmp_path: Path):
    assert all_outputs_present(tmp_path) is False


def test_all_outputs_present_true_when_all_files_exist(tmp_path: Path):
    for name in (
        "monthly_district_review.md",
        "action_tracker.csv",
        "audit_log.json",
        "review_facts.json",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert all_outputs_present(tmp_path) is True


def test_all_outputs_present_false_when_one_file_empty(tmp_path: Path):
    for name in (
        "monthly_district_review.md",
        "action_tracker.csv",
        "audit_log.json",
        "review_facts.json",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "audit_log.json").write_text("", encoding="utf-8")
    assert all_outputs_present(tmp_path) is False


# ---------------------------------------------------------------------------
# Synthetic-data introspection
# ---------------------------------------------------------------------------


def test_synthetic_data_present_false_when_absent(tmp_path: Path):
    assert synthetic_data_present(tmp_path) is False


def test_list_available_districts_empty_when_no_data(tmp_path: Path):
    assert list_available_districts(tmp_path) == []


def test_list_available_periods_falls_back_when_no_data(tmp_path: Path):
    """Spec: never leave the Streamlit period selector empty."""
    out = list_available_periods(tmp_path)
    assert out == ["2026-05"]


# ---- against the real, seeded synthetic dataset (uses the conftest fixture) ----


def test_list_available_districts_against_real_data(gen_dir):
    districts = list_available_districts(gen_dir)
    assert "District Alpha" in districts
    assert len(districts) >= 1
    # Sorted output for stable UI ordering.
    assert districts == sorted(districts)


def test_list_available_periods_against_real_data(gen_dir):
    periods = list_available_periods(gen_dir)
    assert all(len(p) == 7 and p[4] == "-" for p in periods), f"unexpected period shape: {periods}"
    assert len(periods) >= 1


def test_synthetic_data_present_true_against_real_data(gen_dir):
    assert synthetic_data_present(gen_dir) is True
