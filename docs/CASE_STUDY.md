# ShikshaSignal AI — Case Study

> ⚠️ ShikshaSignal AI runs on **synthetic DIKSHA-like data only**. No real student, teacher, or school records are used. The project is a portfolio prototype, not a deployed government system.

A portfolio case study of how I scoped, sequenced, and built a domain-specific AI agent for government education programs — built solo, free-first, offline-default, and grounded in a real B2G workflow.

---

## 1. Context

In B2G EdTech, every district runs **recurring program reviews** — monthly cycles where a PMU (Program Management Unit) analyst assembles "what happened, what's at risk, what to do" for the State Project Director, the District Education Officer (DEO), and field coordinators. The data needed for that review is scattered: **DIKSHA** for digital usage, **NISHTHA** for teacher training, **UDISE+** for school master data, **assessment sheets** for learning outcomes, and **WhatsApp / CRC field notes** for ground reality. None of these systems share a primary key cleanly — UDISE codes, internal IDs, and DIKSHA org IDs drift apart constantly.

I have lived inside this loop as a B2G EdTech PM. The pain is not analytical sophistication. The pain is **assembly**.

## 2. Problem

A PMU analyst typically spends **6–12 hours per district cycle** (2–3 person-days for a state roll-up) doing this manually:

- Pulling four to five exports, reconciling mismatched school IDs by hand.
- Building per-block pivots, colour-coding red cells, writing the slide narrative.
- Pasting WhatsApp issues into a sheet because there is no structured field-issue store.
- Drafting the leadership memo, then drafting per-block coordinator messages.
- Re-doing all of it next cycle from scratch.

The downstream cost: **"what changed since last period" is rarely analysed**, escalations slip a full cycle (1–4 weeks), and "not reported" is silently treated as zero — distorting rankings.

## 3. User Persona

**Primary — PMU analyst / PMU lead.** Employed by the implementation partner. Prepares review material for the State Project Director and DEOs. Spends most of the cycle on mechanical assembly, not analysis. Judged on memo quality and timeliness.

**Secondary — DEO / DPC** (District Education Officer / District Programme Coordinator). Walks into a block review needing a defensible answer to "which 5 schools and why." Lives with the consequences of a bad ranking.

**Tertiary — B2G product manager** (me, and people like me). Needs to see one consistent risk definition across districts to escalate to leadership.

## 4. Product Goal

Turn the manual review prep into:

```bash
python -m app.review --district "District Alpha" --period 2026-05 --llm-provider mock
```

…plus a local Streamlit UI for non-CLI users.

Targets:

- Cut prep from **6–12 hours to ~30–60 minutes**.
- Preserve **every number's auditability** — every figure in the memo traces to a source row.
- Stay **free and offline-default** so it runs on a laptop with no API key.

## 5. Constraints

- **Solo builder**, evenings and weekends.
- **Free-first**: no paid API may be required to run the project.
- **Offline-default**: must work without an internet connection.
- **No real student PII** — synthetic data only, no Aadhaar / APAAR / UDISE pulls.
- **Portfolio-grade in weeks**, not months: must produce a working artifact at the end of every milestone, not a 70-day all-or-nothing build.

## 6. Solution

ShikshaSignal AI is a **terminal-first review compiler** with a **Streamlit viewer** on top.

- **Deterministic-first.** All KPIs, risk scores, rankings, and data-quality flags are computed in pure Python from typed inputs. The LLM never computes a number.
- **LLM bounded to prose.** One well-prompted LLM call per memo section, fed pre-computed facts. Outputs are then re-checked against `review_facts.json`.
- **Grounding check.** Every numeric token in the LLM's draft must trace back to a known fact. If it doesn't, the section falls back to a deterministic Jinja template (MockLLM).
- **Four providers**, all free or local: **Gemini** (free tier), **Groq** (free tier), **Ollama** (fully local), and **MockLLM** (offline default).
- **Audit log on every run** — provider used, fallbacks taken, files read, risk weights, model version.

## 7. MVP Scope

| Piece | Concrete shape |
|---|---|
| Synthetic data | 1 state, 2 districts, 8 blocks, ~160 schools, 8 ISO weeks, planted pathologies |
| Artifacts | `monthly_district_review.md`, `action_tracker.csv`, `audit_log.json`, `review_facts.json`, `risk_ranking.csv` |
| LLM providers | Gemini, Groq, Ollama, MockLLM (default) |
| UI | Streamlit viewer with sidebar controls and 5 tabs |
| Tests | 122+ passing tests across data, risk, grounding, providers, UI artifact reader |

## 8. Key Design Decisions

| # | Decision | Why |
|---|---|---|
| 1 | **Deterministic-first core; LLM only for prose** | Government audiences distrust "confident liars". Numbers must be reproducible byte-for-byte from a seed. |
| 2 | **MockLLM as the default provider** | Free-first and offline-default mean the demo must run with zero credentials. MockLLM (Jinja templates over verified facts) is the trust-preserving baseline. |
| 3 | **`policy_map.yaml` instead of RAG / Chroma** | The real policy-to-KPI mapping is ~6 hardcoded rules. A vector store to look up a 20-line YAML is engineering theatre. Postponed RAG without losing any demo value. |
| 4 | **Per-section LLM fallback semantics** | If a provider errors, returns empty, or fails grounding, that *one section* falls back to MockLLM — not the whole memo. Every fallback is logged in `audit_log.json` with reason. |
| 5 | **Grounding eval as the load-bearing trust signal** | Adversarial tests inject hallucinated numbers into LLM output; the grounding check must catch them. This is the single most important eval — it is what makes the memo safe to show a real DEO. |

## 9. AI / Agent Design

The validation report (`plan.md`) was blunt: **~80% of the demo value is deterministic + one well-prompted LLM call per section.** Not six agents, not LangGraph, not RAG. Just a tight loop:

1. Load synthetic data → 2. Compute KPIs + risk + DQ → 3. Retrieve relevant policy targets → 4. Call the LLM with a fact pack per section → 5. Check grounding → 6. Fall back to MockLLM on any failure → 7. Emit memo + tracker + audit log.

This is the **smallest agentic behaviour worth shipping**: an orchestrator that calls deterministic tools, hands their outputs to a bounded LLM, and verifies every claim before letting it leave the building. Six-agent LangGraph orchestration is on the roadmap (M8) — but only once the deterministic spine is rock-solid. The portfolio lesson here is restraint, not headcount.

## 10. Data Strategy

All data is **synthetic, seeded, and correlated** — not random noise. The generator produces:

- 1 state (Pradesh North), 2 districts (Alpha = focus, Beta = comparison), 8 blocks, ~160 schools.
- 8 ISO weeks of weekly DIKSHA-like usage with realistic seasonality.
- Grade 1–3 assessment data in Literacy and Numeracy.
- ~150 field issues spread across weeks and blocks.
- A risk-band split target of **~55% Low / 30% Medium / 15% High** — so the risk model isn't trivially constant.
- **Planted pathologies** so DQ has real things to catch: a duplicate `school_id`, a teacher with `completion_percent > 100`, a future-dated field issue, an orphan school ID in DIKSHA usage, and ~5–8% deliberately broken rows. One block (Alpha / Madhopur) is engineered to be the villain.

Sample artifacts are checked into `docs/sample_outputs/` so a reviewer can read them without running the code.

## 11. Safety and Governance

Recap (see [`docs/SAFETY_AND_PRIVACY.md`](SAFETY_AND_PRIVACY.md) for the full position):

- **No PII** — synthetic data only. No real student / teacher / school records. No Aadhaar / APAAR.
- **No outbound messaging** — no WhatsApp send, no email send. Stakeholder messages are drafts.
- **Hypothesis labels** — all root causes are labelled "Hypothesis" and require field verification.
- **Status = proposed** — every action starts as `proposed`. Nothing is auto-approved or auto-sent.
- **Audit log everywhere** — every run writes `audit_log.json` with provider, model, fallbacks, files read, and risk weights.

## 12. Evaluation

What's actually tested (122+ tests, growing):

- **Deterministic reproducibility** — CSV byte-identical outputs for a given seed.
- **Risk model invariants** — band split target, component-weight sum, monotonicity.
- **Grounding adversarial tests** — synthetic LLM responses with injected hallucinated numbers must be caught.
- **Provider fallback tests** — missing credentials, import errors, HTTP errors, empty responses, ungrounded outputs — each path is exercised and verified to fall back to MockLLM with a logged reason.
- **UI artifact reader** — the Streamlit viewer reads exactly what `app.review` writes, with no schema drift.

The grounding eval is the load-bearing one. If it ever passes a hallucinated number, the entire trust argument of this project collapses. So it's tested adversarially, not just optimistically.

## 13. Results So Far

- **Five milestones completed** (M1–M5), with M6 (polish) in progress.
- **One-command demo**: `python scripts/run_local_demo.py` produces four artifacts end-to-end.
- **Four LLM providers** wired and tested: Gemini, Groq, Ollama, MockLLM.
- **Streamlit viewer** with sidebar controls, KPI cards, and 5 tabs.
- **122+ tests passing**, full offline workflow, zero paid dependencies.
- **Five output artifacts** (memo, action tracker, audit log, review facts, risk ranking) — see `docs/sample_outputs/` for excerpts.

## 14. What I Learned

- **Framing AI capability vs deterministic capability is the actual product work.** The instinct is to ask "what can the LLM do here?" — the more useful question is "what must NOT be the LLM's job?" Locking the LLM out of numbers was the single highest-leverage decision.
- **Overscoping is the default failure mode of portfolio projects.** The original `CONTEXT.md` was 6 agents + LangGraph + RAG + Chroma + Next.js + Supabase. `plan.md` cut ~60% of v1 and sequenced the rest. Without that cut, this project would still be at zero.
- **A number-grounding eval is worth more than ten capability demos.** It is the only thing standing between "looks impressive" and "is safe to put in front of a DEO."
- **B2G audit culture is a design constraint, not an afterthought.** "Where did this number come from" is asked in every review room. The audit log was not a nice-to-have; it was a precondition for the memo being takeable seriously.
- **Honesty in the UI builds trust faster than polish.** "Hypothesis", "proposed", "synthetic data", and the assumptions-and-limitations footer cost nothing and pre-empt the most common objection.

## 15. Next Steps

See [`docs/ROADMAP.md`](ROADMAP.md) for the full sequence. In short:

- **M6** — documentation polish, sample outputs, case study, safety doc, roadmap. *(In progress.)*
- **M7** — richer demo data, UX refinements in the Streamlit viewer.
- **M8** — LangGraph orchestrator: replace the linear pipeline with a small multi-agent graph, keeping the deterministic spine.
- **M9** — action tracker persistence: carry-over closure across periods, repeat-offender flagging.
- **M10** — packaged demo / deployment story: one-line setup, recorded walkthrough, optional containerised viewer.

---

**Project name:** ShikshaSignal AI · **Status:** Portfolio prototype on synthetic data · **Default mode:** local + offline + free.
