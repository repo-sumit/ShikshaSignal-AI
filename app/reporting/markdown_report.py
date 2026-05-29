"""Render `outputs/monthly_district_review.md`.

Pure-Python assembly: takes a facts dict + per-section narrative strings (from the LLM
provider) and returns a single markdown string. ALL numbers in the rendered document
come from the facts dict or from a small allowlist of deterministic constants — the
grounding test enforces this.

Sections (locked order):
    1. Title
    2. SYNTHETIC DATA disclaimer
    3. Executive summary
    4. District health score
    5. Target-vs-actual KPI table
    6. What changed since last period
    7. Top risky blocks
    8. Top risky schools
    9. Data quality warnings
   10. Policy-linked observations
   11. Root-cause hypotheses
   12. Recommended actions
   13. Draft stakeholder messages
   14. Review meeting questions
   15. Assumptions and limitations
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


# These section headings are referenced by the test suite via substring search;
# changing them is a deliberate, breaking change for any downstream tooling.
SECTION_HEADINGS: dict[str, str] = {
    "executive_summary": "## Executive Summary",
    "health_score": "## District Health Score",
    "kpi_table": "## KPI Snapshot (target vs actual)",
    "what_changed": "## What Changed Since Last Period",
    "top_blocks": "## Top Risky Blocks",
    "top_schools": "## Top Risky Schools",
    "data_quality_warnings": "## Data Quality Warnings",
    "policy_observations": "## Policy-Linked Observations",
    "root_cause_hypotheses": "## Root-Cause Hypotheses",
    "recommended_actions": "## Recommended Actions",
    "stakeholder_messages": "## Draft Stakeholder Messages",
    "meeting_questions": "## Review Meeting Questions",
    "assumptions": "## Assumptions and Limitations",
}


SYNTHETIC_DISCLAIMER: str = (
    "> ⚠ **SYNTHETIC DATA.** This memo was generated entirely from synthetic, "
    "public-safe data. No real student, teacher, school, or district information "
    "is used. Numbers are deterministic for a fixed random seed."
)


def _fmt_number(x, decimals: int = 1) -> str:
    """Format a number for the memo. None / NaN -> 'N/A'."""
    if x is None:
        return "N/A"
    try:
        if isinstance(x, float) and (x != x):  # NaN
            return "N/A"
    except Exception:
        pass
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if decimals == 0:
            return f"{x:.0f}"
        return f"{x:.{decimals}f}"
    return str(x)


def _render_kpi_table(facts: Mapping[str, object]) -> str:
    rows = facts.get("kpi_rows") or []
    if not rows:
        return "_No policy targets configured for this run._"
    lines = [
        "| KPI | Actual | Target | Status | Source |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for r in rows:
        actual = _fmt_number(r.get("actual"))
        target = _fmt_number(r.get("target"))
        lines.append(
            f"| {r.get('label')} | {actual} | {target} | {r.get('status')} | {r.get('source')} |"
        )
    return "\n".join(lines)


def _render_top_blocks(facts: Mapping[str, object]) -> str:
    rows = facts.get("top_blocks") or []
    if not rows:
        return "_No blocks in this district._"
    lines = [
        "| Rank | Block | Mean risk | Band | High-risk schools |",
        "| ---: | --- | ---: | --- | ---: |",
    ]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"| {i} | {r.get('block')} | {_fmt_number(r.get('mean_risk'))} | "
            f"{r.get('risk_band')} | {r.get('high_risk_schools')} |"
        )
    return "\n".join(lines)


def _render_top_schools(facts: Mapping[str, object]) -> str:
    rows = facts.get("top_schools") or []
    if not rows:
        return "_No schools in this district._"
    lines = [
        "| Rank | School | Block | Score | Band | Top drivers |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"| {i} | {r.get('school_id')} {r.get('school_name', '')} | {r.get('block')} | "
            f"{_fmt_number(r.get('risk_score'))} | {r.get('risk_band')} | {r.get('top_drivers')} |"
        )
    return "\n".join(lines)


def _render_dq_findings(facts: Mapping[str, object]) -> str:
    dq = facts.get("data_quality") or {}
    findings = dq.get("findings") or []
    if not findings:
        return "_No data-quality issues flagged._"
    lines = [
        "| Severity | Check | Count | Detail |",
        "| --- | --- | ---: | --- |",
    ]
    for f in findings:
        lines.append(
            f"| {f.get('severity')} | {f.get('check')} | {f.get('count')} | {f.get('detail')} |"
        )
    return "\n".join(lines)


def _render_policy_observations(facts: Mapping[str, object]) -> str:
    rows = facts.get("policy_observations") or []
    if not rows:
        return "_Policy context was unavailable for this run; observations omitted._"
    lines = [
        "| KPI | Status | Actual | Target | Policy mandate |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('label')} | {r.get('status')} | {_fmt_number(r.get('actual'))} | "
            f"{_fmt_number(r.get('target'))} | {r.get('source')} |"
        )
    return "\n".join(lines)


def _render_hypotheses(facts: Mapping[str, object]) -> str:
    rows = facts.get("root_cause_hypotheses") or []
    if not rows:
        return "_No high-risk schools triggered hypothesis generation._"
    bullets = []
    for r in rows:
        bullets.append(
            f"- **Hypothesis ({r.get('school_id')} in {r.get('block')}):** "
            f"{r.get('hypothesis')} _Evidence: {r.get('evidence')}_"
        )
    return "\n".join(bullets)


def _render_action_preview(facts: Mapping[str, object]) -> str:
    rows = facts.get("action_preview") or []
    if not rows:
        return "_No proposed actions for this district._"
    lines = [
        "| Action | School | Block | Priority | Owner | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('action_id')} | {r.get('school_id')} | {r.get('block')} | "
            f"{r.get('priority')} | {r.get('suggested_owner')} | {r.get('status')} |"
        )
    return "\n".join(lines)


def render_review_markdown(
    facts: Mapping[str, object],
    narratives: Mapping[str, str],
) -> str:
    """Assemble the full review memo from facts + LLM-rendered prose."""
    district = facts.get("district", "Unknown")
    period = facts.get("period", "Unknown")
    state = facts.get("state", "")
    title = f"# Monthly District Review — {district}, {state} | Period {period}"

    sections: list[str] = [
        title,
        SYNTHETIC_DISCLAIMER,
        SECTION_HEADINGS["executive_summary"],
        narratives.get("executive_summary", ""),
        SECTION_HEADINGS["health_score"],
        f"**Health score: {facts.get('health_score', 'N/A')}/100** "
        f"(weighted blend of target attainment, data quality, and risk band mix; "
        f"see `outputs/audit_log.json` for the formula version).",
        SECTION_HEADINGS["kpi_table"],
        _render_kpi_table(facts),
        SECTION_HEADINGS["what_changed"],
        narratives.get("what_changed", ""),
        SECTION_HEADINGS["top_blocks"],
        narratives.get("top_blocks_narrative", ""),
        "",
        _render_top_blocks(facts),
        SECTION_HEADINGS["top_schools"],
        narratives.get("top_schools_narrative", ""),
        "",
        _render_top_schools(facts),
        SECTION_HEADINGS["data_quality_warnings"],
        narratives.get("data_quality_warnings", ""),
        "",
        _render_dq_findings(facts),
        SECTION_HEADINGS["policy_observations"],
        narratives.get("policy_observations", ""),
        "",
        _render_policy_observations(facts),
        SECTION_HEADINGS["root_cause_hypotheses"],
        narratives.get("root_cause_hypotheses", ""),
        "",
        _render_hypotheses(facts),
        SECTION_HEADINGS["recommended_actions"],
        narratives.get("recommended_actions", ""),
        "",
        _render_action_preview(facts),
        SECTION_HEADINGS["stakeholder_messages"],
        "### Message — Block Resource Coordinator (top-risk block)\n",
        narratives.get("stakeholder_message_brc", ""),
        "\n### Message — District Education Officer\n",
        narratives.get("stakeholder_message_dleo", ""),
        SECTION_HEADINGS["meeting_questions"],
        narratives.get("meeting_questions", ""),
        SECTION_HEADINGS["assumptions"],
        narratives.get("assumptions", ""),
    ]
    # Trim trailing blank lines, normalise paragraph breaks.
    body = "\n\n".join(s.strip() for s in sections if s is not None).rstrip() + "\n"
    return body


def write_review_markdown(markdown: str, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path
