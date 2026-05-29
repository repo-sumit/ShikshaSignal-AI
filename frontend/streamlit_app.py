"""ShikshaSignal AI — Streamlit Review Viewer (Milestone 5).

A thin local UI on top of the existing CLI compiler. The Streamlit app does
**not** duplicate any review logic — every "Generate Review" click invokes
`app.review.run_review(...)`, the same function the CLI calls, and then reads
the four output artifacts through `app.services.artifact_reader`.

Run:
    streamlit run frontend/streamlit_app.py

All inputs are SYNTHETIC. The viewer is local-first; no data leaves the host
unless the user opted into a real LLM provider (gemini / groq), in which case
only the deterministic `review_facts` JSON is sent to the provider's API.
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


# --------------------------------------------------------------------------------------
# Path bootstrap — let the user run `streamlit run frontend/streamlit_app.py`
# from the repo root without installing the package.
# --------------------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.config import FOCUS_DISTRICT, OUTPUTS_DIR, SYNTHETIC_DIR  # noqa: E402
from app.review import run_review  # noqa: E402
from app.services.artifact_reader import (  # noqa: E402
    all_outputs_present,
    list_available_districts,
    list_available_periods,
    output_paths,
    read_csv,
    read_json,
    read_markdown,
    synthetic_data_present,
)


# --------------------------------------------------------------------------------------
# Page config + light styling — st.metric / st.dataframe / st.download_button only.
# --------------------------------------------------------------------------------------
st.set_page_config(
    page_title="ShikshaSignal AI — Monthly Review",
    page_icon="📊",
    layout="wide",
)


# --------------------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------------------
st.title("ShikshaSignal AI")
st.subheader("Monthly District Review Agent — Local Viewer")
st.caption("Milestone 5 · Streamlit Review Viewer · local demo · synthetic data only")
st.warning(
    "⚠ **SYNTHETIC DATA.** All inputs are synthetic and public-safe — no real student, "
    "teacher, school, or district information is processed. LLMs only narrate verified "
    "deterministic facts; every memo number is grounded in `review_facts.json`. Proposed "
    "actions are never communicated externally without human approval."
)


# --------------------------------------------------------------------------------------
# Sidebar controls
# --------------------------------------------------------------------------------------
with st.sidebar:
    st.header("Controls")

    if not synthetic_data_present():
        st.error(
            "Synthetic data not found in `data/synthetic/`.\n\n"
            "Run this once before using the viewer:\n\n"
            "```bash\npython scripts/generate_synthetic_data.py --seed 42\n```"
        )

    districts = list_available_districts() or [FOCUS_DISTRICT]
    default_district_idx = districts.index(FOCUS_DISTRICT) if FOCUS_DISTRICT in districts else 0
    district = st.selectbox("District", districts, index=default_district_idx)

    periods = list_available_periods()
    period = st.selectbox("Period (YYYY-MM)", periods, index=len(periods) - 1)

    llm_provider = st.selectbox(
        "LLM provider",
        ["mock", "gemini", "groq", "ollama"],
        index=0,
        help="`mock` runs fully offline. Others fall back to mock automatically if "
             "credentials are missing or the call fails.",
    )

    top_n_schools = st.slider("Top N risky schools", min_value=3, max_value=25, value=10)
    top_n_blocks = st.slider("Top N risky blocks", min_value=1, max_value=10, value=5)
    strict_grounding = st.toggle(
        "Strict grounding",
        value=False,
        help="If any LLM section fails the grounding check, re-render the entire memo "
             "with MockLLM.",
    )

    generate_clicked = st.button(
        "Generate Review",
        type="primary",
        use_container_width=True,
        disabled=not synthetic_data_present(),
    )

    debug_mode = st.toggle("Debug mode (show raw errors)", value=False)


# --------------------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------------------
if "last_run" not in st.session_state:
    st.session_state["last_run"] = None  # dict: paths + summary
if "last_error" not in st.session_state:
    st.session_state["last_error"] = None


def _run_review_safely() -> None:
    """Invoke the existing CLI orchestrator and store paths in session state."""
    st.session_state["last_error"] = None
    try:
        arts = run_review(
            district=district,
            period=period,
            top_n_schools=top_n_schools,
            top_n_blocks=top_n_blocks,
            llm_provider=llm_provider,
            strict_grounding=strict_grounding,
        )
    except FileNotFoundError as e:
        st.session_state["last_error"] = (
            "Synthetic data is missing. Run "
            "`python scripts/generate_synthetic_data.py --seed 42` and try again.\n\n"
            f"_Details: {e}_"
        )
        return
    except Exception as e:
        st.session_state["last_error"] = f"Review generation failed: {e}"
        if debug_mode:
            st.session_state["last_error"] += "\n\n```\n" + traceback.format_exc() + "\n```"
        return

    st.session_state["last_run"] = {
        "paths": {
            "review_md": str(arts.monthly_district_review_md),
            "action_tracker_csv": str(arts.action_tracker_csv),
            "audit_log_json": str(arts.audit_log_json),
            "review_facts_json": str(arts.review_facts_json),
        },
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {
            "district": district,
            "period": period,
            "llm_provider": llm_provider,
            "top_n_schools": top_n_schools,
            "top_n_blocks": top_n_blocks,
            "strict_grounding": strict_grounding,
        },
    }


if generate_clicked:
    with st.spinner("Compiling review (deterministic core → LLM narration → grounding check)…"):
        _run_review_safely()


# --------------------------------------------------------------------------------------
# Surface any error from the last run
# --------------------------------------------------------------------------------------
if st.session_state["last_error"]:
    st.error(st.session_state["last_error"])


# --------------------------------------------------------------------------------------
# Load artifacts (use the last-run paths if available, else default outputs/ dir)
# --------------------------------------------------------------------------------------
if st.session_state["last_run"]:
    paths = {k: Path(v) for k, v in st.session_state["last_run"]["paths"].items()}
else:
    paths = output_paths(OUTPUTS_DIR)

artifacts_ready = all_outputs_present(OUTPUTS_DIR) or all(
    p.exists() and p.stat().st_size > 0 for p in paths.values() if p.suffix in {".md", ".csv", ".json"}
)

facts = read_json(paths["review_facts_json"])
audit = read_json(paths["audit_log_json"])
memo_md = read_markdown(paths["review_md"])
actions_df = read_csv(paths["action_tracker_csv"])
risk_ranking_df = read_csv(output_paths(OUTPUTS_DIR)["risk_ranking_csv"])  # produced by app/tools/rankings.py


# --------------------------------------------------------------------------------------
# Executive overview — KPI cards driven by review_facts.json
# --------------------------------------------------------------------------------------
st.divider()
st.header("Executive Overview")

if not artifacts_ready and not facts:
    st.info(
        "No review has been generated yet. Pick a district + period in the sidebar and "
        "click **Generate Review**."
    )
else:
    band_split = facts.get("band_split") or {}
    top_block = facts.get("top_block") or {}
    fallback = bool(audit.get("fallback_used"))
    fb_reason = audit.get("fallback_reason")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Health score", f"{facts.get('health_score', '—')}/100")
    col2.metric("Data quality", f"{facts.get('data_quality_score', '—')}/100")
    col3.metric("Schools covered", facts.get("schools", "—"))
    col4.metric("High-risk schools", f"{band_split.get('High', 0)}%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric(
        "Top risky block",
        top_block.get("block") or "—",
        f"mean risk {top_block.get('mean_risk', '—')}" if top_block else None,
    )
    col6.metric(
        "Reporting coverage",
        f"{facts.get('coverage_pct', '—')}%",
    )
    col7.metric(
        "LLM provider",
        audit.get("llm_provider") or audit.get("actual_llm_provider") or "—",
        delta=("fallback" if fallback else None),
        delta_color="inverse" if fallback else "off",
    )
    col8.metric(
        "Model",
        audit.get("model_name") or "—",
    )

    if fallback:
        st.info(
            f"**LLM fallback used.** Reason: `{fb_reason or 'n/a'}`. Memo numbers are still "
            "fully grounded — the deterministic core produced them; the prose either came "
            "from MockLLM or from your requested provider with a grounded-only re-render."
        )


# --------------------------------------------------------------------------------------
# Tabs — Review Memo · Risk Ranking · Action Tracker · Audit Log · Review Facts
# --------------------------------------------------------------------------------------
st.divider()
tab_memo, tab_risk, tab_actions, tab_audit, tab_facts = st.tabs(
    ["📝 Review Memo", "📊 Risk Ranking", "✅ Action Tracker", "🔍 Audit Log", "🧾 Review Facts"]
)


# ---- Review Memo --------------------------------------------------------------
with tab_memo:
    st.subheader("Monthly District Review Memo")
    if not memo_md:
        st.info("No memo yet. Generate a review from the sidebar.")
    else:
        st.markdown(memo_md)
        st.download_button(
            "Download monthly_district_review.md",
            data=memo_md.encode("utf-8"),
            file_name="monthly_district_review.md",
            mime="text/markdown",
            use_container_width=True,
        )


# ---- Risk Ranking ------------------------------------------------------------
with tab_risk:
    st.subheader("Risk Ranking (deterministic — `outputs/risk_ranking.csv`)")
    if risk_ranking_df.empty:
        st.info(
            "`outputs/risk_ranking.csv` not found. Build it with "
            "`python -m app.tools.rankings`."
        )
    else:
        with st.expander("Filters", expanded=True):
            f1, f2 = st.columns(2)
            band_options = ["All"] + sorted(risk_ranking_df["risk_band"].dropna().unique().tolist())
            band_filter = f1.selectbox("Risk band", band_options, index=0)
            block_options = ["All"] + sorted(risk_ranking_df["block"].dropna().unique().tolist())
            block_filter = f2.selectbox("Block", block_options, index=0)

        view = risk_ranking_df
        if band_filter != "All":
            view = view[view["risk_band"] == band_filter]
        if block_filter != "All":
            view = view[view["block"] == block_filter]
        st.dataframe(view, use_container_width=True, hide_index=True)

        st.download_button(
            "Download risk_ranking.csv",
            data=risk_ranking_df.to_csv(index=False).encode("utf-8"),
            file_name="risk_ranking.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ---- Action Tracker ----------------------------------------------------------
with tab_actions:
    st.subheader("Proposed Actions (`outputs/action_tracker.csv`)")
    st.caption(
        "Every action starts as `proposed`. Human approval is required before "
        "communicating any action externally."
    )
    if actions_df.empty:
        st.info("No actions yet. Generate a review from the sidebar.")
    else:
        st.dataframe(actions_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download action_tracker.csv",
            data=actions_df.to_csv(index=False).encode("utf-8"),
            file_name="action_tracker.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ---- Audit Log ---------------------------------------------------------------
with tab_audit:
    st.subheader("Audit Log (`outputs/audit_log.json`)")
    if not audit:
        st.info("No audit log yet. Generate a review from the sidebar.")
    else:
        summary_rows = [
            ("run_id", audit.get("run_id")),
            ("timestamp", audit.get("timestamp")),
            ("requested_llm_provider", audit.get("requested_llm_provider")),
            ("actual_llm_provider", audit.get("actual_llm_provider") or audit.get("llm_provider")),
            ("model_name", audit.get("model_name")),
            ("fallback_used", audit.get("fallback_used")),
            ("fallback_reason", audit.get("fallback_reason")),
            ("risk_formula_version", audit.get("risk_formula_version")),
            ("provider_latency_ms", audit.get("provider_latency_ms")),
        ]
        st.dataframe(
            pd.DataFrame(summary_rows, columns=["field", "value"]),
            use_container_width=True,
            hide_index=True,
        )

        grounding = audit.get("grounding_failures") or {}
        if grounding:
            st.warning(
                f"Grounding flagged ungrounded tokens in {len(grounding)} section(s). "
                "Affected sections were re-rendered with MockLLM."
            )
            with st.expander("Per-section ungrounded tokens", expanded=False):
                st.json(grounding)

        with st.expander("Data files used", expanded=False):
            st.write(audit.get("data_files_used") or [])
        with st.expander("Policy docs used", expanded=False):
            st.write(audit.get("policy_docs_used") or [])
        with st.expander("Output files", expanded=False):
            st.write(audit.get("output_files") or [])
        with st.expander("Section metadata (per LLM call)", expanded=False):
            st.json(audit.get("section_metadata") or {})

        st.download_button(
            "Download audit_log.json",
            data=json.dumps(audit, indent=2).encode("utf-8"),
            file_name="audit_log.json",
            mime="application/json",
            use_container_width=True,
        )


# ---- Review Facts ------------------------------------------------------------
with tab_facts:
    st.subheader("Review Facts (`outputs/review_facts.json`)")
    st.caption(
        "Every numeric token in the memo must trace to a value in this file. This is the "
        "grounding contract."
    )
    if not facts:
        st.info("No facts yet. Generate a review from the sidebar.")
    else:
        top_keys = [
            "district", "period", "schools", "blocks", "coverage_pct",
            "health_score", "data_quality_score", "schools_not_reporting",
            "band_split", "top_block", "usage_delta", "decliners_count",
            "risk_model_version",
        ]
        summary = pd.DataFrame(
            [(k, facts.get(k)) for k in top_keys if k in facts],
            columns=["fact", "value"],
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)

        with st.expander("Top risky schools (facts subset)", expanded=False):
            top_schools = facts.get("top_schools") or []
            if top_schools:
                st.dataframe(pd.DataFrame(top_schools), use_container_width=True, hide_index=True)
            else:
                st.write("_None._")

        with st.expander("KPI rows (target vs actual)", expanded=False):
            kpi_rows = facts.get("kpi_rows") or []
            if kpi_rows:
                st.dataframe(pd.DataFrame(kpi_rows), use_container_width=True, hide_index=True)
            else:
                st.write("_None._")

        with st.expander("Full review_facts JSON", expanded=False):
            st.json(facts)

        st.download_button(
            "Download review_facts.json",
            data=json.dumps(facts, indent=2).encode("utf-8"),
            file_name="review_facts.json",
            mime="application/json",
            use_container_width=True,
        )


# --------------------------------------------------------------------------------------
# Footer
# --------------------------------------------------------------------------------------
st.divider()
st.caption(
    "ShikshaSignal AI · Monthly District Review Agent · Milestone 5 · "
    "local-first · synthetic data · no PII · LLM never computes numbers."
)
