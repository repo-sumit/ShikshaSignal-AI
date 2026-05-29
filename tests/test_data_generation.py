"""Tests for the synthetic data generator: counts, reproducibility, planted pathologies."""

from __future__ import annotations

import filecmp

from app.config import CSV_FILES, FOCUS_DISTRICT, SCALES
from generate_synthetic_data import generate


def test_expected_counts(tables):
    scale = SCALES["demo"]
    expected_schools = (
        (scale.blocks_focus + scale.blocks_comparison)
        * scale.clusters_per_block
        * scale.schools_per_cluster
    )
    assert tables.schools_dedup["school_id"].nunique() == expected_schools == 160
    assert tables.schools["district"].nunique() == 2
    assert len(tables.weeks) == scale.n_weeks == 8
    # Two districts present, focus district has the most blocks.
    assert FOCUS_DISTRICT in set(tables.schools["district"])


def test_reproducible_bytes(tmp_path):
    """Same seed => byte-identical CSVs (the core trust property)."""
    a, b = tmp_path / "a", tmp_path / "b"
    generate(seed=42, scale_name="demo", outdir=a)
    generate(seed=42, scale_name="demo", outdir=b)
    for fname in CSV_FILES.values():
        assert filecmp.cmp(a / fname, b / fname, shallow=False), f"{fname} differs across runs"


def test_planted_duplicate_school(tables):
    # Exactly one duplicate school_id row is planted for the data-quality layer.
    assert tables.schools["school_id"].duplicated().sum() == 1


def test_planted_invalid_completion(tables):
    tt = tables.teacher_training
    assert (tt["completion_percent"] > 100).sum() >= 1


def test_planted_future_dated_issue(tables):
    import pandas as pd

    from app.config import REFERENCE_DATE

    created = pd.to_datetime(tables.field_issues["created_at"], errors="coerce")
    assert (created > pd.Timestamp(REFERENCE_DATE)).sum() >= 1


def test_planted_orphan_ids(tables):
    valid = set(tables.schools_dedup["school_id"])
    orphan_diksha = ~tables.diksha_usage["school_id"].isin(valid)
    assert orphan_diksha.sum() >= 1


def test_missing_latest_week_present(tables):
    # Some schools deliberately lack a row for the latest week.
    latest = tables.latest_week
    reporting = set(tables.diksha_usage.loc[tables.diksha_usage["week"] == latest, "school_id"])
    valid = set(tables.schools_dedup["school_id"])
    assert len(valid - reporting) >= 1
