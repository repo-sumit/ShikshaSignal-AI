# Evaluation

> ⚠️ **Synthetic data only.** ShikshaSignal AI runs entirely on a synthetic, DIKSHA-like dataset generated locally. No real student, teacher, school, Aadhaar, or APAAR data is used anywhere in the test suite. The evaluation here measures the *engineering correctness* of a demo system, not the quality of any real-world deployment.

## Why evaluation matters here

Government reviewers cannot accept "the AI said so."

A District Magistrate or State Project Director reading a monthly review needs every numeric claim to be hand-recomputable from the underlying tables. A memo that quotes "FLN dropped 4.2 points in Madhopur block" is only useful if a reviewer can open `outputs/review_facts.json`, find that 4.2, and trace it back to a KPI row computed from synthetic DIKSHA-like data.

The **grounding eval** is therefore the load-bearing trust signal of this project. Everything else — KPI determinism, risk-score reproducibility, provider fallback — exists to make that grounding check meaningful. If an LLM can sneak an uncited number into the memo, the system has failed regardless of how good the prose reads.

## Test surface

Each file below is one cohesive slice of behaviour. Run `pytest -q` to execute them all.

| Test file | What it verifies |
| --- | --- |
| `tests/test_data_generation.py` | Synthetic generator: planted pathologies (duplicate school IDs, >100% completion, future-dated issues, orphan IDs), reproducibility under a fixed seed, hierarchy counts (1 state / 2 districts / 8 blocks / ~160 schools / 8 ISO weeks). |
| `tests/test_data_quality.py` | DQ checks actually find the planted bad rows; coverage percentages are computed honestly; missing-week detection works. |
| `tests/test_kpi_calculator.py` | KPI table shape; honest `NaN`-vs-`0` distinction; target-vs-actual deltas; DIKSHA usage week-over-week delta. |
| `tests/test_risk_score.py` | Risk model is deterministic; band split lands within the ~55 / 30 / 15 tolerance; component contributions sum back to the headline score. |
| `tests/test_review_compiler.py` | All four artifacts written (`monthly_district_review.md`, `action_tracker.csv`, `audit_log.json`, `review_facts.json`); every memo section present; audit lineage populated. |
| `tests/test_grounding.py` | Happy-path grounding (zero ungrounded tokens) plus three adversarial injections. The load-bearing eval. |
| `tests/test_llm_factory.py` | Provider resolution; missing-credentials fall back to `MockLLM`; `ProviderResolution` records the requested-vs-actual provider. |
| `tests/test_llm_providers.py` | Gemini / Groq / Ollama with mocked HTTP — happy paths, HTTP error paths, empty-response paths. No real network calls. |
| `tests/test_review_with_llm_fallback.py` | End-to-end fallback scenarios: factory-time, call-time HTTP error, grounding-time. |
| `tests/test_artifact_reader.py` | Defensive Streamlit readers — missing files, empty files, malformed JSON all degrade gracefully. |
| `tests/test_review_service.py` | `run_review()` public contract: signature, return type (`ReviewArtifacts`), idempotency under a frozen timestamp. |
| `tests/test_demo_script.py` | `scripts/run_local_demo.py` end-to-end + `scripts/ingest_policy_docs.py` validates `data/policy_map.yaml`. |

## Deterministic reproducibility

The core data pipeline is bit-for-bit reproducible:

- Same seed → byte-identical CSVs from `scripts/generate_synthetic_data.py --seed 42`.
- Same seed + same `run_review(...)` arguments + a frozen `timestamp` → byte-identical `monthly_district_review.md`, `action_tracker.csv`, and `review_facts.json`.

`audit_log.json` deliberately carries a wall-clock timestamp by default, so it varies run-to-run; tests pin the timestamp to assert exact-equality where it matters.

This determinism is what lets a reviewer rerun the pipeline a month later and confirm a memo was not silently edited.

## Risk score tests (deterministic)

The risk model lives in `app/config.py` (`RISK_WEIGHTS`, `RISK_BANDS`) and `app/tools/risk_score.py`. Tests check:

- **Recomputability.** Given the KPI inputs, each school's composite score is recomputed from the documented weights and asserted to the third decimal.
- **Band split.** Across all ~160 synthetic schools the Low / Medium / High split lands within tolerance of the ~55 / 30 / 15 target. This is a synthetic-data property, not a real-world claim.
- **Component contributions.** Each of the seven components (learning_outcome 0.25, digital_usage 0.20, teacher_training 0.15, infrastructure 0.15, field_issue 0.10, data_availability 0.10, data_quality 0.05) contributes the weighted amount it claims to. The headline score equals the weighted sum.

`risk_formula_version = 1.0` is stamped into every `audit_log.json` so a future model change cannot be confused with an old one.

## Provider fallback tests

Three layers of fallback exist; each is exercised directly.

| Layer | Trigger | Test path |
| --- | --- | --- |
| Factory-time | `GOOGLE_API_KEY` missing, `groq` package not installed, etc. | `tests/test_llm_factory.py` |
| Call-time | The provider raises an HTTP error or returns an empty string mid-run. | `tests/test_llm_providers.py` and `tests/test_review_with_llm_fallback.py` |
| Grounding-time | Provider returns text but the rendered section contains a number that is not in `review_facts.json`. | `tests/test_review_with_llm_fallback.py` and `tests/test_grounding.py` |

Every fallback path is verified to record `fallback_used`, `fallback_reason`, the requested provider, and the actual provider into `audit_log.json` (plus per-section metadata in `audit_log.section_metadata`). Tests inspect the JSON directly — fallbacks are not allowed to "succeed quietly."

## Grounding tests (the load-bearing eval)

`app/eval/grounding.py` extracts every numeric token from the rendered memo (using a word-boundary-aware regex so school IDs like `D01_B03` are not mis-tokenised) and requires each one to appear inside `review_facts.json` or in a tiny pre-justified allowlist (`{0, 1, 2, 100}`, where `100` is the documented risk-scale max).

Three adversarial injections are tested in `tests/test_grounding.py`:

1. **Raw integer injection.** Append `"Fabricated stat: students reached 987654."` to the memo and assert that `987654` shows up in the ungrounded list.
2. **Fractional injection.** Append `"FLN went up by 42.42% this period."` and assert that `42.42` is caught (the `%` is stripped by the normaliser, so it does not "hide" the number).
3. **Runtime monkey-patched provider.** Patch `MockLLM.generate_section` so the `executive_summary` section returns its real text plus `"Independent estimate: 7777 students at risk."`, run the full compiler end-to-end, and assert that `7777` lands in the ungrounded set.

The third path is the realistic failure mode — a real LLM, somewhere in the future, hallucinates a number into one section. The grounding eval catches it from the rendered memo, the section falls back to `MockLLM`, and `audit_log.json` records the failure.

## Adversarial numeric injection (worked example)

Imagine a Gemini call returns the prose:

> "Of the schools surveyed, 13.7 percent show a learning gap in literacy."

The literal token `13.7` does not appear anywhere in `review_facts.json` (the real value computed by the deterministic core was, say, `14.2`). What happens, step by step:

1. The renderer drops the Gemini text into the section.
2. `check_grounding(memo, facts)` returns `["13.7"]`.
3. `app/review.py` sees a non-empty grounding-failure list for that section and re-renders the section with `MockLLM`, which only emits numbers from the facts dict.
4. `audit_log.json` records:
   - `grounding_failures.executive_summary = ["13.7"]`
   - `section_metadata.executive_summary.fallback_used = true`
   - `section_metadata.executive_summary.fallback_reason = "grounding_failure"`
5. If the run was launched with `--strict-grounding`, the entire memo is re-rendered with `MockLLM` (not just the offending section) and the audit log marks the whole run as `fallback_used = true`.

The reviewer can open the audit log, see the hallucination, and trust the published memo because the offending section was replaced before write.

## Why this matters for B2G / government contexts

Audit trails are the difference between adoption and rejection.

- A District Magistrate cannot defend a decision upward if the numbers in a memo came from "the AI". They can defend a decision if they can point at `review_facts.json`, recompute the KPIs from the raw tables, and show the same value.
- A state-level reviewer reviewing twelve districts needs the *same* trust contract for every memo. Grounding is the property that scales across districts without manual fact-checking.
- A regulator auditing the system after the fact can replay a run from the synthetic seed and the audit-logged args, and confirm nothing was edited.

The grounding eval is what makes the system "boring" in the right way — boring is the goal for government tooling.

## Current test count

**122 tests passing** as of Milestone 6 (latest `pytest -q` run). M6 added 15 tests covering the local demo runner and the policy YAML validator; earlier milestones contribute the rest. The count is reproducible — same code + same seed always yields the same number. Run `pytest -q` to confirm.

## How to run tests

```bash
pytest -q
```

Tests do **not** require:

- a real Gemini, Groq, or OpenAI API key,
- network access,
- a running Ollama daemon,
- the Streamlit binary on `PATH`.

All three free/local LLM providers are monkeypatched at the HTTP seam (see `tests/test_llm_providers.py`). The default provider — `MockLLM` — runs entirely offline using deterministic Jinja templates, so even the end-to-end review tests are hermetic.

## Future evaluation work (clearly future, not present)

These are deliberately **not** implemented yet. They are listed so reviewers can see where the eval roadmap goes:

- **Golden memo diffing.** Snapshot a known-good `monthly_district_review.md` per seed and diff against it on every commit.
- **LLM output quality scoring.** Today we only check grounding; we do not score whether Gemini/Groq prose is actually better than the mock baseline.
- **Per-section grounding rubrics.** Today the rule is uniform across sections; in future, "root cause hypotheses" might allow softer numeric constraints than "executive summary."
- **Multi-period regression tests.** Running the same district across consecutive periods and asserting that month-over-month deltas line up with the KPI table.
- **Retrieval evaluation.** When deterministic policy lookup is upgraded to a real RAG step (deliberately deferred per `plan.md` §5), recall@k and faithfulness metrics will need their own test surface.

See also: [`README.md`](../README.md) for the project overview, [`docs/CASE_STUDY.md`](CASE_STUDY.md) for the end-to-end narrative, and `plan.md` for the original scoping decisions.
