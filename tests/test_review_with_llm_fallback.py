"""End-to-end fallback tests for the Review Compiler with real providers.

Each test exercises a different failure mode and asserts that:
  (a) all four artefacts are still written;
  (b) the audit log records the fallback in machine-readable form;
  (c) grounding still passes against the rendered memo.

Zero real network or API keys are used.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import FOCUS_DISTRICT
from app.eval.grounding import check_grounding
from app.review import run_review


def _read_audit(arts) -> dict:
    return json.loads(Path(arts.audit_log_json).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Path 1: provider construction fails (missing credentials) — factory falls back
# ---------------------------------------------------------------------------


def test_gemini_without_credentials_falls_back_at_construction(tmp_path, gen_dir, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="gemini",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )

    for p in arts.as_list():
        assert Path(p).exists() and Path(p).stat().st_size > 0

    audit = _read_audit(arts)
    assert audit["requested_llm_provider"] == "gemini"
    assert audit["llm_provider"] == "mock"
    assert audit["actual_llm_provider"] == "mock"
    assert audit["fallback_used"] is True
    assert "missing_credentials" in (audit["fallback_reason"] or "")

    # Grounding still passes for the (mock-rendered) memo.
    memo = Path(arts.monthly_district_review_md).read_text(encoding="utf-8")
    facts = json.loads(Path(arts.review_facts_json).read_text(encoding="utf-8"))
    assert check_grounding(memo, facts) == []


def test_groq_without_key_falls_back(tmp_path, gen_dir, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="groq",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    audit = _read_audit(arts)
    assert audit["fallback_used"] is True
    assert audit["llm_provider"] == "mock"
    assert audit["requested_llm_provider"] == "groq"


# ---------------------------------------------------------------------------
# Path 2: provider constructs OK but the HTTP call fails — per-section fallback
# ---------------------------------------------------------------------------


def test_gemini_http_error_per_section_falls_back_to_mock(tmp_path, gen_dir, monkeypatch):
    from app.llm._http import HttpError

    monkeypatch.setenv("GOOGLE_API_KEY", "fake-test-key")

    def always_503(*a, **kw):
        raise HttpError("HTTP 503: service unavailable", status=503)

    monkeypatch.setattr("app.llm.gemini_provider.post_json", always_503)

    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="gemini",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )

    for p in arts.as_list():
        assert Path(p).exists() and Path(p).stat().st_size > 0

    audit = _read_audit(arts)
    # Factory succeeded → llm_provider is "gemini" (the requested one)
    assert audit["requested_llm_provider"] == "gemini"
    assert audit["llm_provider"] == "gemini"
    # ... but every section had to fall back to mock.
    assert audit["fallback_used"] is True
    section_meta = audit["section_metadata"]
    assert all(m["fallback_used"] for m in section_meta.values())
    assert all(m["provider"] == "mock" for m in section_meta.values())

    # Grounding still passes for the mock-rendered text.
    memo = Path(arts.monthly_district_review_md).read_text(encoding="utf-8")
    facts = json.loads(Path(arts.review_facts_json).read_text(encoding="utf-8"))
    assert check_grounding(memo, facts) == []


def test_ollama_unreachable_falls_back_to_mock(tmp_path, gen_dir, monkeypatch):
    from app.llm._http import HttpError
    monkeypatch.setattr(
        "app.llm.ollama_provider.post_json",
        lambda *a, **kw: (_ for _ in ()).throw(HttpError("Network failure: refused")),
    )
    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="ollama",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    audit = _read_audit(arts)
    assert audit["requested_llm_provider"] == "ollama"
    assert audit["fallback_used"] is True
    assert all(m["provider"] == "mock" for m in audit["section_metadata"].values())


# ---------------------------------------------------------------------------
# Path 3: HTTP call succeeds but output is ungrounded — grounding fallback
# ---------------------------------------------------------------------------


def test_provider_with_hallucinated_number_fails_grounding_and_falls_back(tmp_path, gen_dir, monkeypatch):
    """Simulate a provider that returns prose with a fabricated number."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.setenv("GROQ_MODEL", "fake-test-model")

    def fake_post(*a, **kw):
        # 987654 is not in any fact — must trigger grounding fallback.
        return {"choices": [{"message": {"content": "Some prose mentioning 987654 children."}}]}

    monkeypatch.setattr("app.llm.groq_provider.post_json", fake_post)

    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="groq",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )

    audit = _read_audit(arts)
    assert audit["requested_llm_provider"] == "groq"
    assert audit["fallback_used"] is True
    # Every section now has the ungrounded number, so every section should have
    # fallen back AND grounding_failures should be populated.
    assert audit["grounding_failures"], "Expected grounding failures to be recorded"
    assert "987654" in next(iter(audit["grounding_failures"].values()))

    # Final memo (now mock-rendered) must still be fully grounded.
    memo = Path(arts.monthly_district_review_md).read_text(encoding="utf-8")
    facts = json.loads(Path(arts.review_facts_json).read_text(encoding="utf-8"))
    assert check_grounding(memo, facts) == []


# ---------------------------------------------------------------------------
# Path 4: strict-grounding flag re-renders the entire memo from mock
# ---------------------------------------------------------------------------


def test_strict_grounding_triggers_full_memo_fallback(tmp_path, gen_dir, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")

    def fake_post(*a, **kw):
        return {"choices": [{"message": {"content": "Fabricated 42424 stats."}}]}

    monkeypatch.setattr("app.llm.groq_provider.post_json", fake_post)

    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="groq",
        strict_grounding=True,
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    audit = _read_audit(arts)
    # After strict re-render, every section is provider=mock and grounding passes.
    assert all(m["provider"] == "mock" for m in audit["section_metadata"].values())
    memo = Path(arts.monthly_district_review_md).read_text(encoding="utf-8")
    facts = json.loads(Path(arts.review_facts_json).read_text(encoding="utf-8"))
    assert check_grounding(memo, facts) == []


# ---------------------------------------------------------------------------
# Path 5: provider works AND is grounded — happy path
# ---------------------------------------------------------------------------


def test_groq_grounded_output_is_kept_no_fallback(tmp_path, gen_dir, monkeypatch):
    """If the provider returns prose that has no numbers, grounding trivially passes
    and the provider's output should be kept (no per-section fallback)."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.setenv("GROQ_MODEL", "fake-test-model")

    grounded_text = (
        "The district shows a mixed picture this period. "
        "Hypothesis: low DIKSHA engagement is correlated with weaker FLN improvement; "
        "this requires field verification before action."
    )

    monkeypatch.setattr(
        "app.llm.groq_provider.post_json",
        lambda *a, **kw: {"choices": [{"message": {"content": grounded_text}}]},
    )

    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="groq",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    audit = _read_audit(arts)
    assert audit["llm_provider"] == "groq"
    # No fallback at construction or section level.
    assert audit["fallback_used"] is False
    assert audit["fallback_reason"] is None
    assert all(m["provider"] == "groq" for m in audit["section_metadata"].values())
    assert audit["grounding_failures"] == {}

    # The memo body should include the provider's prose.
    memo = Path(arts.monthly_district_review_md).read_text(encoding="utf-8")
    assert grounded_text.split(".")[0] in memo


def test_review_never_crashes_for_unknown_provider(tmp_path, gen_dir):
    """Spec requirement: the review command should never crash due to a missing /
    unknown LLM provider."""
    arts = run_review(
        district=FOCUS_DISTRICT, period="2026-05",
        llm_provider="some-future-provider-that-does-not-exist",
        outputs_dir=tmp_path, synthetic_dir=gen_dir,
        timestamp="2026-05-30T00:00:00+00:00",
    )
    for p in arts.as_list():
        assert Path(p).exists() and Path(p).stat().st_size > 0
    audit = _read_audit(arts)
    assert audit["fallback_used"] is True
    assert "unknown_provider" in (audit["fallback_reason"] or "")
