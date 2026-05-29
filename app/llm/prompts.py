"""Prompt construction shared by every real-LLM provider.

The Review Compiler hands these providers ONLY the facts dict, never raw CSVs. Each
section gets the same strict instruction set, plus a section-specific intent. The
deterministic core has already done all the math; the LLM's job is to *write English
prose over the supplied JSON*. After generation, `app.eval.grounding` enforces that
the LLM did not invent a single number.
"""

from __future__ import annotations

import json
from typing import Mapping


# Headline rules every provider receives, verbatim, before the section intent. These
# mirror the project's locked design constraints (CONTEXT.md §20 + plan.md §10).
GROUNDING_RULES: str = """
You are drafting one section of a Monthly District Review for a government education
programme. Follow these rules WITHOUT EXCEPTION:

1. Use ONLY the values in REVIEW_FACTS below. Do not introduce any new numbers, names,
   percentages, dates, school IDs, or block names. Copy numbers verbatim if you must
   cite them; never round, average, or recompute.
2. Do not calculate or infer. If REVIEW_FACTS does not contain a value, omit the claim
   rather than guessing.
3. Causal explanations MUST be labelled as "Hypothesis" and must say "requires field
   verification" or equivalent.
4. Tone: professional, evidence-backed, government-review friendly. Be concise and
   action-oriented; no marketing language.
5. Output only the prose for the requested section. Do NOT repeat the heading. Do not
   add a sign-off, a disclaimer, or your own commentary about these rules.
""".strip()


# What each section is for — pinned wording so the prompt is reproducible.
_SECTION_INTENTS: dict[str, str] = {
    "executive_summary": (
        "Write a single tight paragraph (3-5 sentences) summarising the district's "
        "status for this period. Cover: schools + blocks covered; coverage %; the "
        "health score and the data-quality score; the band split; and the highest-risk "
        "block by name."
    ),
    "what_changed": (
        "Write one short paragraph describing how DIKSHA usage moved between the prior "
        "and the latest week. Mention the week labels exactly as given. If there is a "
        "top decliner, describe it; otherwise say so. Never derive new percentages."
    ),
    "top_blocks_narrative": (
        "Write one short paragraph framing the table of top-risk blocks that follows. "
        "Do not list the blocks one-by-one — the table renders them deterministically. "
        "Reference only the count of blocks shown and the district name."
    ),
    "top_schools_narrative": (
        "Write one short paragraph framing the table of top-risk schools that follows. "
        "Mention that the table includes the per-component breakdown and the two top "
        "drivers per school. Do not name individual schools."
    ),
    "data_quality_warnings": (
        "Write one short paragraph framing the data-quality findings table that "
        "follows. Mention the total number of finding types but do not list them."
    ),
    "policy_observations": (
        "Write one short paragraph framing the KPI-to-policy linkage table that "
        "follows. State plainly that each KPI gap is linked to a policy source. If "
        "no policy linkage was available this run, say policy context was unavailable."
    ),
    "root_cause_hypotheses": (
        "Write one short paragraph introducing the hypotheses bullet list that "
        "follows. Stress that they are hypotheses requiring field verification."
    ),
    "recommended_actions": (
        "Write one short paragraph introducing the proposed actions table. Note that "
        "every action starts as 'proposed' and requires human approval before being "
        "communicated externally."
    ),
    "stakeholder_message_brc": (
        "Draft a short WhatsApp-style message to the Block Resource Coordinator of "
        "the top-risk block. Include: greeting; the block's mean risk and count of "
        "High-band schools; a request to prioritise the schools in the attached "
        "action tracker; a one-line ask to acknowledge once a visit is scheduled. "
        "Five sentences maximum."
    ),
    "stakeholder_message_dleo": (
        "Draft a short email-style message to the District Education Officer. "
        "Include: district health score; share of schools in the High risk band; "
        "usage coverage and the number of schools not reporting in the latest week; "
        "what is attached; a request for sign-off on the top-N proposed actions. "
        "Six sentences maximum."
    ),
    "meeting_questions": (
        "List 3-5 sharp questions an officer should walk into the review meeting "
        "with. Each question must reference a concrete signal from REVIEW_FACTS "
        "(e.g. the top-risky blocks, missing-data schools, hypotheses). Avoid generic "
        "questions. Output as a markdown bullet list."
    ),
    "assumptions": (
        "Write one short paragraph stating the run's assumptions and limitations. "
        "Cover: synthetic data; deterministic numbers for a fixed seed; risk model "
        "version; root causes are hypotheses; policy targets come from policy_map.yaml; "
        "and which LLM provider answered (fall back disclosure if applicable)."
    ),
}


def section_intent(section_name: str) -> str:
    return _SECTION_INTENTS.get(
        section_name,
        "Write a short, evidence-backed paragraph for this section using only the "
        "facts provided.",
    )


def build_section_prompt(
    section_name: str,
    facts: Mapping[str, object],
    policy_snippets: list[str] | None = None,
) -> str:
    """Render the full prompt sent to a real LLM provider for one section.

    `policy_snippets` is an optional list of pre-retrieved policy strings (Milestone 2
    plug-in point). In this milestone the snippets are not used yet — the placeholder
    keeps the prompt shape stable for when policy RAG returns.
    """
    intent = section_intent(section_name)
    snippets_block = ""
    if policy_snippets:
        snippets_block = (
            "\n\nRELEVANT_POLICY_SNIPPETS (use only as guidance for tone; do not invent "
            "numbers from them):\n" + "\n---\n".join(policy_snippets)
        )
    facts_json = json.dumps(_strip_internal_keys(facts), indent=2, sort_keys=False, default=str)
    return (
        f"{GROUNDING_RULES}\n\n"
        f"SECTION: {section_name}\n"
        f"SECTION_INTENT: {intent}{snippets_block}\n\n"
        f"REVIEW_FACTS (the ONLY allowed source of numbers and names):\n{facts_json}\n"
    )


def _strip_internal_keys(facts: Mapping[str, object]) -> dict[str, object]:
    """Drop facts keys that should not leak into the prompt (e.g. in-memory dataframes)."""
    return {k: v for k, v in facts.items() if not k.startswith("_")}
