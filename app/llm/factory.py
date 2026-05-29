"""LLM provider factory.

`get_provider(name)` returns a `ProviderResolution` carrying:

  * the concrete provider instance (always a working object — never None);
  * the requested name (what the caller asked for);
  * `fallback_used: bool` and `fallback_reason: str | None` describing whether
    we had to swap to MockLLM, and why.

Three fall-back paths:
  1. **Unknown provider name** — log a warning, return MockLLM.
  2. **Construction failed (MissingCredentialsError)** — log a warning, return MockLLM.
  3. **Other construction error** (e.g. import-time failure) — log warning, MockLLM.

Call-time failures (HTTP error, grounding miss) are *not* the factory's concern; the
review compiler handles those per section and records them in the audit log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from app.llm.base import BaseLLMProvider, MissingCredentialsError
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.mock_llm import MockLLM
from app.llm.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


# Lazily-resolved registry. Constructor failures bubble up so we can capture the reason
# in `ProviderResolution.fallback_reason`.
_REGISTRY: dict[str, Callable[[], BaseLLMProvider]] = {
    "mock": MockLLM,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
}


@dataclass(frozen=True)
class ProviderResolution:
    """What `get_provider` actually returned, with fall-back bookkeeping."""

    provider: BaseLLMProvider
    name: str
    requested: str
    fallback_used: bool
    fallback_reason: str | None = None
    model: str | None = None

    @property
    def is_mock(self) -> bool:
        return self.name == "mock"


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def _mock_resolution(requested: str, reason: str) -> ProviderResolution:
    mock = MockLLM()
    logger.warning("LLM factory falling back to MockLLM (requested=%r, reason=%s)", requested, reason)
    return ProviderResolution(
        provider=mock,
        name=mock.name,
        requested=requested,
        fallback_used=True,
        fallback_reason=reason,
        model=mock.model,
    )


def get_provider(name: str | None = "mock") -> ProviderResolution:
    """Resolve an LLM provider by name with safe fallback semantics.

    Never raises — even unknown providers and missing credentials produce a working
    MockLLM resolution with `fallback_used=True`.
    """
    requested = (name or "mock").strip().lower()

    if requested == "mock":
        mock = MockLLM()
        return ProviderResolution(
            provider=mock,
            name=mock.name,
            requested=requested,
            fallback_used=False,
            fallback_reason=None,
            model=mock.model,
        )

    constructor = _REGISTRY.get(requested)
    if constructor is None:
        return _mock_resolution(requested, f"unknown_provider:{requested}")

    try:
        instance = constructor()
    except MissingCredentialsError as e:
        return _mock_resolution(requested, f"missing_credentials:{e}")
    except Exception as e:  # import error, env parsing, etc.
        return _mock_resolution(requested, f"construction_error:{type(e).__name__}:{e}")

    return ProviderResolution(
        provider=instance,
        name=instance.name,
        requested=requested,
        fallback_used=False,
        fallback_reason=None,
        model=getattr(instance, "model", None),
    )
