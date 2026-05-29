# Roadmap

## Where this came from

This roadmap reconciles the original product vision in [`CONTEXT.md`](../CONTEXT.md) with the validated, de-risked build order documented in [`plan.md`](../plan.md).

> Synthetic data only. Every milestone — shipped or planned — operates on synthetic DIKSHA-like data. No real student, teacher, or school records are involved. No Aadhaar or APAAR identifiers are used.

## Phase status table

| Phase | Name | Status | Core artefact at phase end | Tests |
| --- | --- | --- | --- | --- |
| M1 | Deterministic analytics core | Done | KPI + risk + rankings printable from CLI | included in 122+ suite |
| M2 | Policy retrieval layer (deterministic YAML lookup) | Done | `data/policy_map.yaml` + `ingest_policy_docs.py` validator | included |
| M3 | Monthly District Review Compiler | Done | `outputs/monthly_district_review.md` + 3 sidecars | included |
| M4 | Free/local LLM providers (mock/gemini/groq/ollama) + fallback | Done | `audit_log.json` records provider, model, fallback, latency | included |
| M5 | Streamlit Review Viewer | Done | local UI at `http://localhost:8501` | included |
| M6 | Portfolio polish + documentation hardening | In progress | README rewrite + 7 docs + sample excerpts + `run_local_demo.py` | added in this milestone |
| M7 | Demo data quality + UX polish | Planned | tighter narrative, richer planted decliners, better Streamlit polish | - |
| M8 | LangGraph single orchestrator | Planned | one orchestrator graph with plan -> tools -> narrate -> ground -> approval-gate | - |
| M9 | Action tracker persistence (carry-over) | Planned | SQLite-backed action state across periods; closure detection | - |
| M10 | Packaged local demo or deployment | Planned | one-binary local demo OR a thin hosted demo with synthetic data only | - |

## What each near-term milestone actually does

### M7 — Demo data quality + UX polish

Tighten the synthetic dataset so the story it tells lands faster. Engineer a clearer cause-and-effect arc for the focus district: more obvious week-over-week decliners, sharper teacher-training gaps in the problem block, and field issues whose timing visibly precedes the learning-outcome dip. On the Streamlit side, polish the KPI cards, add small spark-trends, and improve the empty/error states. **Non-goals:** new data sources, real-data ingestion, multi-district comparison beyond the two demo districts.

### M8 — LangGraph single orchestrator

Replace the current straight-through `run_review(...)` pipeline with one LangGraph orchestrator: `plan -> tools (KPIs, risk, policy lookup) -> narrate -> ground -> approval-gate`. The grounding check and MockLLM fallback stay exactly where they are today — they become explicit graph edges instead of inline calls. **Non-goals:** multi-agent swarms, autonomous tool selection, removing the deterministic core, or moving any computation into the LLM.

### M9 — Action tracker persistence (carry-over)

Today `outputs/action_tracker.csv` is regenerated each run and every action starts `status=proposed`. M9 introduces a small SQLite store so actions carry across monthly periods, prior-period actions appear in the new memo with their last known status, and closure can be detected when the underlying KPI recovers. **Non-goals:** a workflow engine, notifications, role-based assignment, or any outbound communication. Approval still happens out-of-band.

### M10 — Packaged local demo or deployment

One of two paths, picked based on reviewer feedback: either (a) a single packaged local demo (PyInstaller or a `pipx`-installable script) that runs end-to-end on a laptop with no setup, or (b) a thin hosted demo on a free tier that serves the Streamlit viewer over synthetic data only. **Non-goals:** multi-tenant hosting, authentication, real data, or any deployment that could be mistaken for a production system.

## Explicitly out of scope right now

- Real DIKSHA / UDISE / VidyaSamiksha Kendra integration
- Real student-level, teacher-level, or school-level records
- Automated outbound messages (SMS, WhatsApp, email) to officials or field staff
- Paid LLM dependencies — the project must run end-to-end on free/local providers
- Multi-tenant SaaS deployment
- Role-based access control or auth
- Mobile application

## How to suggest a change

Open an issue describing the use case and the persona it serves (e.g. District Education Officer, Block Resource Person, State PMU analyst).
