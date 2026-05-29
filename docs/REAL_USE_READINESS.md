# Real-Use Readiness

> **Disclaimer.** ShikshaSignal AI is a demonstration project. The shipped CSVs
> under `data/synthetic/` are **synthetic and seeded**. This document is a
> **pilot guide** for moving cautiously toward a small, **aggregate-only** trial
> using real exports. It is **not** a production deployment plan. Before any
> real data is loaded, the PMU must complete an **explicit legal / privacy
> review** (DPDP-aligned) and obtain written authorisation from the program
> owner. When in doubt, stay on the synthetic generator.

---

## What this document is (and is not)

- This is **pilot guidance**, not a production deployment plan.
- It assumes a PMU analyst has a small set of **aggregate CSV exports** (state
  or district roll-ups) and wants to dry-run ShikshaSignal AI against them
  locally, with approvals.
- It is **not** a guide to live integration with DIKSHA, UDISE+, NISHTHA, NAS,
  Aadhaar, or APAAR APIs. No such adapter exists in this repo today.
- It complements [`SAFETY_AND_PRIVACY.md`](SAFETY_AND_PRIVACY.md),
  [`EVALUATION.md`](EVALUATION.md), and the [project README](../README.md).

---

## What real data is needed (the minimum useful aggregate set)

The pilot only needs **aggregate, school-level summaries** that map onto the
five CSVs declared in [`schemas/input_schemas.yaml`](../schemas/input_schemas.yaml).
Nothing in the table below is per-student or per-teacher PII.

| Project CSV | Grain | Realistic aggregate source a PMU usually has |
|---|---|---|
| `schools.csv` | one row per school | UDISE+ school-directory extract for the district (school metadata + enrolment + teachers_count + infra score) |
| `diksha_usage.csv` | school x ISO week | DIKSHA / state LMS **school-level** weekly roll-up (scans, sessions, minutes, active teachers, active-students-**proxy**) |
| `assessments.csv` | school x grade x subject x round | District assessment cell summary (baseline / midline / endline averages by school+grade+subject) |
| `teacher_training.csv` | one row per teacher | NISHTHA / state PD dashboard export of **completion %** by teacher and course — synthetic-style `teacher_id` only |
| `field_issues.csv` | one row per issue | District grievance / helpdesk log, redacted to issue_type + severity + status |

All five are tabular CSVs. No APIs. No live joins. No identifying free text.

---

## What data is not needed

- Per-student records (names, DOBs, per-child marks, per-child attendance).
- Per-teacher PII (real names, phone numbers, addresses, employee IDs).
- Granular daily / per-period attendance.
- Free-text WhatsApp or SMS messages.
- Per-device telemetry, IMEI, IP addresses, or browser fingerprints.
- Photos, videos, biometrics, or GPS traces.
- Anything finer than the school x week / school x assessment-round grain
  already in the schema.

If the export contains any of the above, **strip those columns before mapping**.

---

## What data must be avoided (the never list)

Pulled directly from the spirit of [`SAFETY_AND_PRIVACY.md`](SAFETY_AND_PRIVACY.md)
and the `forbidden_fields` list in [`schemas/input_schemas.yaml`](../schemas/input_schemas.yaml):

- No child-level PII of any kind.
- No Aadhaar, APAAR, EMIS, or any government student identifier.
- No real student names, real teacher names, or real parent contacts.
- No real phone numbers, postal addresses, or GPS coordinates.
- No scraped data and no unconsented data.
- No data sourced outside the documented data-sharing agreement.
- No paid or third-party LLM API calls on real data — `--llm-provider mock` is
  the default and stays the default during pilot.

---

## Required approvals (before any real data is used)

- [ ] Written authorisation from the program owner / PMU lead.
- [ ] A signed **data-sharing agreement** scoped to aggregate-only fields.
- [ ] Documented **retention period** (e.g. "delete 30 days after pilot end").
- [ ] Documented **deletion plan** at end of pilot, with owner.
- [ ] A **named data steward** on the PMU side accountable for the CSVs.
- [ ] Alignment with **DPDP / state data-protection guidance** (legal review on file).

**When in doubt, do NOT load the data. Stay synthetic.**

---

## Aggregate-data-only pilot recommendation

- **Scope:** 1 state, 1-2 districts, 1 period (last completed month).
- **Granularity:** school-level aggregates only.
- **Duration:** 4-6 weeks.
- **Definition of success:** the PMU lead signs off that the generated review
  memo matches what they would have produced manually for that district / month,
  modulo wording.

---

## Suggested pilot scope (concrete CSV row counts)

Pilot scale should stay close to the synthetic demo scale. Upper bounds:

| File | Upper bound (rows) |
|---|---|
| `schools.csv` | <= 500 |
| `diksha_usage.csv` | <= 4,000 |
| `assessments.csv` | <= 2,500 |
| `teacher_training.csv` | <= 3,000 |
| `field_issues.csv` | <= 600 |

If a district is larger than this, sub-sample to one or two blocks for the
pilot. Bigger is not better here — speed of human review is the bottleneck.

---

## CSV-first pilot workflow

1. **Map** real exports to ShikshaSignal columns using the mapping template
   at `docs/templates/real_data_mapping_template.csv` (see
   [How to use the mapping template](#how-to-use-the-mapping-template)).
2. **Place** the mapped CSVs in `data/synthetic/` for the pilot. That
   directory is local-only and `.gitignored`, and the loader already reads
   from it.
3. Run:
   ```
   python -m app.tools.import_validator
   ```
4. Open `outputs/import_validation_report.md` and resolve every **ERROR**.
   Re-run until the verdict is **"Ready"** or **"Ready with warnings"**.
5. Run:
   ```
   python -m app.review --district "<District>" --period <YYYY-MM> --llm-provider mock
   ```
6. Hand the generated `outputs/monthly_district_review.md` + `action_tracker.csv`
   to the PMU lead for review and red-pen.
7. Iterate. Fix mappings, re-validate, re-render.

For optional visual review:
```
python -m streamlit run frontend/streamlit_app.py
```

---

## Data retention considerations

- **Local-only by default.** No cloud uploads, no remote LLM calls (mock
  provider), no telemetry.
- `.gitignore` already excludes `data/synthetic/` and `outputs/`. **Never
  commit** real CSVs or generated memos.
- **Delete** the pilot CSVs at the end of the pilot, as committed to in the
  data-sharing agreement. The data steward owns this step.
- **Keep** `outputs/audit_log.json` for traceability of which review ran on
  which data, but redact district / file names if the audit log is shared
  outside the PMU.

---

## Stakeholder checklist

| Role | Responsibility | Artifact they own |
|---|---|---|
| PMU Lead | Authorises pilot; signs off success criteria | Authorisation memo + final go/no-go |
| District Education Officer (DEO) | Validates that findings reflect ground reality | Annotated `monthly_district_review.md` |
| Data Steward | Curates, anonymises, stores, and deletes the CSVs | Data-sharing agreement + deletion log |
| Privacy / Legal | DPDP-aligned review of scope and retention | Legal sign-off note |
| Block Resource Coordinator (BRC/CRC) | Field-verifies hypotheses flagged in the memo | Action-tracker updates with field notes |

---

## Security and governance checklist

- Aggregate-only data scope explicit in the data-sharing agreement.
- No LLM calls outside the user's machine for any provider — `mock` by
  default; local Ollama only if pre-approved.
- `outputs/audit_log.json` reviewed at the end of every run (provider,
  fallback, grounding failures, files read).
- Retention period documented **and enforced** (calendar reminder + steward).
- A one-pager prepared for the PMU lead summarising what the system did and
  did not do for the pilot month.

---

## How to use the mapping template

The template lives at `docs/templates/real_data_mapping_template.md` (human
guide) and `docs/templates/real_data_mapping_template.csv` (machine-readable
mapping). Fill one row per source column: list the source file, source column,
the corresponding ShikshaSignal CSV + column, the transform rule (rename,
recode, unit conversion), and any redactions applied. Anything that cannot be
mapped to an existing ShikshaSignal column is dropped — the schema does not
grow during a pilot.

---

## How to run import validation

```
python -m app.tools.import_validator
```

Expected output: a markdown report at `outputs/import_validation_report.md`
and a machine-readable copy at `outputs/import_validation_report.json`. The
**verdict line** at the top tells the analyst whether the data is `Ready`,
`Ready with warnings`, or `Not ready`. Do not run `app.review` until the
verdict is at least `Ready with warnings`.

---

## Final reminder

**This is a pilot toolkit, not a production system. Legal and privacy review
must happen before any real data is loaded onto a machine that runs this
project. Until that review is on file, stay on the synthetic generator
(`python scripts/generate_synthetic_data.py --seed 42`) and treat every
output as a demonstration only.**

See also: [`SAFETY_AND_PRIVACY.md`](SAFETY_AND_PRIVACY.md),
[`EVALUATION.md`](EVALUATION.md),
[`ROADMAP.md`](ROADMAP.md),
[`CASE_STUDY.md`](CASE_STUDY.md).
