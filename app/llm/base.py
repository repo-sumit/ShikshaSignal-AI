"""LLM provider interface used by the Review Compiler.

A provider takes a `section_name` plus a dictionary of pre-computed facts and returns
PROSE only. Providers must never compute numbers, rank anything, or invent facts that
are not already present in the facts dict — the deterministic core has done all the
math, and the grounding check (`app.eval.grounding`) will fail any number that does
not trace back to `review_facts.json`.

Phase-2 providers (Milestone 3): `MockLLM` (Jinja templates, offline default).
Phase-4 providers (Milestone 4): `GeminiProvider`, `GroqProvider`, `OllamaProvider`,
all behind the same `BaseLLMProvider` contract so the Review Compiler does not need to
know which backend is in use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable


# Section names the Review Compiler narrates. Listed here so providers and tests share
# one definition of "what is expected to exist."
SUPPORTED_SECTIONS: tuple[str, ...] = (
    "executive_summary",
    "what_changed",
    "top_blocks_narrative",
    "top_schools_narrative",
    "data_quality_warnings",
    "policy_observations",
    "root_cause_hypotheses",
    "recommended_actions",
    "stakeholder_message_brc",
    "stakeholder_message_dleo",
    "meeting_questions",
    "assumptions",
)


# ---------------------------------------------------------------------------
# Result type — what providers actually hand back
# ---------------------------------------------------------------------------


@dataclass
class GenerationResult:
    """One section's generation outcome, with provenance + telemetry.

    `text` is empty when the call failed; callers MUST treat an empty text or a non-None
    `error` as a signal to fall back. `model` is the concrete model identifier that
    answered (e.g. ``gemini-1.5-flash``); for MockLLM it is the template-set tag.
    """

    text: str
    provider_name: str
    model: str | None = None
    latency_ms: float = 0.0
    error: str | None = None
    # Set by the orchestrator (not the provider) when a per-section fallback was used.
    fallback_used: bool = False
    fallback_reason: str | None = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnknownSectionError(ValueError):
    """Raised when a provider is asked to narrate a section it does not know about."""


class MissingCredentialsError(RuntimeError):
    """Raised at provider construction when required env vars are absent.

    The factory catches this and falls back to MockLLM, recording the reason in the
    audit log so a reviewer can see why the cheaper path was taken.
    """


class ProviderCallError(RuntimeError):
    """Raised inside `generate` for transport-level failures (HTTP, parse, timeout).

    Providers should prefer returning a `GenerationResult` with `error` set rather than
    propagating this — the orchestrator only catches it as a last-ditch safety net.
    """


def assert_supported(section_name: str) -> None:
    if section_name not in SUPPORTED_SECTIONS:
        raise UnknownSectionError(
            f"Section {section_name!r} is not in SUPPORTED_SECTIONS. "
            f"Add it to app.llm.base.SUPPORTED_SECTIONS and provide a template."
        )


# ---------------------------------------------------------------------------
# Provider contracts
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal duck-typed contract — what the Review Compiler historically used.

    Kept for back-compat with Milestone 3 code paths. New code should prefer the
    `BaseLLMProvider` ABC below, which carries the richer `GenerationResult`.
    """

    name: str

    def generate_section(self, section_name: str, facts: Mapping[str, object]) -> str: ...


class BaseLLMProvider(ABC):
    """Abstract base for all real LLM providers.

    Subclasses MUST implement `generate(section, facts) -> GenerationResult`. The
    legacy `generate_section(section, facts) -> str` shim is provided here so existing
    callers continue to work unchanged.
    """

    name: str = "base"
    model: str | None = None

    @abstractmethod
    def generate(self, section_name: str, facts: Mapping[str, object]) -> GenerationResult:
        """Return a `GenerationResult` for `section_name`.

        Implementations should catch their own transport failures and return a result
        with `error` set + empty `text`, rather than raising. This keeps the
        orchestrator's fallback logic uniform across providers.
        """

    def generate_section(self, section_name: str, facts: Mapping[str, object]) -> str:
        """Back-compat shim — returns just the text. Loses telemetry; new callers
        should use `generate(...)` directly."""
        return self.generate(section_name, facts).text
