# ShikshaSignal AI — Monthly District Review Agent

![tests](https://img.shields.io/badge/tests-passing-brightgreen)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-MIT-lightgrey)
![offline-first](https://img.shields.io/badge/offline-first-success)
![synthetic-data](https://img.shields.io/badge/data-synthetic-orange)

> ⚠️ **SYNTHETIC DEMONSTRATION DATA — NOT REAL GOVERNMENT RECORDS.**
> Every CSV in this repo is produced by a seeded generator. District, block, and
> school names are fictional. There is no child-level PII, no Aadhaar/APAAR, no
> scraped or government-issued data. References to "DIKSHA-like" or
> "UDISE+-like" describe the *shape* of the synthetic data, not its source.

## One-line pitch

A local-first, free-first AI-assisted review copilot that turns synthetic
district education program data into an auditable monthly review memo,
explainable risk ranking, action tracker, and audit log.

---

## Why this project exists

A PMU (Program Management Unit) analyst preparing a District Education Officer
review today spends **6–12 hours per district cycle** stitching together
DIKSHA usage exports, FLN assessment sheets, NISHTHA/training records,
WhatsApp field notes, and UDISE+ extracts — most of it mechanical
reconciliation across mismatched school IDs and inconsistent "not reported vs
zero" conventions (see [`plan.md` §2](plan.md)).

The deliverable at the end of that grind is not a chart. It is **prose +
prioritized actions + owners + evidence**: which five schools, why they
slipped, who acts next, what the data quality caveats are. ShikshaSignal AI
automates the assembly while keeping every number deterministic and traceable.

## Real-world workflow being solved

A PMU analyst's monthly cycle, compressed:

1. Pull last month's DIKSHA usage, FLN assessment, teacher training, and field
   issue exports.
2. Reconcile school IDs across systems, drop bad rows, flag missing weeks.
3. Compute KPIs vs policy targets and vs last period.
4. Decide which blocks and schools are "High risk" — and defend the call.
5. Draft a memo for the DEO, a per-block action tracker, and assumptions/caveats.

ShikshaSignal AI runs steps 2–5 as one command, against synthetic data, and
hands back four artifacts a human can paste into a review deck.

## What the product does

Running the compiler produces four artifacts in `outputs/`:

- `monthly_district_review.md` — the review memo (executive summary, what
  changed, hypotheses, recommendations, assumptions footer).
- `action_tracker.csv` — proposed actions with owner role, priority, evidence
  pointer. Every row starts `status=proposed` and needs human approval.
- `review_facts.json` — the canonical set of pre-computed numbers the memo
  is allowed to cite. Used by the grounding check.
- `audit_log.json` — run lineage: provider, model, fallback flags per
  section, latency, files used, risk model version.

`rankings.py` additionally writes `outputs/risk_ranking.csv` and
`outputs/block_risk_ranking.csv`.

## Demo preview

- [`docs/sample_outputs/sample_review_excerpt.md`](docs/sample_outputs/sample_review_excerpt.md)
- [`docs/sample_outputs/sample_action_tracker_excerpt.md`](docs/sample_outputs/sample_action_tracker_excerpt.md)

## Architecture overview

A deterministic Python core (data quality → KPIs → decomposed risk → rankings)
produces a `review_facts.json` payload. A thin LLM narrator (mock by default,
or Gemini / Groq / Ollama) renders each memo section from those facts under
strict grounding rules. Any ungrounded number triggers a per-section fallback
to the offline MockLLM. A Streamlit viewer reads the artifacts back without
duplicating any review logic.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full diagram and
data flow.

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| M1 | Synthetic data + data quality + KPI + decomposed risk + rankings | Done |
| M2 | Deterministic policy map lookup (RAG deferred per `plan.md` §5) | Done |
| M3 | Review compiler + MockLLM narrator + markdown / action / audit reporting + grounding eval | Done |
| M4 | Free / local LLM providers (Gemini, Groq, Ollama) + factory + fallback semantics | Done |
| M5 | Local Streamlit viewer over existing artifacts | Done |
| M6 | Demo polish: one-command runner, sample outputs, portfolio docs, expanded tests | Done |
| M7 | Real-use readiness layer: configurable KPI/risk, schema specs, import validator, mapping templates, Data Readiness tab | In progress |
| M8 | LangGraph single orchestrator (plan → tools → narrate → ground → approve) | Planned |
| M9 | Action tracker persistence + carry-over closure across periods | Planned |
| M10 | Packaged local demo or thin synthetic-data hosted demo | Planned |

Full roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Quick start

```bash
pip install -r requirements.txt
python scripts/generate_synthetic_data.py --seed 42
python -m app.tools.import_validator
python scripts/ingest_policy_docs.py
python scripts/run_local_demo.py
python -m streamlit run frontend/streamlit_app.py
pytest -q
```

Requires Python 3.11+. No API keys are needed for the default path.

## CLI usage

```bash
# Offline default — MockLLM, no keys, no network
python -m app.review --district "District Alpha" --period 2026-05 --llm-provider mock

# Google Gemini free tier — needs GOOGLE_API_KEY (or GEMINI_API_KEY)
python -m app.review --district "District Alpha" --period 2026-05 --llm-provider gemini

# Groq free tier — needs GROQ_API_KEY
python -m app.review --district "District Alpha" --period 2026-05 --llm-provider groq

# Local Ollama daemon — needs OLLAMA_BASE_URL (default http://localhost:11434)
python -m app.review --district "District Alpha" --period 2026-05 --llm-provider ollama

# Strict mode: if any section fails the grounding check, rerender the WHOLE memo with MockLLM
python -m app.review --district "District Alpha" --period 2026-05 --llm-provider mock --strict-grounding
```

## Streamlit usage

```bash
python -m streamlit run frontend/streamlit_app.py
```

> Note (Windows): use `python -m streamlit run ...` — Streamlit's `Scripts/`
> directory is not always on `PATH`, so the bare `streamlit run ...` form can
> fail. On POSIX, either form works.

The viewer is local-only, reads back the four artifacts in `outputs/`, and
exposes the same provider + strict-grounding controls as the CLI.

## LLM provider options

| Provider | Env vars | Fallback behaviour |
| --- | --- | --- |
| `mock` (default) | none | N/A — this *is* the fallback target |
| `gemini` | `GOOGLE_API_KEY` or `GEMINI_API_KEY`, optional `GEMINI_MODEL` | Missing key → MockLLM at construction. HTTP error / empty / ungrounded → per-section MockLLM |
| `groq` | `GROQ_API_KEY`, optional `GROQ_MODEL` | Same three-layer fallback |
| `ollama` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Daemon unreachable → MockLLM; same call-time + grounding fallbacks |

Every fallback path is logged in `audit_log.json` with `fallback_used`,
`fallback_reason`, and per-section `provider` metadata. `--strict-grounding`
re-renders the entire memo with MockLLM if any section failed grounding.

## Output artifacts

| File | Contents | How it stays grounded |
| --- | --- | --- |
| `outputs/monthly_district_review.md` | Executive summary, what changed, hypotheses, recommendations, assumptions footer | Every numeric token validated against `review_facts.json` by `app.eval.grounding`; failed sections fall back to MockLLM |
| `outputs/action_tracker.csv` | Proposed actions with owner role, priority, evidence pointer, `status=proposed` | Generated deterministically from risk + KPI tables, not from LLM output |
| `outputs/review_facts.json` | Canonical computed numbers (KPIs, risk components, deltas, ranks) | Produced by deterministic Python only — the single source of truth |
| `outputs/audit_log.json` | Run lineage: provider, model, fallback flags, latency, files used, risk model version + config path | Written from `app.reporting.audit_log`; no LLM input |
| `outputs/import_validation_report.{md,json}` | Per-CSV readiness report: presence, columns, PK uniqueness, FK match rate, planted-pathology findings, verdict | Pure deterministic check against `schemas/input_schemas.yaml`; no LLM input |

## Real-use readiness (Milestone 7)

The synthetic demo is the default. Milestone 7 adds the layer a PMU analyst
would need before pointing the compiler at **aggregate, public-safe, approved**
CSV exports — without unlocking real student-level data, real APIs, or any
outbound messaging.

| Capability | File | Purpose |
| --- | --- | --- |
| Configurable risk weights | [`config/risk_weights.yaml`](config/risk_weights.yaml) | Edit the 7 risk-component weights. Validator enforces they sum to 1.0 and use known component names. |
| Configurable KPI targets | [`config/kpi_targets.yaml`](config/kpi_targets.yaml) | Edit the policy-linked KPI targets used in the memo's target-vs-actual table. Wins over the legacy `data/policy_map.yaml`. |
| Input schema spec | [`schemas/input_schemas.yaml`](schemas/input_schemas.yaml) | Declarative contract for the five CSVs (required cols, types, enums, primary + foreign keys, forbidden-fields list). |
| Import validator | [`app/tools/import_validator.py`](app/tools/import_validator.py) | `python -m app.tools.import_validator` → markdown + JSON readiness report; verdict ∈ {Ready, Ready with warnings, Not ready}. |
| Mapping template | [`docs/templates/real_data_mapping_template.md`](docs/templates/real_data_mapping_template.md) + [`.csv`](docs/templates/real_data_mapping_template.csv) | One row per ShikshaSignal target column, ready for an analyst to fill in source-system / source-column / transformation against an aggregate export. |
| Readiness guide | [`docs/REAL_USE_READINESS.md`](docs/REAL_USE_READINESS.md) | Pilot scope, required approvals, security/governance checklist, CSV-first workflow. Pilot-only — **not** production deployment guidance. |
| Streamlit Data Readiness tab | [`frontend/streamlit_app.py`](frontend/streamlit_app.py) | Visualises the validator's verdict, per-file results, and individual findings inside the viewer. |

Validator usage:

```bash
python -m app.tools.import_validator                    # writes outputs/import_validation_report.{md,json}
python -m app.tools.import_validator --source-dir path/to/csvs --outputs-dir path/to/out
```

> The validator exits non-zero only when the verdict is **Not ready** (errors
> present). Warnings exit 0, so this can be wired into pre-commit / CI loops
> without false positives.

The audit log records the active risk config — so every review is traceable
back to the exact `risk_weights.yaml` (or the built-in fallback) that produced
its scores:

```json
"risk_formula_version": "1.0",
"risk_weights": { "learning_outcome": 0.25, "digital_usage": 0.20, ... },
"risk_config_path": ".../config/risk_weights.yaml",
"risk_config_source": "yaml"
```

## Safety and governance

The "never" rules — enforced in tests, not just documented (see
[`docs/SAFETY_AND_PRIVACY.md`](docs/SAFETY_AND_PRIVACY.md)):

- The LLM never computes numbers, never ranks, never invents facts.
- Every memo number must trace to `review_facts.json`.
- Root causes are labelled "Hypothesis" and require field verification.
- All actions start `status=proposed`. Nothing is auto-approved or auto-sent.
- Synthetic data only. No real student / teacher / school records. No
  Aadhaar, APAAR, or other PII.
- Local-first. No paid API is required to run any part of the project.
- Fallback to MockLLM is the trust-preserving path and remains the default.

## Testing and evaluation

- Current test count: **122 passing** as of M5; growing through M6.
- Includes `app/eval/grounding.py` — a number-grounding harness that traces
  every memo number back to `review_facts.json`.
- Adversarial tests inject ungrounded numbers into LLM output and assert the
  fallback fires.
- Reproducibility tests assert byte-stable artifacts for a fixed seed.

Detail: [`docs/EVALUATION.md`](docs/EVALUATION.md).

## Roadmap

- M6 (in progress): one-command demo, sample outputs, polished docs.
- M7: multi-period carry-over and closure tracking in the action tracker.
- M8: WhatsApp-style stakeholder message drafts (drafts only — no sending).
- M9: optional RAG over policy documents (currently a deterministic YAML map).
- M10: multi-district roll-up memo.

Full plan: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Portfolio / interview talking points

- **Deterministic-first AI agent.** KPIs, risk scores, and rankings are
  unit-tested Python; the LLM only narrates pre-computed facts — so a wrong
  number is impossible by construction.
- **Grounding eval that catches hallucinations.** Every numeric token in the
  memo is traced back to `review_facts.json`; ungrounded sections are
  auto-replaced and the failure is logged.
- **Free-first, offline by default.** MockLLM is feature-complete; Gemini,
  Groq, and Ollama are opt-in and fall back gracefully when keys or daemons
  are unavailable.
- **Phased, validated scope.** Each milestone ships a runnable artifact;
  scope cuts (e.g., deferring RAG) are documented in `plan.md` rather than
  hidden.
- **Domain-honest.** Built around the PMU analyst's real monthly review
  workflow — owners, evidence pointers, assumptions footer, and a
  synthetic-data disclaimer on every artifact.
