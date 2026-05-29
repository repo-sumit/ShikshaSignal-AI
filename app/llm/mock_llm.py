"""MockLLM — deterministic Jinja-template-based narrator (default LLM provider).

Why this is the default and not "just a fallback":
  * It runs offline, no API keys, free, byte-stable.
  * The Review Compiler's contract is that every NUMBER in the memo comes from the
    facts dict; MockLLM enforces that by *only* substituting values that exist in
    `facts` — no model freedom to round, paraphrase numerically, or invent.
  * It is the load-bearing eval target: the grounding test diffs the memo against
    `review_facts.json` and must pass at all times, including in CI without network.

Every section is rendered from a small Jinja template kept inline. The templates use
only values that the Review Compiler puts into the facts dict.

Run as a quick smoke test:
    python -m app.llm.mock_llm
"""

from __future__ import annotations

import json
import time
from typing import Mapping

import jinja2

from app.llm.base import (
    SUPPORTED_SECTIONS,
    BaseLLMProvider,
    GenerationResult,
    assert_supported,
)


# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------

# A reusable "no data" string so missing facts produce graceful prose rather than crashes.
_NA = "not available"


_TEMPLATES: dict[str, str] = {
    # ---- Executive summary ---------------------------------------------------
    "executive_summary": """
{{ district }} review for period {{ period }} covers {{ schools }} schools across {{ blocks }} blocks. Usage reporting coverage is {{ coverage_pct }}%, district health score is {{ health_score }}/100, and the data-quality score is {{ data_quality_score }}/100. Of the schools scored, {{ band_split.High }}% are High risk, {{ band_split.Medium }}% Medium, and {{ band_split.Low }}% Low.{% if top_block %} The block requiring the most attention is {{ top_block.block }} (mean risk {{ top_block.mean_risk }}, {{ top_block.high_risk_schools }} schools in the High band).{% endif %}
""".strip(),

    # ---- What changed --------------------------------------------------------
    "what_changed": """
DIKSHA usage moved from {{ usage_delta.sessions_prior_mean }} sessions/school in {{ usage_delta.prior_week }} to {{ usage_delta.sessions_latest_mean }} in {{ usage_delta.latest_week }}{% if usage_delta.wow_pct is not none %} (week-over-week {{ usage_delta.wow_pct }}%){% endif %}. {% if decliners_count == 0 %}No material decliners were detected this period (schools dropping below 60% of their recent mean).{% else %}{{ decliners_count }} school(s) registered a material decline against their recent mean; the steepest is {{ top_decliner.school_id }} in {{ top_decliner.block }}, from {{ top_decliner.sessions_prior_mean }} to {{ top_decliner.sessions_latest }} sessions ({{ top_decliner.drop_vs_recent_pct }}%).{% endif %}
""".strip(),

    # ---- Top blocks narrative -----------------------------------------------
    "top_blocks_narrative": """
{% if top_blocks %}Across {{ district }}, the {{ top_n_blocks }} blocks with the highest mean school risk this period are listed below. Each row shows the block's mean risk score, band, and count of schools in the High band.{% else %}No blocks ranked above the threshold this period.{% endif %}
""".strip(),

    # ---- Top schools narrative ----------------------------------------------
    "top_schools_narrative": """
{% if top_schools %}The top {{ top_n_schools }} highest-risk schools below carry the full per-component breakdown (learning_outcome, digital_usage, teacher_training, infrastructure, field_issue, data_availability, data_quality) and the two drivers contributing most to the score. Every score is hand-recomputable from the components and the weights in the audit log.{% else %}No schools ranked above the threshold this period.{% endif %}
""".strip(),

    # ---- Data quality warnings ----------------------------------------------
    "data_quality_warnings": """
{% if data_quality.findings %}The data-quality pass found {{ data_quality.findings_count }} type(s) of issue. The largest contributors are:{% else %}No data-quality issues were flagged this period.{% endif %}
""".strip(),

    # ---- Policy observations -------------------------------------------------
    "policy_observations": """
{% if policy_observations_available %}KPI gaps below are linked to the relevant policy mandate via data/policy_map.yaml. Every row cites the source mandate the target is derived from.{% else %}Policy context was unavailable for this run — no entries were found in data/policy_map.yaml, so policy linkage is omitted.{% endif %}
""".strip(),

    # ---- Root-cause hypotheses ----------------------------------------------
    "root_cause_hypotheses": """
The following hypotheses are derived from the top driver of each high-risk school and the data-quality findings. They are labelled *Hypothesis* deliberately: they explain a pattern in the data and require field verification before being treated as causal. Numbers in each line trace to the per-school risk components.
""".strip(),

    # ---- Recommended actions -------------------------------------------------
    "recommended_actions": """
Each row in the action tracker maps a top-risk school's primary driver to a concrete next step, a suggested owner (role, not a named individual), a priority, the supporting evidence, and the policy reference. Status starts as *proposed*; a human reviewer must approve before any action is communicated externally.
""".strip(),

    # ---- Stakeholder message - BRC -----------------------------------------
    "stakeholder_message_brc": """
To: Block Resource Coordinator, {{ top_block.block if top_block else 'the highest-risk block' }}
Subject: Priority schools for the next field visit cycle

Namaste, sharing the priority schools flagged in the {{ period }} review for {{ district }}. The block's mean risk is {{ top_block.mean_risk if top_block else _na }} with {{ top_block.high_risk_schools if top_block else _na }} schools in the High band. Please prioritise mentor visits to the schools listed in the attached action tracker. Each row carries the primary risk driver and the supporting evidence. Please mark the action *acknowledged* once a visit is scheduled.
""".strip(),

    # ---- Stakeholder message - District Education Officer -------------------
    "stakeholder_message_dleo": """
To: District Education Officer, {{ district }}
Subject: {{ period }} review summary

Briefly: {{ district }} health score for {{ period }} is {{ health_score }}/100. {{ band_split.High }}% of schools are in the High risk band. Usage coverage is {{ coverage_pct }}% with {{ schools_not_reporting }} schools not reporting in {{ usage_delta.latest_week }}. The full review memo, risk ranking, and action tracker (status: proposed) are attached. Requesting your review and sign-off on the Top-{{ top_n_actions }} actions before circulation.
""".strip(),

    # ---- Meeting questions ---------------------------------------------------
    "meeting_questions": """
Suggested questions to walk into the review meeting with:
- Which of the Top-{{ top_n_blocks }} risky blocks have a mentor visit already scheduled this cycle?
- For schools missing the latest week of DIKSHA usage data, who is responsible for following up on data submission?
- Which planted root-cause hypothesis can be confirmed or refuted by the BRC in the next two days?
- Of the Top-{{ top_n_actions }} proposed actions, which can be approved today and which need owner clarification?
""".strip(),

    # ---- Assumptions / limitations ------------------------------------------
    "assumptions": """
This memo was generated from SYNTHETIC, public-safe data (see disclaimer above). Numbers are deterministic for a fixed seed. The risk score follows model v{{ risk_model_version }} with weights documented in the audit log. Root causes are labelled hypotheses and require field verification. Policy targets are loaded from data/policy_map.yaml, not from RAG over policy PDFs (intentionally deferred to a later phase). The LLM provider for this run was {{ llm_provider }}{% if fallback_used %} (auto-fell back from {{ requested_provider }} to mock){% endif %}.
""".strip(),
}


class MockLLM(BaseLLMProvider):
    """Deterministic Jinja-based provider used as the project's default narrator.

    `model` is set to a stable tag so audit logs can distinguish MockLLM runs.
    """

    name = "mock"
    model = "jinja-templates-v1"

    def __init__(self) -> None:
        self._env = jinja2.Environment(
            undefined=jinja2.ChainableUndefined,  # missing facts render as empty, not raise
            autoescape=False,
            keep_trailing_newline=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ---- Patchable text-only API (Milestone 3 test surface) -----------------

    def generate_section(self, section_name: str, facts: Mapping[str, object]) -> str:
        """Render the section as plain text.

        This is the layer Milestone 3 tests monkeypatch to simulate hallucinated
        output; keep it as the single place rendering happens so both old and new
        callers see the same string.
        """
        assert_supported(section_name)
        template_src = _TEMPLATES.get(section_name)
        if template_src is None:
            raise KeyError(f"No template registered for section {section_name!r}.")
        template = self._env.from_string(template_src)
        ctx: dict[str, object] = {"_na": _NA}
        ctx.update(facts)
        rendered = template.render(**ctx)
        # Collapse blank lines that Jinja sometimes leaves between blocks.
        return "\n".join(line.rstrip() for line in rendered.splitlines() if line.strip()).strip()

    # ---- New `generate(...) -> GenerationResult` path -----------------------
    # Delegates to generate_section so any monkeypatch of the text-only seam
    # propagates here too (the M3 grounding-injection test relies on this).

    def generate(self, section_name: str, facts: Mapping[str, object]) -> GenerationResult:
        t0 = time.perf_counter()
        try:
            text = self.generate_section(section_name, facts)
            return GenerationResult(
                text=text,
                provider_name=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:  # pragma: no cover - mock should not fail in practice
            return GenerationResult(
                text="",
                provider_name=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error=str(e),
            )


def main() -> None:
    """Quick smoke render for every section so the template set stays valid."""
    sample_facts: dict[str, object] = {
        "district": "District Alpha",
        "period": "2026-05",
        "schools": 120,
        "blocks": 8,
        "coverage_pct": 91.7,
        "health_score": 58,
        "data_quality_score": 87,
        "band_split": {"High": 12, "Medium": 30, "Low": 58},
        "top_block": {"block": "Block A1", "mean_risk": 62.4, "high_risk_schools": 4},
        "usage_delta": {
            "latest_week": "2026-W25",
            "prior_week": "2026-W24",
            "sessions_latest_mean": 22.3,
            "sessions_prior_mean": 35.1,
            "wow_pct": -36.4,
        },
        "decliners_count": 6,
        "top_decliner": {
            "school_id": "SCH_017",
            "block": "Block A1",
            "sessions_prior_mean": 28.0,
            "sessions_latest": 6.0,
            "drop_vs_recent_pct": -78.6,
        },
        "top_blocks": [{"block": "Block A1"}, {"block": "Block A3"}],
        "top_schools": [{"school_id": "SCH_017"}, {"school_id": "SCH_042"}],
        "data_quality": {"findings": [{"check": "missing_latest_week_usage"}], "coverage": {"schools_total": 120, "schools_reporting": 110}},
        "policy_observations_available": True,
        "risk_model_version": "1.0",
        "llm_provider": "mock",
        "fallback_used": False,
        "requested_provider": "mock",
        "top_n_actions": 5,
        "top_n_blocks": 5,
    }
    mock = MockLLM()
    for section in SUPPORTED_SECTIONS:
        text = mock.generate_section(section, sample_facts)
        print(f"\n--- {section} ---\n{text}")


if __name__ == "__main__":
    main()
