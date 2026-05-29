"""LLM provider factory.

The factory returns the requested provider when known, or falls back to MockLLM with a
warning when not. Callers receive a small `ProviderResolution` describing what they
actually got, so the audit log can record the fallback (a load-bearing trust signal).

Phase 1 ships with MockLLM only. The signature is shaped so adding Gemini / Groq /
Ollama later is a one-line registration here — no caller needs to change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from app.llm.base import LLMProvider
from app.llm.mock_llm import MockLLM

logger = logging.getLogger(__name__)


# Map provider name -> zero-arg constructor. Lazily evaluated so adding a future
# provider does not force its dependencies to import on the mock path.
_REGISTRY: dict[str, Callable[[], LLMProvider]] = {
    "mock": MockLLM,
}


@dataclass(frozen=True)
class ProviderResolution:
    """What `get_provider` actually returned, including any fallback bookkeeping."""

    provider: LLMProvider
    name: str               # actual name returned ("mock" today)
    requested: str          # what the caller asked for
    fallback_used: bool     # True if we returned mock because `requested` was unknown


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def get_provider(name: str | None = "mock") -> ProviderResolution:
    """Resolve an LLM provider by name. Unknown names log a warning and fall back to mock."""
    requested = (name or "mock").strip().lower()
    constructor = _REGISTRY.get(requested)
    if constructor is None:
        logger.warning(
            "Unknown LLM provider %r; falling back to MockLLM. Available: %s",
            requested,
            list_providers(),
        )
        return ProviderResolution(
            provider=MockLLM(),
            name="mock",
            requested=requested,
            fallback_used=True,
        )
    return ProviderResolution(
        provider=constructor(),
        name=requested,
        requested=requested,
        fallback_used=False,
    )
