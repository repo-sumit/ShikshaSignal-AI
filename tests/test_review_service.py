"""Tests for the `run_review` callable as a *service* (the seam between the CLI and the
Streamlit viewer). They overlap with `test_review_compiler.py` deliberately — this file
locks down the **public contract** the Streamlit viewer relies on, separately from the
compiler's internal behaviour."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import FOCUS_DISTRICT
from app.review import ReviewArtifacts, run_review


# ---------------------------------------------------------------------------
# Public contract: signature + return type
# ---------------------------------------------------------------------------


def test_run_review_returns_review_artifacts(tmp_path, gen_dir):
    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    assert isinstance(arts, ReviewArtifacts)
    # Every documented attribute is a Path that actually exists.
    for attr in (
        "monthly_district_review_md",
        "action_tracker_csv",
        "audit_log_json",
        "review_facts_json",
    ):
        p = getattr(arts, attr)
        assert isinstance(p, Path)
        assert p.exists() and p.stat().st_size > 0


def test_run_review_accepts_all_keyword_arguments(tmp_path, gen_dir):
    """The viewer relies on this exact kwargs surface."""
    arts = run_review(
        district=FOCUS_DISTRICT,
        period="2026-05",
        llm_provider="mock",
        top_n_schools=8,
        top_n_blocks=4,
        strict_grounding=False,
        outputs_dir=tmp_path,
        synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    facts = json.loads(arts.review_facts_json.read_text(encoding="utf-8"))
    assert facts["top_n_schools"] == 8
    assert facts["top_n_blocks"] == 4
    assert facts["district"] == FOCUS_DISTRICT


# ---------------------------------------------------------------------------
# Provider/fallback metadata travels through to the audit log
# ---------------------------------------------------------------------------


def test_run_review_preserves_provider_fallback_metadata(tmp_path, gen_dir, monkeypatch):
    """The Streamlit viewer surfaces these fields — they must be present and accurate."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="gemini",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    audit = json.loads(arts.audit_log_json.read_text(encoding="utf-8"))
    for key in (
        "requested_llm_provider",
        "actual_llm_provider",
        "llm_provider",
        "model_name",
        "fallback_used",
        "fallback_reason",
        "grounding_failures",
        "provider_latency_ms",
        "section_metadata",
    ):
        assert key in audit, f"audit_log missing field: {key}"
    assert audit["requested_llm_provider"] == "gemini"
    assert audit["llm_provider"] == "mock"      # fell back
    assert audit["fallback_used"] is True
    assert "missing_credentials" in (audit["fallback_reason"] or "")


def test_run_review_mock_path_records_no_fallback(tmp_path, gen_dir):
    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="mock",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    audit = json.loads(arts.audit_log_json.read_text(encoding="utf-8"))
    assert audit["fallback_used"] is False
    assert audit["llm_provider"] == "mock"
    assert audit["fallback_reason"] is None


# ---------------------------------------------------------------------------
# Service is import-safe even before any data has been generated
# ---------------------------------------------------------------------------


def test_run_review_raises_clearly_when_synthetic_data_missing(tmp_path):
    """The viewer catches this and shows a hint; verify the underlying error is loud."""
    empty_dir = tmp_path / "no_data"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        run_review(
            district=FOCUS_DISTRICT, period="2026-05",
            outputs_dir=tmp_path / "out",
            synthetic_dir=empty_dir,
            timestamp="2026-05-30T00:00:00+00:00",
        )


def test_review_artifacts_as_list_returns_four_paths(tmp_path, gen_dir):
    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    paths = arts.as_list()
    assert len(paths) == 4
    assert all(isinstance(p, Path) for p in paths)
    # Stable ordering (memo, actions, audit, facts) — viewer relies on this.
    assert paths[0].name == "monthly_district_review.md"
    assert paths[1].name == "action_tracker.csv"
    assert paths[2].name == "audit_log.json"
    assert paths[3].name == "review_facts.json"
