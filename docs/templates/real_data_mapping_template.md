# Real-Data Mapping Template

> **Disclaimer:** This template is for **aggregate, public-safe data only**, and only after the formal approvals listed in [docs/REAL_USE_READINESS.md](../REAL_USE_READINESS.md) have been granted. Never map per-student, per-teacher, Aadhaar/APAAR, phone-number, or GPS-level fields into ShikshaSignal AI. ShikshaSignal AI ships with **synthetic data by default**; real data is loaded only after readiness is signed off.

## Purpose

This document is the human-readable companion to [`docs/templates/real_data_mapping_template.csv`](real_data_mapping_template.csv). It explains how a PMU analyst should record the mapping between an existing aggregate export (DIKSHA dashboard pull, NISHTHA report, district MIS extract, etc.) and the ShikshaSignal AI CSV schema defined in [`schemas/input_schemas.yaml`](../../schemas/input_schemas.yaml). The CSV template uses **one row per ShikshaSignal target column**, so that every field the pipeline expects is explicitly accounted for — including the ones your source system does not yet provide.

## How to fill it in

1. Open [`docs/templates/real_data_mapping_template.csv`](real_data_mapping_template.csv) in your spreadsheet tool of choice.
2. For each row, fill in the source columns from your aggregate export (source system, source file name, source column name).
3. Document any **transformation** needed to get from the source value to the ShikshaSignal column — e.g., rename, cast to int, convert minutes-to-hours, aggregate per ISO week, or roll up to the school level.
4. **Leave the row empty if the column is not available in your export.** The import validator (`python -m app.tools.import_validator`) will then warn you when the field is missing from the generated CSV, so missing data is surfaced loudly rather than silently filled with zeros.
5. Save the filled template **alongside the data-sharing agreement**, NOT in this repository. The mapping may carry names of internal source systems and PMU staff, and should be treated as controlled documentation.

## Column-by-column fields

| Column | Meaning |
|---|---|
| `source_system` | Name of the system the export came from (e.g., `DIKSHA aggregate export`, `NISHTHA dashboard`, `District MIS`). |
| `source_file` | Actual filename you received from the source system (e.g., `diksha_school_summary_2026_04.csv`). Helps future analysts trace lineage. |
| `source_column` | The exact column header in the source file. Preserve casing — it matters for ETL scripts. |
| `target_file` | Which ShikshaSignal CSV the value lands in. One of: `schools.csv`, `diksha_usage.csv`, `assessments.csv`, `teacher_training.csv`, `field_issues.csv`. |
| `target_column` | The ShikshaSignal column name, exactly as defined in [`schemas/input_schemas.yaml`](../../schemas/input_schemas.yaml). |
| `transformation` | The step needed to get from source value to target value: `rename`, `cast to int`, unit conversion (`seconds -> minutes`), aggregation (`daily -> ISO week`), or composite (`rename + cast + clip`). |
| `required` | `yes` / `no` — taken from `schemas/input_schemas.yaml`. Required fields must be populated for the review to run. |
| `owner` | Who on the PMU side can answer questions about this field (role, not personal phone). E.g., `District PMU analyst`, `State MIS cell`. |
| `validation_notes` | Range, enum values, nullability — e.g., `must be > 0`, `enum: baseline|midline|endline`, `ISO YYYY-Www`, `nullable when status != resolved`. |

## Example: filling out one row (worked example)

A fictional example for the `enrollment` column on `schools.csv`:

| Field | Value |
|---|---|
| `target_file` | `schools.csv` |
| `target_column` | `enrollment` |
| `source_system` | `DIKSHA aggregate export` |
| `source_file` | `diksha_school_summary_2026_04.csv` |
| `source_column` | `totalEnrolment` |
| `transformation` | `rename + cast to int` |
| `required` | `yes` |
| `owner` | `District PMU analyst` |
| `validation_notes` | `must be > 0; reject rows where source value is null or negative` |

All values above are illustrative — the real source column names will depend on the export your PMU receives.

## What to do AFTER mapping

- Run the import validator: `python -m app.tools.import_validator`. It will produce `outputs/import_validation_report.md` and `outputs/import_validation_report.json`.
- **Resolve every `ERROR` finding** before running the review. `WARN` findings should be triaged, but the review can still run.
- Keep the filled template stored **with the data-sharing agreement**, NOT in git. Treat it as controlled documentation.

## Reminders

> - **Aggregate only.** No per-student or per-teacher data ever enters ShikshaSignal AI. The schema deliberately aggregates students to `active_students_proxy`.
> - **Synthetic data is the default.** Only load real data once every checkbox in [docs/REAL_USE_READINESS.md](../REAL_USE_READINESS.md) is complete and signed.
> - See also: [docs/SAFETY_AND_PRIVACY.md](../SAFETY_AND_PRIVACY.md), [docs/CASE_STUDY.md](../CASE_STUDY.md), [docs/EVALUATION.md](../EVALUATION.md), [docs/ROADMAP.md](../ROADMAP.md).
