"""LLM provider interface used by the Review Compiler.

A provider takes a `section_name` plus a *dictionary of pre-computed facts* and returns
PROSE only. Providers must never compute numbers, rank anything, or invent facts that are
not already present in the facts dict — the deterministic core has done all the math, and
grounding tests will fail any number that does not trace back to `review_facts.json`.

Concrete providers in this phase: `MockLLM` (Jinja templates, no network). Future phases
will add Gemini / Groq / Ollama implementations behind the exact same interface.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable


# Section names the Review Compiler narrates. Listed here so providers and tests share one
# definition of "what is expected to exist."
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


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal contract every LLM backend must satisfy.

    Implementations should be DETERMINISTIC for the same inputs in this milestone so
    grounding tests and golden diffs remain stable.
    """

    name: str

    def generate_section(self, section_name: str, facts: Mapping[str, object]) -> str:
        """Return human-readable prose for `section_name` using only values in `facts`."""
        ...


class UnknownSectionError(ValueError):
    """Raised when a provider is asked to narrate a section it does not know about."""


def assert_supported(section_name: str) -> None:
    if section_name not in SUPPORTED_SECTIONS:
        raise UnknownSectionError(
            f"Section {section_name!r} is not in SUPPORTED_SECTIONS. "
            f"Add it to app.llm.base.SUPPORTED_SECTIONS and provide a template."
        )
