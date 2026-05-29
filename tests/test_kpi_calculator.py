"""Tests for the KPI calculator: shape, honest missing-data handling, target-vs-actual."""

from __future__ import annotations

import pandas as pd

from app.config import FOCUS_DISTRICT
from app.tools.kpi_calculator import compute_school_kpis, district_summary, load_policy_targets


def test_school_kpis_shape(tables):
    kpis = compute_school_kpis(tables)
    assert len(kpis) == tables.schools_dedup["school_id"].nunique()
    for col in ["sessions_latest", "reported_latest", "fln_gain",
                "training_completion_pct", "open_critical"]:
        assert col in kpis.columns


def test_missing_latest_is_nan_not_zero(tables):
    """A school missing its latest-week row must have NaN sessions_latest, not 0."""
    kpis = compute_school_kpis(tables)
    missing = kpis[~kpis["reported_latest"]]
    assert len(missing) >= 1
    assert missing["sessions_latest"].isna().all()


def test_policy_targets_loaded():
    targets = load_policy_targets()
    assert "fln_proficiency_pct" in targets
    assert targets["teacher_training_completion_pct"]["target"] == 80


def test_district_summary_struggling(tables):
    s = district_summary(tables, FOCUS_DISTRICT)
    assert s["schools"] == 120
    assert 80 <= s["coverage_pct"] <= 100
    by_key = {k["kpi"]: k for k in s["kpis"]}
    # The focus district is engineered to be below FLN and training targets.
    assert by_key["fln_proficiency_pct"]["status"] == "below target"
    assert by_key["teacher_training_completion_pct"]["status"] == "below target"


def test_usage_delta_present(tables):
    s = district_summary(tables, FOCUS_DISTRICT)
    ud = s["usage_delta"]
    assert ud["latest_week"] == tables.latest_week
    assert not pd.isna(ud["sessions_latest_mean"])
