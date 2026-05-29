"""Tests for the risk engine: reproducibility, ranges, weights, band logic, problem block."""

from __future__ import annotations

import pytest

from app.config import FOCUS_DISTRICT, RISK_WEIGHTS, TARGET_BAND_SPLIT, band_for_score
from app.tools.risk_score import COMPONENTS, band_split, compute_block_risk, compute_school_risk


def test_weights_sum_to_one():
    assert abs(sum(RISK_WEIGHTS.values()) - 1.0) < 1e-9


def test_scores_reproducible(tables):
    a = compute_school_risk(tables)
    b = compute_school_risk(tables)
    assert a.equals(b)


def test_components_and_score_in_range(tables):
    risk = compute_school_risk(tables)
    for col in COMPONENTS + ["risk_score"]:
        assert risk[col].between(0, 100).all(), f"{col} out of 0-100"


def test_band_matches_score(tables):
    """Regression: continuous bands, no gaps (a 69.x score must not fall back to 'Low')."""
    risk = compute_school_risk(tables)
    for _, r in risk.iterrows():
        assert r["risk_band"] == band_for_score(r["risk_score"])


def test_band_boundaries():
    assert band_for_score(39.9) == "Low"
    assert band_for_score(40.0) == "Medium"
    assert band_for_score(69.9) == "Medium"   # the value that exposed the original bug
    assert band_for_score(70.0) == "High"
    assert band_for_score(100.0) == "High"


def test_band_split_in_tolerance(tables):
    split = band_split(compute_school_risk(tables))
    for band, (lo, hi) in TARGET_BAND_SPLIT.items():
        assert lo <= split[band] <= hi, f"{band}={split[band]:.1%} outside {lo:.0%}-{hi:.0%}"


def test_problem_block_is_worst(tables):
    blocks = compute_block_risk(compute_school_risk(tables))
    top = blocks.iloc[0]
    assert top["district"] == FOCUS_DISTRICT
    assert top["high_risk_schools"] >= 5
    # Clear separation from the next-worst block.
    assert top["mean_risk"] - blocks.iloc[1]["mean_risk"] > 10


def test_explanation_present(tables):
    risk = compute_school_risk(tables)
    assert risk["explanation"].str.len().gt(0).all()
    assert risk["top_drivers"].str.contains(",").all()
