# 3-Minute Demo Script

> Setup story: You are presenting **ShikshaSignal AI** to a PM, recruiter, or B2G stakeholder. The project runs **fully local** on your laptop with **synthetic DIKSHA-like data** — no real student or school records, no paid APIs, no government deployment claims.

> ⚠️ Disclaimer to say once, up front: "Everything you'll see uses synthetic data engineered to mimic DIKSHA/UDISE shapes. The agent is designed so the same code accepts real aggregated data later."

---

## Persona (in 30 seconds)

Say this verbatim:

> "I'm a PMU analyst at a State Project Office. Every month I compile a District Review Memo for the District Magistrate. I open six dashboards, copy numbers into a deck, write talking points, and chase block-level officers for action items. It's six to twelve hours per district, per cycle. This agent does that work in under a minute — and every number is auditable."

---

## Problem

What happens today, manually:

- Pull DIKSHA usage, learning outcomes, teacher training, infrastructure, and field issues from five separate dashboards.
- Reconcile them in Excel. Spot the worst-performing blocks by eye.
- Draft a memo. Guess at root causes. Email block officers with vague asks.
- No grounding. No audit trail. No standard format. Different analyst, different memo.

**The pain:** 6-12 hours per district per cycle, and the output isn't repeatable.

**Our wedge:** deterministic KPIs + risk score + a bounded LLM that only narrates the numbers it's given.

---

## Terminal demo flow

### Step 1 — Generate the full review in one command

```
python scripts/run_local_demo.py
```

(Point at the terminal.) "This generates synthetic data, validates the policy YAML, and compiles the review in a few seconds. Four artifacts land in `outputs/`."

Point out as it runs:
- Synthetic data generated (~160 schools, 8 weeks, engineered pathologies).
- `data/policy_map.yaml` validated (6 policy targets).
- Review compiled with the mock LLM provider.
- Four files written: `monthly_district_review.md`, `action_tracker.csv`, `audit_log.json`, `review_facts.json`.

### Step 2 — Open the memo

```
outputs/monthly_district_review.md
```

(Scroll slowly.) Point at:
- The **KPI table** — every row is target-vs-actual against `policy_map.yaml`.
- Root causes are labelled **"Hypothesis"** — the agent never claims certainty without field verification.
- The synthetic-data disclaimer at the top.

### Step 3 — Open the action tracker

```
outputs/action_tracker.csv
```

(Point at the columns.) Three things to call out:
- Every row has an **evidence** field linking back to a KPI value.
- `suggested_owner` is a **role** (Block Education Officer, Cluster Resource Coordinator) — never a person.
- Every action starts at `status = proposed`. Nothing auto-approves, nothing auto-sends.

### Step 4 — Open the audit log

```
outputs/audit_log.json
```

(Pause on this one.) "This is the trust artifact." Point at:
- `llm_provider: mock` and `actual_llm_provider: mock`
- `fallback_used: false`
- `model_name`, `provider_latency_ms`, `risk_formula_version: 1.0`
- `grounding_failures: {}` — zero ungrounded numbers in the memo.
- `risk_weights` — the exact 7-component weighting is logged with every run.

### Step 5 — Re-run with Gemini (no API key) to show graceful fallback

```
python -m app.review --district "District Alpha" --period 2026-05 --llm-provider gemini
```

(Point at the terminal.) "I don't have a Gemini key set. The agent doesn't crash."

Open `outputs/audit_log.json` again:
- `requested_llm_provider: gemini`
- `actual_llm_provider: mock`
- `fallback_used: true`
- `fallback_reason: missing_credentials`

"That's the trust-preserving path. The audit log always records exactly what happened."

### Step 6 — Show the grounding tests

```
pytest tests/test_grounding.py -q
```

(While it runs.) "These are adversarial tests. They inject fake numbers into LLM output and assert that `check_grounding()` catches them. The `--strict-grounding` flag re-renders the entire memo with the mock LLM if any section fails."

---

## Streamlit demo flow

### Step 1 — Launch the viewer

```
python -m streamlit run frontend/streamlit_app.py
```

(While it loads.) "Same artifacts, browsable UI. This is what a PMU analyst would actually use."

### Step 2 — Configure in the sidebar

- District: **District Alpha**
- Period: **2026-05**
- Provider: **mock**
- Click **Generate Review**.

### Step 3 — Executive Overview

(Point at the metric cards.) "Overall risk band, district score, top-3 blocks at risk, data quality score — all computed deterministically, before the LLM sees anything."

### Step 4 — Walk the five tabs

1. **Review Memo** — the narrated markdown.
2. **Risk Ranking** — block-level table, sortable.
3. **Action Tracker** — every row with evidence and proposed owner role.
4. **Audit Log** — the same JSON, pretty-printed.
5. **Review Facts** — the structured fact pack the LLM was allowed to reference.

### Step 5 — Hit a download button

(Click the download icon on the memo tab.) "Every artifact downloads as-is. This is what gets attached to the DM's review packet."

### Step 6 — Toggle provider to "groq" with no key

Change the sidebar provider to **groq**, click **Generate Review** again.

(Point at the fallback banner.) "Same story — the viewer surfaces the fallback. The audit log records `fallback_reason: missing_credentials`. Nothing is hidden."

---

## What to click / what to show

A checklist of micro-moments that make the demo land:

- [ ] The terminal run finishes in **seconds**, not minutes.
- [ ] The KPI table has **every row tied to a policy target**.
- [ ] The word **"Hypothesis"** is visible next to every root cause.
- [ ] `status = proposed` in the action tracker.
- [ ] `fallback_used: true` with a clear `fallback_reason` in audit log.
- [ ] Grounding tests pass live.
- [ ] Streamlit sidebar swap shows the **same artifacts** rendered in a UI.
- [ ] The synthetic-data disclaimer is visible at the top of the memo.

---

## Closing pitch

> "ShikshaSignal AI is a deterministic-first AI agent for B2G review rooms. The numbers come from policy-grounded KPIs and a transparent risk formula. The LLM only narrates what it's given, and every memo number is traceable back to a structured fact pack. It runs offline with a mock provider, gracefully falls back when free APIs aren't available, and writes an audit log on every run. It's ready for a B2G review room because it was designed to be auditable from the first line of code."

---

## Fallback talking points

**Q: "Couldn't an LLM just compute these numbers directly?"**
> No — and we explicitly chose not to. LLMs hallucinate numbers. For B2G use, every number must be auditable, reproducible, and tied to a formula. The risk score has a versioned formula (`risk_formula_version: 1.0`) and seven weighted components logged in every audit entry. The LLM never computes, never ranks, never invents. It only narrates.

**Q: "What if the Gemini API goes down mid-cycle?"**
> The agent falls back to the mock provider, completes the run, and records `fallback_used: true` with a `fallback_reason` in the audit log. There are three fallback layers: construction-time (missing key), call-time (HTTP failure), and grounding-time (ungrounded output). The PMU analyst always gets a memo, and the audit log always tells the truth about which provider produced it.

**Q: "Where's the real data?"**
> Synthetic, by design. This is a portfolio project — I don't have a DPIA, an MoU, or production DIKSHA access, and I won't pretend I do. The data generator engineers realistic pathologies (duplicate school IDs, future-dated issues, orphan records) so the data quality scorer and risk model find real things. The schema is shaped to accept real aggregated state data later without changing the agent.

---

## Interview explanation

A 3-4 sentence version you can deliver in an AI/PM interview:

> "I built a Monthly District Review Agent for Indian government education — the domain I want to work in. The design choice that matters most is that the LLM is bounded: a deterministic Python core computes every KPI and risk score, and the LLM only narrates a structured fact pack, with grounding checks that fail-closed to a mock provider when numbers don't trace. Engineering-wise it's 122 passing tests, four free LLM providers with three layers of fallback, and an audit log on every run. The portfolio differentiator is that it's built the way a B2G product should be built — auditable by construction, not auditable as an afterthought."
