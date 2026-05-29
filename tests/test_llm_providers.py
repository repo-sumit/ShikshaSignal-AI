"""Per-provider tests with monkeypatched HTTP — zero real network, zero real keys.

We monkeypatch `app.llm._http.post_json` (the single transport seam) so each provider
test exercises the request shape it builds, the response parser, and the error path.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.llm._http import HttpError
from app.llm.base import GenerationResult, MissingCredentialsError
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.mock_llm import MockLLM
from app.llm.ollama_provider import OllamaProvider


SAMPLE_FACTS: dict[str, Any] = {
    "district": "District Alpha",
    "period": "2026-05",
    "schools": 120,
    "blocks": 6,
    "coverage_pct": 92.5,
    "health_score": 40,
    "data_quality_score": 46,
    "band_split": {"High": 12, "Medium": 38, "Low": 50},
    "top_block": {"block": "District Alpha / Madhopur", "mean_risk": 68.4, "high_risk_schools": 9},
    "usage_delta": {"latest_week": "2026-W25", "prior_week": "2026-W24",
                    "sessions_latest_mean": 34.5, "sessions_prior_mean": 33.4, "wow_pct": 3.3},
    "decliners_count": 0,
    "top_decliner": None,
    "top_blocks": [{"rank": 1, "block": "X", "mean_risk": 60, "risk_band": "Medium", "high_risk_schools": 4}],
    "top_schools": [],
    "data_quality": {"findings": [], "findings_count": 0,
                     "coverage": {"schools_total": 120, "schools_reporting": 110}},
    "kpi_rows": [],
    "policy_observations": [],
    "policy_observations_available": False,
    "root_cause_hypotheses": [],
    "action_preview": [],
    "risk_model_version": "1.0",
    "schools_not_reporting": 10,
    "llm_provider": "test",
    "requested_provider": "test",
    "fallback_used": False,
    "top_n_actions": 10,
    "top_n_blocks": 5,
    "top_n_schools": 10,
}


# ---------------------------------------------------------------------------
# MockLLM remains the safest path
# ---------------------------------------------------------------------------


def test_mock_provider_returns_generation_result():
    mock = MockLLM()
    result = mock.generate("executive_summary", SAMPLE_FACTS)
    assert isinstance(result, GenerationResult)
    assert result.provider_name == "mock"
    assert result.model == "jinja-templates-v1"
    assert result.error is None
    assert result.text  # non-empty prose
    assert result.latency_ms >= 0


def test_mock_back_compat_shim_still_returns_string():
    """The legacy Milestone-3 `generate_section(...) -> str` API still works."""
    text = MockLLM().generate_section("executive_summary", SAMPLE_FACTS)
    assert isinstance(text, str) and text


# ---------------------------------------------------------------------------
# Gemini (monkeypatched HTTP)
# ---------------------------------------------------------------------------


def test_gemini_missing_key_raises_at_construction(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingCredentialsError):
        GeminiProvider()


def test_gemini_happy_path(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    captured: dict = {}

    def fake_post(url, payload, headers=None, timeout=20.0):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"candidates": [{"content": {"parts": [{"text": "Generated prose."}]}}]}

    monkeypatch.setattr("app.llm.gemini_provider.post_json", fake_post)

    provider = GeminiProvider(model="gemini-1.5-flash")
    result = provider.generate("executive_summary", SAMPLE_FACTS)

    assert result.provider_name == "gemini"
    assert result.model == "gemini-1.5-flash"
    assert result.text == "Generated prose."
    assert result.error is None
    assert "generativelanguage.googleapis.com" in captured["url"]
    assert "key=fake-key" in captured["url"]
    # Prompt is wrapped in the Gemini "contents/parts/text" shape.
    assert captured["payload"]["contents"][0]["parts"][0]["text"].startswith("You are drafting")


def test_gemini_http_error_returns_result_with_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    def fake_post(*a, **kw):
        raise HttpError("HTTP 503: service unavailable", status=503)

    monkeypatch.setattr("app.llm.gemini_provider.post_json", fake_post)

    result = GeminiProvider().generate("executive_summary", SAMPLE_FACTS)
    assert result.text == ""
    assert result.error is not None
    assert "503" in result.error
    assert result.provider_name == "gemini"


def test_gemini_empty_candidates_treated_as_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    monkeypatch.setattr("app.llm.gemini_provider.post_json", lambda *a, **kw: {"candidates": []})
    result = GeminiProvider().generate("executive_summary", SAMPLE_FACTS)
    assert result.text == ""
    assert result.error and "empty" in result.error.lower()


# ---------------------------------------------------------------------------
# Groq (monkeypatched HTTP)
# ---------------------------------------------------------------------------


def test_groq_missing_key_raises_at_construction(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(MissingCredentialsError):
        GroqProvider()


def test_groq_happy_path(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")

    captured: dict = {}

    def fake_post(url, payload, headers=None, timeout=20.0):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "Groq generated prose."}}]}

    monkeypatch.setattr("app.llm.groq_provider.post_json", fake_post)
    provider = GroqProvider(model="llama-3.1-8b-instant")
    result = provider.generate("executive_summary", SAMPLE_FACTS)

    assert result.provider_name == "groq"
    assert result.model == "llama-3.1-8b-instant"
    assert result.text == "Groq generated prose."
    assert result.error is None
    assert "groq.com" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer fake-key"
    # OpenAI-compatible body shape.
    assert "messages" in captured["payload"]
    assert captured["payload"]["model"] == "llama-3.1-8b-instant"


def test_groq_http_error_returns_result_with_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(
        "app.llm.groq_provider.post_json",
        lambda *a, **kw: (_ for _ in ()).throw(HttpError("network failure")),
    )
    result = GroqProvider().generate("executive_summary", SAMPLE_FACTS)
    assert result.text == ""
    assert result.error and "network" in result.error.lower()


def test_groq_empty_choices_treated_as_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.setattr("app.llm.groq_provider.post_json", lambda *a, **kw: {"choices": []})
    result = GroqProvider().generate("executive_summary", SAMPLE_FACTS)
    assert result.text == ""
    assert result.error and "empty" in result.error.lower()


# ---------------------------------------------------------------------------
# Ollama (monkeypatched HTTP)
# ---------------------------------------------------------------------------


def test_ollama_construction_does_not_probe_server(monkeypatch):
    """Construction must not perform any network IO — important for hermetic tests."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://nowhere.invalid:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    provider = OllamaProvider()
    assert provider.base_url == "http://nowhere.invalid:11434"
    assert provider.model == "qwen2.5:7b"


def test_ollama_happy_path(monkeypatch):
    captured: dict = {}

    def fake_post(url, payload, headers=None, timeout=60.0):
        captured["url"] = url
        captured["payload"] = payload
        return {"response": "Ollama generated prose.", "done": True}

    monkeypatch.setattr("app.llm.ollama_provider.post_json", fake_post)
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:7b")
    result = provider.generate("executive_summary", SAMPLE_FACTS)

    assert result.provider_name == "ollama"
    assert result.text == "Ollama generated prose."
    assert result.error is None
    assert captured["url"].endswith("/api/generate")
    assert captured["payload"]["model"] == "qwen2.5:7b"
    assert captured["payload"]["stream"] is False


def test_ollama_unreachable_returns_result_with_error(monkeypatch):
    """If the daemon is down, the provider must surface the error and not raise."""
    def fake_post(*a, **kw):
        raise HttpError("Network failure: [Errno 111] Connection refused")

    monkeypatch.setattr("app.llm.ollama_provider.post_json", fake_post)
    result = OllamaProvider(base_url="http://localhost:11434").generate(
        "executive_summary", SAMPLE_FACTS
    )
    assert result.text == ""
    assert result.error and "connection" in result.error.lower()


def test_ollama_empty_response_treated_as_error(monkeypatch):
    monkeypatch.setattr("app.llm.ollama_provider.post_json", lambda *a, **kw: {"response": ""})
    result = OllamaProvider().generate("executive_summary", SAMPLE_FACTS)
    assert result.text == ""
    assert result.error and "empty" in result.error.lower()
