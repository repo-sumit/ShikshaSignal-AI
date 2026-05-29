"""Factory tests — what `get_provider(...)` returns for each name + failure mode.

These tests run entirely offline and do not depend on any real LLM credentials.
"""

from __future__ import annotations

import pytest

from app.llm.factory import ProviderResolution, get_provider, list_providers
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.mock_llm import MockLLM
from app.llm.ollama_provider import OllamaProvider


def _clear_llm_env(monkeypatch):
    for var in (
        "GOOGLE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
        "GEMINI_MODEL", "GROQ_MODEL", "OLLAMA_BASE_URL", "OLLAMA_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Mock is the default; everything else is also listed
# ---------------------------------------------------------------------------


def test_list_providers_includes_all_four():
    assert set(list_providers()) == {"mock", "gemini", "groq", "ollama"}


def test_mock_is_default_when_no_name_passed(monkeypatch):
    _clear_llm_env(monkeypatch)
    res = get_provider(None)
    assert isinstance(res, ProviderResolution)
    assert res.name == "mock"
    assert isinstance(res.provider, MockLLM)
    assert res.fallback_used is False
    assert res.fallback_reason is None
    assert res.requested == "mock"


def test_explicit_mock_request(monkeypatch):
    _clear_llm_env(monkeypatch)
    res = get_provider("mock")
    assert res.name == "mock"
    assert res.fallback_used is False


# ---------------------------------------------------------------------------
# Unknown names fall back to mock with reason
# ---------------------------------------------------------------------------


def test_unknown_provider_falls_back_to_mock(monkeypatch):
    _clear_llm_env(monkeypatch)
    res = get_provider("some-future-thing")
    assert res.name == "mock"
    assert res.fallback_used is True
    assert res.fallback_reason is not None
    assert "unknown_provider" in res.fallback_reason
    assert res.requested == "some-future-thing"


# ---------------------------------------------------------------------------
# Missing-credential providers fall back to mock with reason
# ---------------------------------------------------------------------------


def test_gemini_without_keys_falls_back_to_mock(monkeypatch):
    _clear_llm_env(monkeypatch)
    res = get_provider("gemini")
    assert res.name == "mock"
    assert res.fallback_used is True
    assert "missing_credentials" in (res.fallback_reason or "")
    assert res.requested == "gemini"


def test_groq_without_key_falls_back_to_mock(monkeypatch):
    _clear_llm_env(monkeypatch)
    res = get_provider("groq")
    assert res.name == "mock"
    assert res.fallback_used is True
    assert "missing_credentials" in (res.fallback_reason or "")


# ---------------------------------------------------------------------------
# When credentials are present, the real provider is constructed
# ---------------------------------------------------------------------------


def test_gemini_with_google_api_key_constructs(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key-for-test")
    res = get_provider("gemini")
    assert res.name == "gemini"
    assert isinstance(res.provider, GeminiProvider)
    assert res.fallback_used is False
    assert res.model == "gemini-1.5-flash"


def test_gemini_accepts_gemini_api_key_alias(monkeypatch):
    """GOOGLE_API_KEY is canonical, but GEMINI_API_KEY also works (back-compat)."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    res = get_provider("gemini")
    assert res.name == "gemini"
    assert res.fallback_used is False


def test_groq_with_key_constructs(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    res = get_provider("groq")
    assert res.name == "groq"
    assert isinstance(res.provider, GroqProvider)
    assert res.fallback_used is False
    assert res.model == "llama-3.1-8b-instant"


def test_ollama_always_constructs_no_key_required(monkeypatch):
    """Ollama needs no credentials at construction; reachability is checked at call time."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example.invalid:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    res = get_provider("ollama")
    assert res.name == "ollama"
    assert isinstance(res.provider, OllamaProvider)
    assert res.fallback_used is False
    assert res.provider.base_url == "http://example.invalid:11434"
    assert res.model == "qwen2.5:7b"


# ---------------------------------------------------------------------------
# Resolution metadata contract
# ---------------------------------------------------------------------------


def test_resolution_metadata_shape(monkeypatch):
    _clear_llm_env(monkeypatch)
    res = get_provider("mock")
    # Stable surface used by review.py + audit log.
    assert hasattr(res, "provider")
    assert hasattr(res, "name")
    assert hasattr(res, "requested")
    assert hasattr(res, "fallback_used")
    assert hasattr(res, "fallback_reason")
    assert hasattr(res, "model")
    assert res.is_mock is True


def test_get_provider_never_raises(monkeypatch):
    """The factory's contract: any input must produce a working provider."""
    _clear_llm_env(monkeypatch)
    for name in ["mock", "gemini", "groq", "ollama", "totally-unknown", "", None]:
        res = get_provider(name)
        assert res.provider is not None
        # Even on fallback, the resulting provider must be usable.
        assert callable(getattr(res.provider, "generate", None))
