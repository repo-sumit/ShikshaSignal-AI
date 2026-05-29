"""Tests for the data-quality tool: coverage, reconciliation, and that planted issues are caught."""

from __future__ import annotations

from app.tools.data_quality import assess_quality


def _finding(rep, check):
    return next((f for f in rep.findings if f["check"] == check), None)


def test_coverage_reported(tables):
    rep = assess_quality(tables)
    cov = rep.coverage
    assert cov["schools_total"] == 160
    assert 0 < cov["coverage_pct"] <= 100
    assert cov["schools_reporting"] <= cov["schools_total"]


def test_catches_duplicate_school(tables):
    rep = assess_quality(tables)
    f = _finding(rep, "duplicate_school_id")
    assert f is not None and f["count"] == 1


def test_catches_invalid_completion(tables):
    rep = assess_quality(tables)
    f = _finding(rep, "invalid_completion_percent")
    assert f is not None and f["count"] >= 1


def test_catches_future_dated_issue(tables):
    rep = assess_quality(tables)
    f = _finding(rep, "future_dated_issue")
    assert f is not None and f["count"] >= 1


def test_reconciliation_finds_orphans(tables):
    rep = assess_quality(tables)
    total_unmatched = sum(r["unmatched_rows"] for r in rep.reconciliation.values())
    assert total_unmatched >= 1


def test_per_school_signals_cover_all_schools(tables):
    rep = assess_quality(tables)
    assert len(rep.per_school) == tables.schools_dedup["school_id"].nunique()
    for col in ["missing_latest_week", "missing_usage_entirely",
                "missing_assessment", "dq_invalid_count"]:
        assert col in rep.per_school.columns


def test_score_between_0_and_100(tables):
    rep = assess_quality(tables)
    assert 0 <= rep.data_quality_score <= 100
