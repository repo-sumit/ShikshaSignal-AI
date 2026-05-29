# ShikshaSignal AI — Product Validation & Practicality Report

## Context

Sumit (B2G EdTech PM) wants ShikshaSignal AI to be a flagship AI-agent portfolio project: useful to real government education teams, free-first, terminal-first, synthetic-data-safe, and buildable solo. This document is **not a build** — it is a critical validation of the idea in `CONTEXT.md` and a sharpened, more practical product definition. It was produced by a 6-agent analysis (strategy, scope, tech/data, B2G-domain grounding, plus two adversarial critics) and synthesized here. The headline: the *core insight is real and demoable, but the `CONTEXT.md` scope is ~4–5× too large to build all at once and must be sequenced, not attempted in one shot.*

> **Decisions locked (user, 2026-05-29):**
> 1. **Scope = keep the full `CONTEXT.md` vision** (6-agent LangGraph + RAG + Chroma + Next.js + Supabase) as the *destination*. Per the validation findings **and `CONTEXT.md` §9/§21**, it will be built in **phases**, deterministic-core-first, so there is a working, auditable, demoable artifact at the end of every phase — not a 70-day all-or-nothing build. The lean A-spine the report recommends becomes **Phase 1**, not the whole product.
> 2. **Cadence = Monthly** (default), with a `--week` drill-down. Product renamed **Monthly District Review Agent**.
> The validation guardrails apply to *every* phase: the LLM never computes numbers; MockLLM (Jinja) is the default with auto-fallback; every memo number must trace to source data (number-grounding eval harness); synthetic data is correlated + seasonal + clearly labeled synthetic.

---

## 1. Idea Quality Verdict

| Axis | Score (1–10) | Justification |
|---|:---:|---|
| Real-world usefulness | **8** | PMU/DEO review prep is a genuine, recurring, hated manual chore. Right pain. |
| B2G EdTech relevance | **9** | DIKSHA / NIPUN / PM SHRI / NISHTHA hierarchy is authentic to Sumit's world. |
| AI-agent fit | **6** | Synthesis & drafting suit LLMs, but most *decision* value is deterministic math, not agentic reasoning. |
| Flagship portfolio value | **8** | A working domain-specific agent that emits a real memo + tracker beats "another RAG chatbot." |
| Feasibility for a solo builder | **4** | Full vision (6 agents + LangGraph + RAG + Chroma + SQLite→Supabase + Streamlit→Next.js + audit + approval) ≈ 3–4 months solo. High abandonment risk. |
| Data availability | **7** | Synthetic gen is easy & public-safe; the catch is *realistic correlation* so root-cause demos aren't laughable. |
| Differentiation vs dashboards/chatbots | **7** | "Why + what to do + who acts + track closure" differentiates **if** the deterministic core is trustworthy; weak if it's just GPT prose over CSVs. |
| Demo potential | **9** | "One command → a credible district review memo + risk CSV + action tracker" is a great 90-second demo. |
| Recruiter/interviewer appeal | **8** | Shows PM judgment + domain depth + agent orchestration + eval discipline — rare combination. |
| Risk of becoming too broad (HIGH = BAD) | **9** | Very high. 6 agents, 2 frontends, 2 DBs, 5 personas, 10 output artifacts — classic portfolio over-scope that never ships. |

**Overall verdict: "Good idea but needs sharper scope."**

The core insight — turning scattered program data into an evidence-backed review brief + action tracker — is real, domain-authentic, and demoable. But `CONTEXT.md` is a *product roadmap masquerading as an MVP*. The defensible value lives in the **deterministic analytics + risk core** and the **single best LLM use (narrative synthesis into a review memo)**, not in the agent count. If the LLM only paraphrases numbers, differentiation collapses to "dashboard with a chatty summary." **Build it — but cut ~60% of v1.**

---

## 2. Real Problem Validation

**Strongest single problem:** A PMU program analyst must assemble a recurring district/state review deck and spends **70–80% of the cycle on mechanical data assembly, not analysis**.

- **Who exactly:** The **PMU analyst / PMU lead** (employed by the implementation partner running the program), who prepares review material for the State Project Director / Education Secretary and DEOs. Secondary: the **DEO/DPC** who must walk into a block review with a defensible "which 5 schools and why."
- **Painful manual workflow today:** Pull DIKSHA usage exports + assessment sheets + NISHTHA/training exports + UDISE+ extract → **reconcile mismatched school IDs** (UDISE vs internal vs DIKSHA org ID — hours, error-prone) → manually paste WhatsApp/CRC field notes into a sheet → build per-block pivots, color red cells, write a slide narrative → draft leadership memo + per-block coordinator messages → redo it next cycle from scratch. **~6–12 hours per district cycle; 2–3 person-days for a state roll-up.**
- **Decisions delayed:** Which schools get the next mentor (CRC) visit; which teachers need training follow-up; which infra tickets escalate; which underperformance gets flagged *before* the review. Escalations slip a full cycle (1–4 weeks).
- **Data they have but don't act on:** Usage drops, training stalls, baseline→endline regressions are visible in raw exports but never cross-joined; field issues sit in WhatsApp; "not reported" is treated as zero, distorting rankings.
- **Repeatedly created artifacts:** Review deck, leadership memo, coordinator messages, action/follow-up tracker, "meeting questions."
- **Why an agent beats a dashboard (and when it doesn't):** The deliverable is *prose + prioritized actions*, not a chart — a dashboard shows "Block 3 = 41%"; the officer still has to write *why, what to do, who owns it, what evidence*. That synthesis is the LLM's real edge. It is **NOT** better for the numeric truth — KPIs, risk, rankings, DQ flags must be **deterministic**, or you've built a confident liar.
- **Measurable value:** Review prep ~6–12h → ~30–60 min (≈80–90% reduction); escalation latency "next cycle" → "same day"; one consistent risk definition across districts.

> **Problem statement:** *A PMU program analyst struggles to produce timely, evidence-backed district review briefs because the data is scattered across DIKSHA exports, assessment sheets, training records, and WhatsApp field reports with mismatched IDs and no shared risk definition, leading to delayed escalations and decks that describe what happened but not what to do. ShikshaSignal AI helps by deterministically computing KPIs, risk scores, and data-quality flags, then using a single LLM layer to turn those verified numbers into a review memo, prioritized intervention plan, and stakeholder messages — cutting review prep from hours to minutes.*

---

## 3. Use-Case Prioritization

Scoring 1–5 (1 = weak, 5 = strong). *AI-agent value* is low when a sorted dashboard table already does the job.

| # | Use case | Pain | Data avail | AI value | MVP feas | Demo | **TOTAL** |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | **Weekly/monthly district review generation (composite memo)** | 5 | 5 | 5 | 4 | 5 | **24** |
| 2 | High-risk school/block identification | 5 | 5 | 2 | 5 | 4 | **21** |
| 3 | Action-tracker generation (risk → owner/priority) | 4 | 4 | 4 | 5 | 4 | **21** |
| 4 | DIKSHA usage-drop diagnosis (WoW + root cause) | 4 | 5 | 4 | 4 | 4 | **21** |
| 5 | "What changed since last period?" delta analysis | 4 | 5 | 4 | 4 | 4 | **21** |
| 6 | FLN assessment gap analysis (baseline→current vs avg) | 5 | 4 | 3 | 4 | 4 | **20** |
| 7 | Stakeholder message drafting (BRC/CRC nudges) | 4 | 4 | 5 | 4 | 3 | **20** |
| 8 | Monthly review-meeting pack (roll-up) | 4 | 4 | 3 | 4 | 4 | **19** |
| 9 | Teacher-training completion follow-up | 4 | 4 | 2 | 5 | 3 | **18** |
| 10 | District/block comparison (benchmarking) | 3 | 5 | 2 | 4 | 3 | **17** |
| 11 | Escalation report (threshold breach → memo) | 3 | 4 | 3 | 3 | 3 | **16** |
| 12 | Field-issue summarization (free-text clustering) | 3 | 3 | 4 | 3 | 3 | **16** |
| 13 | Policy-to-KPI mapping (NIPUN/PM SHRI → thresholds) | 2 | 3 | 3 | 3 | 4 | **15** |

**Honest low-scorer notes:** Policy-to-KPI mapping (#13) is the most *overrated* item — the real mapping is ~6 hardcoded rules; a Chroma+RAG pipeline to retrieve a 20-line YAML is engineering theatre. Field-issue summarization (#12) suffers "grading your own homework" (your faker text won't match real messy multilingual notes). #2/#9/#10 are genuinely useful but **deterministic table ops** — keep them as *tools the agent calls*, not standalone "agents." Escalation (#11) is just the review filtered to High band — a parameter, not a product.

- **TOP 1 for MVP: #1 Weekly/monthly district review generation** — the only use case that *consumes* risk + delta + policy + drafting as inputs, produces a real hand-built artifact, and demos in one command. Everything else is a component of it.
- **TOP 3 for V2:** (1) **"What changed since last period"** delta — cheapest high-value add; turns a report into *monitoring*. (2) **Action-tracker with owner/priority + carry-over closure** — converts insight into accountability. (3) **Usage-drop diagnosis with root-cause hypotheses** — clearest "agent reasoning over data" that isn't a sorted table.

---

## 4. What Should Be Added

| Addition | Why it matters | Phase | Difficulty | Data needed |
|---|---|:--:|:--:|---|
| Action-owner assignment (role-mapped BRC/CRC/DEO) | Insight without an owner is ignored in gov programs | **MVP** | Low | risk type → role rules |
| Evidence/source panel (every claim cites the row/metric) | **Biggest credibility lever** for a gov audience | **MVP** | Low | already in CSVs |
| Data-quality + freshness/coverage warnings | Officials distrust tools that hide gaps; builds trust | **MVP** | Low | the 5 CSVs |
| Target-vs-actual-vs-last-period on every KPI | *The* language of the review room; raw values are meaningless | **MVP** | Low | KPIs + policy targets |
| Decomposed/explainable risk score (component contributions) | Kills the "black box = 73" objection; defensible upward | **MVP** | Low | risk components |
| "What changed since last period" delta narrative | First thing every senior official asks | **MVP** | Low | ≥2 periods |
| Before/after comparison (baseline vs current) | Core to FLN/NIPUN story | **MVP** | Low | assessments.csv |
| District/block/**cluster**/school hierarchy | Matches the real org chart; needed to route actions | **MVP** | Low | schools.csv (+cluster) |
| Exportable memo (Markdown → paste into deck/Word) | Adoption = "I can drop this into my deck" | **MVP** | Low | report output |
| WhatsApp-style stakeholder message drafts (no sending) | Realistic, demos well | **MVP** | Low | risk/action outputs |
| Program health score (single 0–100 district number) | Executives want one headline number | **MVP** | Low | KPI aggregates |
| "Assumptions & limitations" footer on every memo | Cheap honesty; pre-empts "where's this from?" | **MVP** | Low | none |
| **ID-reconciliation report (matched/unmatched schools)** | Demonstrates you understand the real #1 pain | **MVP** | Med | source keys |
| **"Missing data → who to chase" list** | A DEO's real first move is *getting* data | **MVP** | Low | DQ + hierarchy |
| Follow-up tracker (carry-over open/closed from last period) | Weakest part of real reviews; disproportionately valuable | **V2** | Med | prior tracker |
| Intervention confidence score (High/Med/Low + why) | Honest hedging; avoids overconfident gov recs | **V2** | Med | risk + DQ |
| Hindi / simple-language stakeholder summary | Field "last mile" reads Hindi | **V2** | Med | summary + LLM |
| **WhatsApp-text → structured-issue extractor** | Solves the one input everyone struggles with; biggest "wow" | **V2** | Med | raw field text |
| Repeat-offender / persistent-risk flag (High ≥2 periods) | The signal that drives field visits | **V2** | Med | multi-period history |
| Human-approval gate before final recs | Matches gov governance | **V2** | Low | approval flag |
| Audit log of agent reasoning (plan + tool calls) | Trust + "agentic" portfolio story | **V2** | Med | agent trace |
| Escalation matrix (band → who's notified) | Encodes gov SOP | **V2** | Low | threshold rules |
| Policy-to-KPI mapping **as YAML, not RAG** | Sources targets; 80% value at 5% effort | **V2** | Low | 1 mapping file |
| Mock PMU dashboard (Streamlit) | Demo polish, not where value is | **Later** | Med | all outputs |

**Cheapest credibility multipliers (do these first):** target-vs-actual framing, decomposed risk, data-coverage honesty + "who to chase", "what changed", and "hypothesis — verify" labeling. Together they convert a *dashboard* into a *review-room-ready tool* for ~a day of work.

---

## 5. What Should Be Edited or Reduced

| Item | Verdict | Why |
|---|---|---|
| Multi-agent architecture | **Simplify in MVP** | Build as 4–5 deterministic functions in sequence (load→QA→analytics→risk→draft). A 6-agent graph for a linear report is over-engineering + a debugging nightmare. |
| LangGraph | **Postpone to V2** | Stateful-graph overhead, zero MVP payoff for a linear pipeline. Adopt only when you add the human-approval interrupt + "what changed" branching. |
| RAG | **Postpone to V2** | Corpus is ~6 short docs → 10 KPIs. Replace with `policy_map.yaml`. RAG over 6 docs is a slower hardcode. |
| PDF policy ingestion | **Remove (MVP)** | Author clean markdown; PyMuPDF/pdfplumber parsing of gov PDFs is yak-shaving with no demo value. Drop `unstructured`. |
| Supabase | **Postpone to V2** | CSV + a results folder (or SQLite for tracker write-state) is enough for single-user terminal MVP. |
| Next.js dashboard | **Postpone to V2** | A React app is weeks of work proving nothing about the agent. Terminal + `.md` artifact *is* the MVP. |
| Vector DB (Chroma) | **Remove (MVP)** | No RAG in MVP → no vectors. |
| Authentication | **Remove (MVP)** | Single local user; pure overhead. |
| Real-time / gov APIs | **Remove** | Explicit non-goal; synthetic CSV only. |
| Multi-role permissions (RBAC) | **Simplify in MVP** | Keep `role` as a *prompt parameter* that changes tone/owner-routing; no enforcement. |
| Automated WhatsApp/email sending | **Remove (MVP)** | Generate *draft* text only; sending is a non-goal + compliance liability. |
| Advanced ML prediction | **Remove** | Weighted formula is the right level; you'd be overfitting synthetic data you wrote. |
| PDF report generation | **Postpone to V2** | Markdown copy-pastes into decks; add PDF only if asked. |
| Live deployment | **Postpone to V2** | `git clone + python` run is the demo. |

**Bottom line:** the original design is ~4–5× too large for v1. Cut to **deterministic core + ONE LLM writer call + markdown output.** Everything tagged agent/graph/RAG/vector/dashboard/deploy is V2.

---

## 6. More Practical Product Positioning

### Option A — District Review Copilot (review prep)
- **User:** PMU analyst / PMU lead (secondary: DEO). **Problem:** 6–12 h/cycle of manual deck assembly across 5+ sources; nothing templated across cycles.
- **MVP workflow:** Load CSVs → deterministic KPI + DQ pass → deterministic risk ranking → ONE synthesis call drafts memo + meeting questions + messages → write `weekly_district_review.md` + `risk_ranking.csv` + `action_tracker.csv`.
- **Agent role:** Narrative synthesis of *verified* numbers; role-specific messages; meeting questions. Math stays deterministic.
- **Why practical:** Smallest end-to-end path to a real artifact; mirrors an actual recurring job; one-command demo. **Weakness:** "just a report generator" if root-cause is shallow; needs ≥2 periods to feel alive. **Portfolio:** High — readable in 60s, clear PM framing.

### Option B — Program Risk & Intervention Planner
- **User:** DEO / BRC allocating limited field-visit capacity. **Problem:** no defensible, consistent triage.
- **MVP workflow:** Risk engine scores every school/block with per-factor breakdown → planner maps each high-risk school to action + owner + priority + evidence → ranked CSV + per-school action cards.
- **Agent role:** Action recommendation + evidence assembly + risk-band explanation. **Why practical:** risk engine is deterministic + testable; LLM bounded to action drafting. **Weakness:** arbitrary weights without validation; "interventions" can sound generic. **Portfolio:** High for analytics, weaker as an *agent* showcase (mostly scoring + lookup).

### Option C — Policy-to-Action PMU Assistant
- **User:** State PMU lead aligning execution to NIPUN/PM SHRI mandates. **Problem:** policy goals not continuously mapped to live KPI gaps.
- **MVP workflow:** Ingest policy docs → RAG index → for each KPI gap retrieve the relevant mandate → generate "policy goal X at risk because KPI Y" + compliance follow-ups.
- **Agent role:** RAG retrieval + grounded mapping. **Why practical:** distinctive, hard to clone, B2G-credible *if* corpus is real. **Weakness:** highest build cost (RAG + chunking + hallucination eval); demo feels abstract; weakest standalone. **Portfolio:** highest differentiation, highest sprawl risk.

**Recommendation: Build Option A as the spine, fold in ONE bounded element of B (decomposed/explainable risk + a small action-rule library), and grow toward C.** A is most demoable, most credible (mirrors a real job), least likely to sprawl. B's risk engine is already *inside* A's pipeline, so you get its analytical credibility for free.

> **Per the locked decision (full vision):** A is **Phase 1**; C (Policy-to-Action / RAG) is retained as a later phase, *not* dropped. **But even in Phase 1, policy linkage starts as a hardcoded KPI→target/mandate lookup table (5–8 rows) before it becomes RAG** — the YAML captures 80% of the value at 5% of the effort and de-risks the RAG phase by giving it a deterministic baseline to beat.

---

## 7. Practical MVP Definition

- **MVP name:** **Monthly District Review Agent** *(see §13 — change "Weekly" → "Monthly"; real DEO reviews are monthly, weekly DIKSHA data is noisy. Keep a `--week` drill-down.)*
- **Target persona:** the **District PMU analyst** who hand-builds the review for the DEO/SPM. Secondary: the DEO who reads it.
- **ONE primary workflow:** `python -m app.review --district "District Alpha" --period 2026-05` → load CSVs → deterministic KPIs + risk + DQ + period-over-period delta → ONE LLM call (mock by default; Gemini/Groq optional; Ollama fallback) narrates from verified facts → write artifacts. No chat, no UI, no API server in v1.
- **Input data (synthetic, public-safe):** the 5 CSVs (`schools`, `diksha_usage`, `assessments`, `teacher_training`, `field_issues`) for **≥2 periods** + `policy_map.yaml`. Scale: **2 districts / 8 blocks / ~120 schools** (not 1,000).
- **Output artifacts:**
  - `outputs/weekly_district_review.md` — health score, KPI summary (target-vs-actual), block risk ranking, top risky schools, **what changed**, DQ warnings + "who to chase", policy-linked observations, root-cause **hypotheses (labeled)**, Top-5 actions, draft messages, meeting questions, assumptions footer.
  - `outputs/risk_ranking.csv` — every block & school with score, band, **component breakdown**.
  - `outputs/action_tracker.csv` — risk → action → suggested owner (role) → priority → evidence → status (`proposed`).
- **Success criteria:** (1) one command → all 3 artifacts in <60s on a free/mock path; (2) **100% of numeric claims trace to a CSV value**; (3) risk scores deterministic & reproducible (unit-tested, same input → identical CSV); (4) runs end-to-end with **no paid API**; (5) **degrades gracefully** — if the LLM is unavailable, deterministic + template memo still generates; (6) memo ≤2 pages, zero manual fact-fixing for the demo district.
- **Demo (60–90s):** "PMUs spend a day a week building these by hand — watch." → show 5 CSVs → run one command (KPIs, risk, delta, DQ, "drafting…") → open the memo (health score → red blocks → *what changed* → a hypothesis with its **evidence lines** → Top-5 actions w/ owners) → open `action_tracker.csv` + a Hindi/WhatsApp draft → close on the assumptions footer.
- **Not included in Phase 1 (deferred to later phases per the roadmap, not removed):** LangGraph multi-agent graph, RAG/Chroma, PDF ingestion, Next.js, Supabase, auth/RBAC, real APIs, outbound messaging, ML models, deployment. *(§5's "Remove" verdicts apply to Phase 1 only; under the locked full-vision decision these re-enter in P3–P5.)*

---

## 8. Free-First Technical Reality Check

**Design discipline that makes free-tier viable:** the **LLM never does math, never ranks, never invents numbers — it only narrates pre-computed values.** That makes Mock vs Groq vs Gemini vs Ollama a *prose-quality* choice, not a *correctness* choice — and it's exactly the design a government reviewer trusts.

- **Ollama (local):** `qwen2.5:7b` or `llama3.1:8b` (16 GB RAM) is the best local pick; 3B models are an OK CPU fallback but drift on long structured memos and first-token latency (5–30s) makes live demos painful. **Use as the "fully offline" badge, not the showcase.**
- **Gemini free (`gemini-2.x-flash`):** prose well above any 3B local model; ~10–15 RPM / ~250 req/day free. **Recommended default cloud.** Caveat: free-tier may use prompts to improve Google's products → *synthetic data only*, state it in README (turn it into a privacy talking point).
- **Groq free (Llama-3.x 8B/70B):** LPU speed makes "watch the memo generate in 4s" feel magical → **best for a live/video demo.** Caveat: tighter daily caps, models renamed often → **read model name from env, never hardcode.**
- **Local embeddings:** `all-MiniLM-L6-v2` (CPU, ms, free) — only relevant once V2 RAG exists; for 6 docs a numpy cosine match (~20 lines) beats a vector DB.
- **MockLLM (Jinja2 templates) — non-negotiable:** renders every section with **zero model calls** + rule-based root-cause lines. It is the **load-bearing de-risk**: CI/`pytest`/first demo run offline with no keys; free APIs throttle at the worst moment; gives a byte-stable golden output to diff-test grounding against; "works fully offline, no AI dependency for correctness" is itself a B2G selling point.

**LLM abstraction:** one interface, four backends, swap by `LLM_PROVIDER=mock|groq|gemini|ollama`. **Default = `mock`.** Every real provider wraps calls in try/except with **auto-fallback to MockLLM** (log `LLM_FALLBACK_USED=true`). Same prompt templates for all; model names from env; LLM receives only pre-computed numbers and returns only prose (Pydantic-validate, fall back to mock on parse failure).

| Stack | Layers | Tradeoff |
|---|---|---|
| **(a) Zero-cost** | MockLLM (Jinja) · Pandas+CSV · markdown policy · CLI→`.md`/`.csv` | Templated prose, no fluency |
| **(b) Better free-tier (default)** | **Gemini Flash default + Groq 70B for live speed**, MockLLM always wired as fallback · MiniLM (V2) · Pandas (+optional DuckDB) · Streamlit viewer · SQLite for tracker state | Free quotas; synthetic-only terms |
| **(c) Paid upgrade later** | Claude Sonnet/GPT · pgvector/Qdrant · Postgres+RBAC · Next.js | ₹/memo + infra + compliance work |

**Default recommendation:** build the **zero-cost core first** (deterministic + MockLLM, fully tested, fully offline), then layer **(b)** with `gemini` as documented default and `groq` as the fast-demo toggle. Ollama = nice-to-have badge. Don't touch (c) until someone pays.

---

## 9. Data Reality Check

- **Synthetic (everything, v1):** all 5 CSVs + policy markdown from one seeded script (`--seed 42`). Lets you *engineer the risk spread on purpose*.
- **Public data LATER (with caveats):** UDISE+ (real school directory/infra — *aggregate only, stale, yearly*); NAS (district/state achievement — *sample-based, no school-level*); ASER (rural FLN — *NGO method, attribution*); DIKSHA public reports (*aggregate, lagged, no per-school-week*). **Frame:** "schema built to *accept* UDISE+/NAS aggregates later" — stronger than faking real data.
- **Avoid entirely:** any child-level record (names, DOB, marks-per-child, attendance-per-child), Aadhaar/APAAR/student IDs, real phone numbers/addresses/GPS, real teacher names/IDs, scraped per-school-per-child rows, and **real district/school names** (use "District Alpha", "GPS Rampur No.2"). Use proxies only (`active_students_proxy`, synthetic `TCH_00471`).
- **Exact CSVs first (CONTEXT schemas + 3 critical fixes):**
  1. `schools.csv` — *add `cluster`* (CRC persona dies without it).
  2. `diksha_usage.csv` — weekly rows = the "what changed" engine.
  3. `assessments.csv` — *add `assessment_round` (baseline|midline|endline)* so improvement is well-defined; model as **sparse waves, not weekly**.
  4. `teacher_training.csv` — *add `last_activity_date`* for stale-record checks.
  5. `field_issues.csv` — add `issue_type` enum, `resolved_at`.
  6. `policy_documents/*.md` — 6 one-page hand-written files, **no PDFs**.
- **Minimum rows for a convincing first demo (CONTEXT's 1,000 schools is too big — unreadable + slow):** **1 state · 2 districts (1 focus + 1 comparison) · 8 blocks · ~120 schools (~15/block) · ~600 teachers · 8 weeks DIKSHA · G1–G3 × 2 subjects (~720 rows) · ~150 field issues.** Keep a `--scale full` flag to regenerate the 1,000-school version for one "it scales" screenshot.
- **Make it feel real:** Indian naming conventions (GPS/UPS/Govt Girls HS, fictional districts); **exam-period usage trough weeks 5–6 (−30–60%) + explicit summer-vacation near-zero** so the tool recognizes seasonal dips instead of screaming "collapse!"; **engineer correlations from a latent per-school health factor** (no internet → low sessions; low training → flat FLN gain; ≥2 open issues → lower usage) so 1–2 blocks are consistently red and a "villain block" exists; 1–2 deliberate false-positives to make explainability look real; **5–8% deliberately broken rows** (missing latest week, `completion_percent=140`, `enrollment=0`, future `created_at`, one duplicate `school_id`) so DQ has real findings; 3–4 hard-injected sharp decliners for "biggest movers."
- **Hierarchy:** denormalize `state→district→block→cluster→school` onto each school row; `school_id` is the single FK in all fact tables; structured debuggable IDs like `D01_B03_C2_SCH017`; aggregation is pure `groupby`.
- **Week-over-week:** each school = baseline level + trend slope + per-week noise + seasonal multiplier + optional shock; compute latest, prior, WoW %Δ, 4-week rolling mean, decliner flag (`latest < 0.7 × 4-wk mean`).
- **Risk signals:** drive from the latent health factor + per-component noise → CONTEXT weights; **target ~55% Low / ~30% Med / ~15% High**; one clear "problem block." Sanity-assert the band histogram after generation; normalize each component to 0–100 before weighting (or raw learning-points swamp the score).
- **Realistic ranges (PMU would nod):** DIKSHA — 25–45% of schools are genuine non-starters (0 usage); typical 20–80 scans/month; FLN baseline 25–45% at grade level, believable endline gain +8–20 pts (>+30 is suspicious); training completion 40–75% mid-cycle; digital-device availability 20–55%; student attendance 55–80% with festival/exam dips.

---

## 10. Agent Fit Analysis

| Layer | Capabilities |
|---|---|
| **Deterministic (normal code)** | CSV load + schema validation; data-quality checks; KPI calc; weighted risk scoring + banding; ranking / top-N / WoW diffs / decliners. *The LLM must never compute these.* |
| **LLM (language)** | Narrative summary over pre-computed facts; root-cause **hypotheses** (constrained, labeled); intervention phrasing; stakeholder messages; Hindi simplification. |
| **Agentic (planning/tools/memory/loop)** | Intent routing (which sections a query needs); deciding which tools to call & in what order; loop until memo complete / self-check; human-in-the-loop approval; light memory of prior-period actions. |

**Honest verdict:** ~**80% of demonstrable value is deterministic** + one well-prompted LLM call per section. The CONTEXT 6-agent LangGraph swarm is **largely theater** — a "Risk Scoring Agent" running a fixed formula is `risk_score()`, not an agent; a sharp reviewer reads it as resume-padding. **But** "agentic" *is* justifiable if confined to what genuinely needs planning + tool use + a loop + approval.

**Smallest agentic behavior worth shipping (the one MVP agent):** a tool-using **"Review Compiler"** that → **(1) plans** the section set from query+role → **(2) calls deterministic tools** (`load → validate → kpis → risk → rank → diff → policy_lookup`, all returning JSON) → **(3) narrates** each planned section via a constrained LLM call on that section's JSON → **(4) self-checks grounding** (every number in prose must exist in source JSON; re-run ungrounded sections, bounded retries) — *this loop is what earns "agentic, not a script"* → **(5) approval interrupt** (actions written `status=proposed`, flip to `approved` only on `--approve`).

**Must stay deterministic for trust/auditability:** all numbers (LLM only echoes; post-check rejects any number not in source JSON); the risk formula + banding (version-stamped, hand-recomputable); DQ findings; ranking/top-N; the audit trail (every tool call, input hash, provider used + whether mock-fallback fired, approval event); provenance on every claim; **root causes always labeled "hypothesis."**

---

## 11. Final Improved Product Scope

- **Product Name:** **ShikshaSignal AI — Monthly District Review Agent** (v1).
- **Target User:** District PMU analyst (primary) preparing the DEO/State review; DEO (secondary reader).
- **Core Problem:** Review prep is 70–80% manual data wrangling across 5+ mismatched sources, delaying escalations and producing decks that say *what happened* but not *what to do, by whom, with what evidence*.
- **MVP Workflow:** `python -m app.review --district "District Alpha" --period 2026-05` → load → validate/DQ + ID-reconciliation → KPIs (target-vs-actual) + risk (decomposed) + period delta → Review-Compiler agent plans sections → MockLLM (default) / Gemini / Groq narrates from verified facts → grounding self-check → write 3 artifacts + audit log.
- **Key Features:** decomposed explainable risk; target-vs-actual KPIs; "what changed"; DQ + coverage honesty + "who to chase"; evidence/provenance on every claim; role-mapped action owners; Top-5 actions one-pager; draft stakeholder messages; assumptions/limitations footer; hypothesis-labeled causation; deterministic + offline fallback.
- **Data Inputs:** 5 synthetic CSVs (≥2 periods, ~120 schools) + `policy_map.yaml`.
- **AI Capabilities:** one constrained LLM narration layer (mock/free-tier) over verified facts; planning + grounding self-check + approval interrupt (the single honest agent).
- **Deterministic Capabilities:** loading, validation, DQ, KPIs, risk scoring/banding, ranking, deltas, artifact writing, audit log.
- **Outputs:** `outputs/weekly_district_review.md`, `outputs/risk_ranking.csv`, `outputs/action_tracker.csv` + `outputs/audit_log.json`.
- **Why Useful:** automates the real weekly/monthly artifact a PMU hand-builds; cuts prep hours→minutes; surfaces escalations same-day.
- **Why Practical:** terminal-first, free-first (one optional LLM call w/ deterministic fallback), data-safe, solo-buildable in ~15 days, one-command demo.
- **Why Portfolio-Worthy:** "I built the analyst, not the dashboard" — encodes how a government review room *thinks* (target-vs-actual, RAG-by-name, action carry-over, coverage honesty, verify-before-you-accuse) with every number auditable. A PM's differentiator, not just an engineer's.

---

## 12. First Build Plan (first 10 tasks — no AI APIs)

| # | File/folder | What to build | Why it matters | Acceptance criteria | Test command |
|---|---|---|---|---|---|
| 1 | repo root: `README.md`, `requirements.txt` (lean: pandas, pydantic, jinja2, pyyaml, pytest), `.env.example` (`LLM_PROVIDER=mock`), `app/`, `scripts/`, `data/synthetic/`, `outputs/`, `tests/` | Lean scaffold + venv + SYNTHETIC-DATA banner in README | Clean start; avoids the over-scoped tree | `pip install -r requirements.txt` succeeds; folders exist | `pip install -r requirements.txt` |
| 2 | `scripts/generate_synthetic_data.py` | Seeded generator: hierarchy (2 dist/8 blocks/~120 schools/cluster), latent health factor → **correlated** metrics, exam/vacation seasonality, 3–4 injected decliners, 5–8% broken rows, target ~55/30/15 band split | Realistic data = credible demo; defeats "randomized = fake" | Produces 5 CSVs in `data/synthetic/`; rerun w/ same seed = identical files; band-split assertion passes | `python scripts/generate_synthetic_data.py --seed 42` |
| 3 | `app/tools/csv_loader.py` + `app/schemas/` | Typed loaders + Pydantic schemas for all 5 CSVs | Trust starts at ingestion | Loads all CSVs into validated frames; bad rows reported not crashed | `python -m app.tools.csv_loader` |
| 4 | `app/tools/data_quality.py` | Missing/stale/invalid/duplicate checks + coverage % + ID-reconciliation (matched/unmatched) | Coverage honesty = #1 credibility signal | Emits DQ report incl. the planted broken rows + "% schools reporting" | `python -m app.tools.data_quality` |
| 5 | `app/tools/kpi_calculator.py` + `data/policy_map.yaml` | District/block/school KPI rollups as **target-vs-actual-vs-last-period** | The review room's language | Prints district summary (sessions, training %, FLN gain, counts) vs targets | `python -m app.tools.kpi_calculator` |
| 6 | `app/tools/risk_score.py` | Decomposed weighted score (config weights) + bands + **per-component contributions**; version-stamped | Explainable risk kills the black-box objection | Same input → identical scores (reproducibility test); each school shows component breakdown | `python -m app.tools.risk_score` |
| 7 | `app/tools/rankings.py` → `outputs/risk_ranking.csv` | Block/school ranking + "what changed"/decliners; CSV writer | Turns scores into the artifact officials scan | `risk_ranking.csv` written with score+band+components+delta | `python -m app.tools.rankings` |
| 8 | `app/llm/` (`base.py`, `factory.py`, `mock_llm.py`) + Jinja templates | LLM abstraction; **MockLLM (Jinja) as default**, rule-based root-cause lines | Load-bearing de-risk; offline-first | `LLM_PROVIDER=mock` renders all sections, no network | `python -m app.llm.mock_llm` |
| 9 | `app/review.py` (Review-Compiler) → `outputs/weekly_district_review.md`, `outputs/action_tracker.csv`, `outputs/audit_log.json` | Orchestrate: plan → call tools → mock-narrate → **grounding self-check** → write artifacts; actions `status=proposed` | The end-to-end product; the demo | One command writes all 3 artifacts; every memo number traces to source JSON | `python -m app.review --district "District Alpha"` |
| 10 | `tests/` (`test_data_generation`, `test_kpi_calculator`, `test_risk_score`, `test_grounding`) + `tests/golden_review.md` | Unit tests + **number-grounding assertion** (no memo number absent from facts-JSON) + golden diff | Separates "tested" from "graded my own homework" | `pytest` green; grounding test catches an injected hallucinated number | `pytest -q` |

*Build LLM-free through Task 10. Only after these pass, wire Gemini/Groq behind the same `app/llm` interface (no code change beyond a provider class) — keeping mock as the auto-fallback.*

---

## 13. Final Recommendation

- **Should you build this?** **Yes — as the full `CONTEXT.md` vision, built in validated phases (your locked choice).** The full 6-agent / RAG / dashboard / DB system is the *destination*; the only risk to manage is the ~70-day all-at-once trap, so we sequence it (roadmap below) and ship a working artifact at the end of each phase. `CONTEXT.md` itself mandates this order (§9, §21).
- **Positioning:** **Option A (Monthly District Review Copilot) spine + Option B's decomposed/explainable risk** as Phase 1; **Option C (Policy-to-Action / RAG)** retained as a later phase.
- **Sequence, don't skip:** keep LangGraph swarm, RAG/Chroma, Next.js, Supabase, auth, audit — but each enters only after the deterministic core + single grounded agent are working and tested. Policy linkage ships as a YAML lookup *before* RAG.
- **Add to make it real (every phase):** correlated+seasonal synthetic data; ≥2 periods for "what changed"; ID-reconciliation + data-coverage honesty; decomposed risk; evidence/provenance on every claim; hypothesis-labeling; role-mapped owners; a **number-grounding eval harness** (`golden_review.md`); MockLLM default + auto-fallback.
- **First terminal demo should:** run **one command** that loads synthetic CSVs, computes KPIs + risk ranking + DQ deterministically, narrates a memo from verified facts (mock by default), and writes `weekly_district_review.md` + `risk_ranking.csv` + `action_tracker.csv`, then prints top-5 risky blocks/schools.
- **First command to run:** `python scripts/generate_synthetic_data.py --seed 42` (then `python -m app.tools.kpi_calculator`, then `python -m app.tools.risk_score` — build zero LLM code until these three produce trustworthy, tested output).
- **Biggest risk to defend against:** the **synthetic-data circularity trap** ("you found what you planted"). Defenses: (1) number-grounding eval harness; (2) rule-derived, hypothesis-labeled causation (no free-text LLM guessing); (3) loud "synthetic-by-design, schema accepts real aggregates later" framing.

> **One-sentence portfolio pitch:** *ShikshaSignal AI is a terminal-first, free-first agentic copilot that ingests the messy, mismatched reality of a district's education data and produces the exact paste-ready monthly review memo, explainable risk ranking, and carry-over action tracker a PMU finalizes the night before the DEO meeting — with every number deterministic, traceable, and auditable.*

---

## Phased Roadmap to the Full Vision (reconciles the full-scope decision with the validated build order)

| Phase | Goal | Adds (from the full `CONTEXT.md` vision) | Demoable artifact at phase end |
|---|---|---|---|
| **P1 — Deterministic core** *(= `CONTEXT.md` Milestone 1; Tasks 1–7 below)* | Trustworthy data + KPIs + risk, no AI | synthetic generator, loaders, data-quality, KPI calc, risk score, rankings | CLI prints district summary + top-5 risky blocks/schools; `risk_ranking.csv` |
| **P2 — Single grounded agent** *(Tasks 8–10)* | Honest "agentic" memo, free/offline | LLM abstraction + MockLLM default, Review-Compiler (plan→tools→narrate→grounding check→approval gate), `policy_map.yaml`, eval harness | One command → `weekly_district_review.md` + `action_tracker.csv` + `audit_log.json`; `pytest` green |
| **P3 — Free-tier LLM + Streamlit viewer** | Fluent prose + visual demo | Gemini/Groq/Ollama behind the same interface (auto-fallback to mock), Streamlit 4-screen viewer, Hindi/simple-language messages | Live "watch it generate" demo; screenshot-able dashboard |
| **P4 — Multi-agent + RAG + persistence** | The full `CONTEXT.md` architecture | LangGraph orchestrator + 6 agents (over the existing deterministic tools), Policy RAG (MiniLM + Chroma) over real markdown, SQLite→Supabase for action-tracker carry-over, FastAPI routes | Multi-turn agent answering the 10 golden prompts; carry-over closure tracking |
| **P5 — Product-grade + V2 features** | Polish + differentiators | Next.js/shadcn frontend, auth/RBAC, audit UI, WhatsApp-text→structured-issue extractor, persistent-risk flags, deployment | Hosted, shareable product |

**Rule across phases:** a phase ships only when its artifact is tested and the number-grounding assertion passes. Never let a later-phase keyword (LangGraph, Chroma, Next.js) block a working artifact.

---

## Verification (how to validate the direction before/while building)

This report is the deliverable; the decisions are locked. The first executable proof of correctness is **P1, Tasks 2 + 6**: running `python scripts/generate_synthetic_data.py --seed 42` then `python -m app.tools.risk_score` should print a believable **~55/30/15 Low/Med/High** band split and one clear "problem block" — the earliest signal the data + risk core are credible *before* any LLM is added. P2 adds the decisive test: `pytest` must catch an injected hallucinated number via the grounding assertion.
