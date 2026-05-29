# ShikshaSignal AI — Project Overview

> ⚠ **Disclaimer:** ShikshaSignal AI runs on **synthetic, DIKSHA-like data only** — no real student, teacher, or school records, no Aadhaar/APAAR, no live government APIs. The project is **local-first**: it runs end-to-end on a laptop with no paid API and no internet (MockLLM is the default narrator). Every number in every memo is computed in deterministic Python and is hand-recomputable from the source CSVs.

## Product thesis

ShikshaSignal AI turns the scattered, mismatched program data a district PMU analyst lives with — DIKSHA usage exports, FLN assessment sheets, NISHTHA-style training rolls, WhatsApp field issues, school directory rows — into a single paste-ready monthly review memo, an explainable risk ranking, and a carry-over action tracker. Every KPI, risk score, and ranking is computed deterministically; the LLM is bounded to narrating those verified numbers into prose. The result is a review artifact the analyst can defend line-by-line in front of the DEO, with every claim traceable back to a row in a CSV.

## Target users

### Primary — District PMU analyst

The person who currently hand-builds the review the night before the DEO meeting. They have the data but not the time to reconcile it. They are the analyst the tool replaces, not the audience the tool writes for.

### Secondary — District Education Officer (DEO)

The consumer of the memo. They read top-down, want target-vs-actual framing, want to know "which 5 schools and why," and will not trust a number they cannot recompute.

### Secondary — B2G EdTech program manager / implementation partner

Runs the program on behalf of the state. Uses the same memo and action tracker to brief their leadership, route field visits, and close out the previous month's actions.

## Problem statement

A district PMU analyst spends **70–80% of the review cycle on mechanical data assembly across five or more mismatched sources** — reconciling school IDs between UDISE, internal, and DIKSHA exports; copy-pasting WhatsApp notes into a sheet; rebuilding per-block pivots from scratch; writing the narrative last. Roughly **6–12 hours per district cycle**, two to three person-days for a state roll-up. Escalations slip a full cycle (1–4 weeks) because the underlying signals — usage drops, training stalls, repeated field issues — are visible in the raw exports but never cross-joined. The data exists. The synthesis does not.

## Primary workflow

| # | Step | Artifact |
|---|------|----------|
| 1 | Open the laptop, regenerate (or load) the five synthetic CSVs and the policy map | `data/synthetic/*.csv`, `data/policy_map.yaml` |
| 2 | Run the one-command demo: `python scripts/run_local_demo.py` | console log + four output files |
| 3 | Deterministic layer loads, validates, computes data-quality flags, KPIs, decomposed risk, rankings, and period delta | `outputs/review_facts.json`, `outputs/risk_ranking.csv`, `outputs/block_risk_ranking.csv` |
| 4 | Review-Compiler plans sections, narrates each from `review_facts.json`, runs the grounding self-check, and falls back to MockLLM on any failure | `outputs/monthly_district_review.md` |
| 5 | Action tracker is emitted with every action at `status=proposed` (nothing auto-approved, nothing auto-sent) | `outputs/action_tracker.csv` |
| 6 | Every tool call, provider used, fallback fired, and grounding failure is logged | `outputs/audit_log.json` |
| 7 | Optional: open the Streamlit viewer to walk a stakeholder through the same artifacts: `python -m streamlit run frontend/streamlit_app.py` | five-tab viewer |

The memo is then pasted into the deck or Word doc the DEO actually reads.

## Why a dashboard alone is not enough

- A dashboard shows **what** (Block 3 = 41%). The reviewer still has to write **why, what to do, who owns it, and what evidence**.
- Dashboards rarely link a number to a **policy goal or target** — "41% scans" is meaningless without "target 70%, last month 48%, NIPUN linkage."
- Dashboards treat **"no data" as zero**, which silently distorts rankings and hides the schools that need the most chasing.
- Dashboards do not produce a **carry-over action tracker**: there is no memory that last month's action for SCH_017 is still open.
- Dashboards do not produce **stakeholder-ready prose**. The analyst still has to write the memo.

## Why deterministic-first matters here

Government users cannot trust a confident-but-wrong number. A "73 risk" with no decomposition, no source rows, and no version stamp is unusable in a review room. ShikshaSignal AI keeps every number in plain Python:

- Risk weights, bands, and the formula version are stamped into `audit_log.json` so the score is **hand-recomputable** from the same CSVs.
- The KPI table is **target-vs-actual-vs-last-period** because that is the language of the review room.
- The **grounding evaluator** rejects any number in the memo that is not present in `review_facts.json`, and `--strict-grounding` re-renders the whole memo with MockLLM if any section fails.
- Every fallback (missing API key, HTTP error, ungrounded output) is logged with a reason, so the audit trail tells you exactly which sentences came from which provider.

The LLM is a writer, not a calculator. That is the entire trust contract.

## Why this is a practical AI-agent project

This is not another RAG chatbot over six policy PDFs. The LLM is bounded to narration; the "agent" is the loop around it:

1. **Plan** the section set from the role and the available facts.
2. **Call deterministic tools** (`load → DQ → KPIs → risk → rank → delta → policy_lookup`), all returning JSON.
3. **Narrate** each section by passing only the verified JSON for that section to the LLM.
4. **Self-check grounding** — every number in the prose must trace to `review_facts.json`; ungrounded sections are re-rendered with MockLLM.
5. **Approval gate** — every action is written as `status=proposed`; nothing is auto-approved, nothing is auto-sent.

That five-step loop is what earns the word "agent" without inventing six fake ones. The full LangGraph multi-agent orchestration described in `CONTEXT.md` is **queued for Phase 8**, but the current single-LLM-pass design is the validated MVP: it ships a real, testable, demoable artifact today and gives the multi-agent phase a deterministic baseline to beat.
