"""ShikshaSignal AI — Monthly District Review compiler.

Single terminal-first entrypoint that wires the deterministic analytics core (KPIs,
risk, data quality, rankings) with a Jinja-templated MockLLM narrator and writes
four artefacts:

    outputs/monthly_district_review.md
    outputs/action_tracker.csv
    outputs/audit_log.json
    outputs/review_facts.json

Design rules (validated in tests):
  * The LLM never computes numbers — it only narrates pre-computed facts.
  * Every number in the memo must trace to `review_facts.json` (grounding test).
  * Root causes are labelled hypotheses; actions start `status=proposed`.
  * Outputs are deterministic for a fixed seed + same args.

Run:
    python -m app.review --district "District Alpha" --period 2026-05
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import (
    CSV_FILES,
    DATA_DIR,
    FOCUS_DISTRICT,
    OUTPUTS_DIR,
    RISK_MODEL_VERSION,
    RISK_WEIGHTS,
    STATE_NAME,
    SYNTHETIC_DIR,
)
from app.eval.grounding import check_grounding
from app.llm.base import SUPPORTED_SECTIONS, BaseLLMProvider, GenerationResult
from app.llm.factory import ProviderResolution, get_provider
from app.llm.mock_llm import MockLLM
from app.reporting.action_tracker import (
    ACTION_COLUMNS,
    build_action_tracker,
    write_action_tracker,
)
from app.reporting.audit_log import build_audit_log, write_audit_log
from app.reporting.markdown_report import (
    render_review_markdown,
    write_review_markdown,
)
from app.tools.csv_loader import Tables, load_all
from app.tools.data_quality import DataQualityReport, assess_quality
from app.tools.kpi_calculator import (
    compute_school_kpis,
    district_summary,
    load_policy_targets,
)
from app.tools.rankings import build_school_ranking, whats_changed
from app.tools.risk_score import band_split, compute_block_risk, compute_school_risk

logger = logging.getLogger(__name__)

POLICY_MAP_PATH: Path = DATA_DIR / "policy_map.yaml"


# -----------------------------------------------------------------------------
# Output bundle
# -----------------------------------------------------------------------------


@dataclass
class ReviewArtifacts:
    """File paths written for one review run; surfaced for callers/tests."""

    monthly_district_review_md: Path
    action_tracker_csv: Path
    audit_log_json: Path
    review_facts_json: Path

    def as_list(self) -> list[Path]:
        return [
            self.monthly_district_review_md,
            self.action_tracker_csv,
            self.audit_log_json,
            self.review_facts_json,
        ]


# -----------------------------------------------------------------------------
# Number coercion helpers
# -----------------------------------------------------------------------------


def _to_jsonable(x: Any) -> Any:
    """Convert numpy / pandas scalars into plain Python types for JSON."""
    if x is None:
        return None
    if isinstance(x, (str, bool, int)):
        return x
    if isinstance(x, float):
        return None if math.isnan(x) else x
    if isinstance(x, dict):
        return {str(k): _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]
    # numpy / pandas scalar
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass
    try:
        return float(x) if not isinstance(x, bool) else bool(x)
    except Exception:
        return str(x)


def _round_or_none(x: Any, decimals: int = 1) -> Any:
    if x is None:
        return None
    try:
        if isinstance(x, float) and math.isnan(x):
            return None
        return round(float(x), decimals)
    except Exception:
        return x


# -----------------------------------------------------------------------------
# Fact assembly
# -----------------------------------------------------------------------------


def _health_score(d_summary: dict, dq: DataQualityReport, bsplit: dict) -> int:
    """Deterministic, transparent 0-100 health score.

    Blend three signals:
      * KPI attainment: share of KPI rows whose status is "on track".
      * Data quality score (already 0-100, capped).
      * Risk mix: penalty proportional to share of High-band schools.
    """
    kpis = d_summary.get("kpis") or []
    if kpis:
        on_track = sum(1 for k in kpis if k.get("status") == "on track")
        attainment = (on_track / len(kpis)) * 100
    else:
        attainment = 50.0
    dq_score = float(dq.data_quality_score)
    high_pct = float(bsplit.get("High", 0.0)) * 100  # band_split returns fractions 0..1
    score = 0.5 * attainment + 0.3 * dq_score + 0.2 * (100.0 - high_pct)
    return int(max(0, min(100, round(score))))


def _band_split_percent(bsplit: dict) -> dict[str, int]:
    """band_split returns fractions 0..1; the memo speaks in whole percentages."""
    return {b: int(round(100 * float(bsplit.get(b, 0.0)))) for b in ("Low", "Medium", "High")}


def _top_block_rows(block_risk: pd.DataFrame, district: str, n: int) -> list[dict]:
    if block_risk is None or block_risk.empty:
        return []
    scoped = block_risk[block_risk["district"] == district].head(n).copy()
    return [
        {
            "rank": i,
            "block": r["block"],
            "mean_risk": _round_or_none(r["mean_risk"]),
            "risk_band": r["risk_band"],
            "high_risk_schools": int(r["high_risk_schools"]),
        }
        for i, (_, r) in enumerate(scoped.iterrows(), start=1)
    ]


def _top_school_rows(school_ranking: pd.DataFrame, district: str, n: int) -> list[dict]:
    if school_ranking is None or school_ranking.empty:
        return []
    scoped = school_ranking[school_ranking["district"] == district].head(n).copy()
    rows: list[dict] = []
    for i, (_, r) in enumerate(scoped.iterrows(), start=1):
        rows.append(
            {
                "rank": i,
                "school_id": r["school_id"],
                "school_name": r.get("school_name"),
                "block": r["block"],
                "risk_score": _round_or_none(r["risk_score"]),
                "risk_band": r["risk_band"],
                "top_drivers": r["top_drivers"],
                "learning_outcome": _round_or_none(r["learning_outcome"]),
                "digital_usage": _round_or_none(r["digital_usage"]),
                "teacher_training": _round_or_none(r["teacher_training"]),
                "infrastructure": _round_or_none(r["infrastructure"]),
                "field_issue": _round_or_none(r["field_issue"]),
                "data_availability": _round_or_none(r["data_availability"]),
                "data_quality": _round_or_none(r["data_quality"]),
            }
        )
    return rows


def _hypotheses_from_top_schools(top_schools: list[dict]) -> list[dict]:
    """Rule-based root-cause hypothesis per top-risky school.

    Wording is templated from the primary driver. No LLM freedom here either —
    keeps causal claims auditable and consistent across runs.
    """
    templates = {
        "learning_outcome": "Weak FLN improvement and below-target proficiency suggest gaps in foundational pedagogy.",
        "digital_usage": "Low DIKSHA sessions point to either connectivity/device issues or teachers not yet integrating DIKSHA into routine practice.",
        "teacher_training": "Below-target NISHTHA/FLN completion suggests teachers are stuck mid-module or unstarted.",
        "infrastructure": "Weak infrastructure (low score, missing internet or devices) likely caps both adoption and outcomes.",
        "field_issue": "Open Critical/High field issues are likely depressing daily classroom function.",
        "data_availability": "Schools with patchy DIKSHA reporting may be reporting through other channels, masking real status.",
        "data_quality": "Data-quality flags (invalid completion, duplicates) make this school's metrics unreliable.",
    }
    rows: list[dict] = []
    for s in top_schools:
        primary = (s.get("top_drivers") or "").split(", ")[0]
        hypothesis = templates.get(primary, "No specific hypothesis; review at the next field visit.")
        evidence_bits: list[str] = []
        for k in ("learning_outcome", "digital_usage", "teacher_training", "infrastructure",
                  "field_issue", "data_availability", "data_quality"):
            v = s.get(k)
            if v is not None:
                evidence_bits.append(f"{k}={v}")
        rows.append(
            {
                "school_id": s["school_id"],
                "block": s["block"],
                "hypothesis": hypothesis,
                "evidence": "; ".join(evidence_bits),
            }
        )
    return rows


def _action_preview_rows(action_tracker: pd.DataFrame, n: int) -> list[dict]:
    if action_tracker is None or action_tracker.empty:
        return []
    cols = ["action_id", "school_id", "block", "priority", "suggested_owner", "status"]
    return [
        {c: row.get(c) for c in cols}
        for _, row in action_tracker.head(n).iterrows()
    ]


def _top_decliner_row(whats_changed_df: pd.DataFrame) -> dict | None:
    if whats_changed_df is None or whats_changed_df.empty:
        return None
    r = whats_changed_df.iloc[0]
    return {
        "school_id": r["school_id"],
        "block": r["block"],
        "sessions_prior_mean": _round_or_none(r["sessions_prior_mean"]),
        "sessions_latest": _round_or_none(r["sessions_latest"]),
        "drop_vs_recent_pct": _round_or_none(r["drop_vs_recent_pct"]),
    }


def build_review_facts(
    tables: Tables,
    district: str,
    period: str,
    top_n_blocks: int,
    top_n_schools: int,
    top_n_actions: int,
    provider: ProviderResolution,
) -> dict:
    """Compile the JSON facts that the memo + actions + audit log all share."""
    d_summary = district_summary(tables, district=district)

    school_risk = compute_school_risk(tables)
    block_risk = compute_block_risk(school_risk)
    bsplit = band_split(school_risk[school_risk["district"] == district])

    school_ranking = build_school_ranking(tables)
    scoped_ranking = school_ranking[school_ranking["district"] == district]
    decliners = whats_changed(scoped_ranking, top=10)

    dq: DataQualityReport = assess_quality(tables)

    top_blocks = _top_block_rows(block_risk, district, top_n_blocks)
    top_schools = _top_school_rows(school_ranking, district, top_n_schools)

    actions = build_action_tracker(school_ranking, district=district, top_n=top_n_actions)
    action_preview = _action_preview_rows(actions, top_n_actions)
    hypotheses = _hypotheses_from_top_schools(top_schools)

    policy_obs_rows = [
        {
            "label": k.get("label"),
            "kpi": k.get("kpi"),
            "actual": _round_or_none(k.get("actual")),
            "target": k.get("target"),
            "status": k.get("status"),
            "source": k.get("source"),
        }
        for k in (d_summary.get("kpis") or [])
        if k.get("source")
    ]

    health = _health_score(d_summary, dq, bsplit)

    schools_not_reporting = max(
        0,
        int(dq.coverage.get("schools_total", 0)) - int(dq.coverage.get("schools_reporting", 0)),
    )

    facts: dict[str, Any] = {
        "district": district,
        "state": STATE_NAME,
        "period": period,
        "schools": int(d_summary["schools"]),
        "blocks": int(d_summary["blocks"]),
        "coverage_pct": _round_or_none(d_summary["coverage_pct"]),
        "schools_not_reporting": schools_not_reporting,
        "health_score": health,
        "data_quality_score": int(dq.data_quality_score),
        "band_split": _band_split_percent(bsplit),
        "top_block": top_blocks[0] if top_blocks else None,
        "usage_delta": _to_jsonable(d_summary["usage_delta"]),
        "decliners_count": int(len(decliners)),
        "top_decliner": _top_decliner_row(decliners),
        "top_blocks": top_blocks,
        "top_schools": top_schools,
        "data_quality": {
            "coverage": _to_jsonable(dq.coverage),
            "findings": _to_jsonable(dq.findings),
            "findings_count": len(dq.findings),
            "weeks_expected": int(dq.weeks_expected),
            "latest_week": dq.latest_week,
        },
        "kpi_rows": _to_jsonable(d_summary.get("kpis") or []),
        "policy_observations": policy_obs_rows,
        "policy_observations_available": bool(policy_obs_rows),
        "root_cause_hypotheses": hypotheses,
        "action_preview": action_preview,
        "risk_model_version": RISK_MODEL_VERSION,
        "risk_weights_percent": {k: int(round(v * 100)) for k, v in RISK_WEIGHTS.items()},
        "llm_provider": provider.name,
        "requested_provider": provider.requested,
        "fallback_used": provider.fallback_used,
        "top_n_actions": top_n_actions,
        "top_n_blocks": top_n_blocks,
        "top_n_schools": top_n_schools,
        # An explicit reminder that 100 is the risk-score scale max — used in
        # phrases like "78/100" inside evidence strings.
        "risk_score_scale_max": 100,
        # The two cut-points of the risk bands so grounding sees these constants.
        "band_thresholds": {"low_to_medium": 40, "medium_to_high": 70},
    }
    facts["_action_tracker_df"] = actions   # in-memory only; stripped before JSON write
    return facts


# -----------------------------------------------------------------------------
# Orchestrator
# -----------------------------------------------------------------------------


@dataclass
class NarrationReport:
    """Per-section telemetry returned alongside the assembled narratives.

    Keeps the orchestrator's fallback bookkeeping in one place so the audit log can
    record exactly which sections used which provider, and why.
    """

    narratives: dict[str, str]
    section_metadata: dict[str, dict]
    grounding_failures: dict[str, list[str]]
    total_latency_ms: float
    any_section_fell_back: bool


def _narrate_all(
    provider: BaseLLMProvider,
    facts: dict,
    *,
    strict_grounding: bool = False,
    mock_for_fallback: BaseLLMProvider | None = None,
) -> NarrationReport:
    """Walk every SUPPORTED_SECTION and ask the provider to narrate it.

    For every section we:
      1. Call the provider to get a `GenerationResult`.
      2. If the call errored or returned empty text, fall back to MockLLM.
      3. Otherwise check that every numeric token in the text is grounded in `facts`.
         If grounding fails, fall back to MockLLM and record the offending tokens.

    With `strict_grounding=True`, *any* section grounding failure triggers a full-memo
    fallback at the end (handled by the caller via `any_section_fell_back`).
    """
    mock = mock_for_fallback or MockLLM()

    narratives: dict[str, str] = {}
    section_meta: dict[str, dict] = {}
    grounding_failures: dict[str, list[str]] = {}
    total_latency = 0.0
    any_fell_back = False

    for section in SUPPORTED_SECTIONS:
        primary: GenerationResult = provider.generate(section, facts)
        total_latency += primary.latency_ms
        used = primary

        # --- 1. Call-time failure path ---
        if primary.error or not primary.text.strip():
            mock_result = mock.generate(section, facts)
            mock_result.fallback_used = True
            mock_result.fallback_reason = primary.error or "empty_provider_output"
            used = mock_result
            any_fell_back = True
        else:
            # --- 2. Grounding check on the prose ---
            ungrounded = check_grounding(primary.text, facts)
            if ungrounded:
                grounding_failures[section] = ungrounded
                mock_result = mock.generate(section, facts)
                mock_result.fallback_used = True
                mock_result.fallback_reason = (
                    f"grounding_failed: {len(ungrounded)} ungrounded token(s)"
                )
                used = mock_result
                any_fell_back = True

        narratives[section] = used.text
        section_meta[section] = {
            "provider": used.provider_name,
            "model": used.model,
            "latency_ms": round(used.latency_ms, 2),
            "fallback_used": used.fallback_used,
            "fallback_reason": used.fallback_reason,
            # Always record the primary attempt's error too, even if a fallback recovered:
            "primary_error": primary.error,
        }

    return NarrationReport(
        narratives=narratives,
        section_metadata=section_meta,
        grounding_failures=grounding_failures,
        total_latency_ms=total_latency,
        any_section_fell_back=any_fell_back,
    )


def _write_facts_json(facts: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialisable = {k: v for k, v in facts.items() if not k.startswith("_")}
    path.write_text(
        json.dumps(_to_jsonable(serialisable), indent=2, sort_keys=False),
        encoding="utf-8",
    )
    return path


def run_review(
    district: str = FOCUS_DISTRICT,
    period: str = "2026-05",
    top_n_schools: int = 10,
    top_n_blocks: int = 5,
    top_n_actions: int = 10,
    llm_provider: str = "mock",
    strict_grounding: bool = False,
    outputs_dir: Path = OUTPUTS_DIR,
    synthetic_dir: Path = SYNTHETIC_DIR,
    timestamp: str | None = None,
) -> ReviewArtifacts:
    """Top-level orchestrator. Returns the four output paths.

    `strict_grounding=True` means: if ANY section fails the grounding check, the
    entire memo is re-rendered with MockLLM. Default (False) is per-section
    fallback, which is usually friendlier.
    """
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    tables: Tables = load_all(Path(synthetic_dir))
    resolution = get_provider(llm_provider)

    facts = build_review_facts(
        tables=tables,
        district=district,
        period=period,
        top_n_blocks=top_n_blocks,
        top_n_schools=top_n_schools,
        top_n_actions=top_n_actions,
        provider=resolution,
    )

    mock_fallback = MockLLM() if resolution.name != "mock" else resolution.provider
    report = _narrate_all(
        resolution.provider,
        facts,
        strict_grounding=strict_grounding,
        mock_for_fallback=mock_fallback,
    )

    # In strict mode, if anything fell back at the section level, re-render the
    # whole memo from MockLLM so the document is uniform.
    if strict_grounding and report.any_section_fell_back:
        report = _narrate_all(
            mock_fallback,
            facts,
            strict_grounding=False,
            mock_for_fallback=mock_fallback,
        )

    narratives = report.narratives
    markdown = render_review_markdown(facts, narratives)

    md_path = write_review_markdown(markdown, outputs_dir / "monthly_district_review.md")
    actions_df: pd.DataFrame = facts.pop("_action_tracker_df")
    actions_path = write_action_tracker(actions_df, outputs_dir / "action_tracker.csv")
    facts_path = _write_facts_json(facts, outputs_dir / "review_facts.json")

    command_args = {
        "district": district,
        "period": period,
        "top_n_schools": top_n_schools,
        "top_n_blocks": top_n_blocks,
        "top_n_actions": top_n_actions,
        "llm_provider": llm_provider,
        "strict_grounding": bool(strict_grounding),
    }
    data_files_used = [Path(synthetic_dir) / fname for fname in CSV_FILES.values()]
    policy_docs_used = [POLICY_MAP_PATH] if POLICY_MAP_PATH.exists() else []

    # Compose the fallback flag + reason from BOTH stages: factory-level
    # (construction) and orchestration-level (any per-section fall-back).
    section_fallback = report.any_section_fell_back
    final_fallback_used = bool(resolution.fallback_used or section_fallback)
    final_fallback_reason: str | None
    if resolution.fallback_used and section_fallback:
        final_fallback_reason = (
            f"{resolution.fallback_reason}; section_fallbacks={sum(1 for m in report.section_metadata.values() if m['fallback_used'])}"
        )
    elif resolution.fallback_used:
        final_fallback_reason = resolution.fallback_reason
    elif section_fallback:
        n_fb = sum(1 for m in report.section_metadata.values() if m["fallback_used"])
        final_fallback_reason = f"section_fallbacks={n_fb}"
    else:
        final_fallback_reason = None

    # The "actual" provider name for the AUDIT_LOG is the one that produced the
    # majority of narrations. If anything fell back at construction time we never
    # called the real provider at all, so this is just resolution.name.
    actual_provider_name = resolution.name

    audit = build_audit_log(
        command_args=command_args,
        data_files_used=data_files_used,
        policy_docs_used=policy_docs_used,
        llm_provider=actual_provider_name,
        requested_llm_provider=resolution.requested,
        fallback_used=final_fallback_used,
        output_files=[md_path, actions_path, facts_path],
        risk_formula_version=RISK_MODEL_VERSION,
        risk_weights=RISK_WEIGHTS,
        timestamp=timestamp,
        model_name=resolution.model,
        fallback_reason=final_fallback_reason,
        grounding_failures=report.grounding_failures,
        provider_latency_ms=report.total_latency_ms,
        section_metadata=report.section_metadata,
        extra={
            "district_schools": int(facts.get("schools", 0)),
            "district_blocks": int(facts.get("blocks", 0)),
            "data_quality_score": int(facts.get("data_quality_score", 0)),
            "health_score": int(facts.get("health_score", 0)),
            "band_split_percent": facts.get("band_split", {}),
            "strict_grounding": bool(strict_grounding),
        },
    )
    audit_path = write_audit_log(audit, outputs_dir / "audit_log.json")
    # Update audit's output_files to include itself.
    audit_payload = audit.to_dict()
    audit_payload["output_files"] = [str(p) for p in [md_path, actions_path, facts_path, audit_path]]
    audit_path.write_text(json.dumps(audit_payload, indent=2, sort_keys=False), encoding="utf-8")

    return ReviewArtifacts(
        monthly_district_review_md=md_path,
        action_tracker_csv=actions_path,
        audit_log_json=audit_path,
        review_facts_json=facts_path,
    )


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile the monthly district review.")
    parser.add_argument("--district", type=str, default=FOCUS_DISTRICT)
    parser.add_argument("--period", type=str, default="2026-05")
    parser.add_argument("--top-n-schools", type=int, default=10)
    parser.add_argument("--top-n-blocks", type=int, default=5)
    parser.add_argument("--top-n-actions", type=int, default=10)
    parser.add_argument(
        "--llm-provider",
        type=str,
        default="mock",
        choices=["mock", "gemini", "groq", "ollama"],
        help="LLM backend. 'mock' (default) is offline; others fall back to mock if unavailable.",
    )
    parser.add_argument(
        "--strict-grounding",
        action="store_true",
        help="If any section fails the grounding check, re-render the entire memo with MockLLM.",
    )
    parser.add_argument("--outputs-dir", type=Path, default=OUTPUTS_DIR)
    parser.add_argument("--synthetic-dir", type=Path, default=SYNTHETIC_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    args = _parse_args(argv)
    arts = run_review(
        district=args.district,
        period=args.period,
        top_n_schools=args.top_n_schools,
        top_n_blocks=args.top_n_blocks,
        top_n_actions=args.top_n_actions,
        llm_provider=args.llm_provider,
        strict_grounding=args.strict_grounding,
        outputs_dir=args.outputs_dir,
        synthetic_dir=args.synthetic_dir,
    )
    print("\n=== Monthly District Review compiled ===")
    print(f"  {arts.monthly_district_review_md}")
    print(f"  {arts.action_tracker_csv}")
    print(f"  {arts.audit_log_json}")
    print(f"  {arts.review_facts_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
