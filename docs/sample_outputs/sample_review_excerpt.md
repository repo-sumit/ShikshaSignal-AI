# Sample Review Excerpt (Synthetic — Documentation Only)

> **Synthetic sample excerpt for documentation only.**
> This is a curated slice of an actual run of
> `python -m app.review --district "District Alpha" --period 2026-05 --llm-provider mock`,
> kept here so reviewers can see the shape of the output without running the
> pipeline themselves. All names, numbers, and findings are entirely synthetic
> and reflect generator settings — they are not real records.

---

# Monthly District Review — District Alpha, Pradesh North | Period 2026-05

> ⚠ **SYNTHETIC DATA.** This memo was generated entirely from synthetic, public-safe data.
> No real student, teacher, school, or district information is used. Numbers are
> deterministic for a fixed random seed.

## Executive Summary

District Alpha review for period 2026-05 covers 120 schools across 6 blocks. Usage
reporting coverage is 92.5%, district health score is 40/100, and the data-quality
score is 46/100. Of the schools scored, 12% are High risk, 38% Medium, and 50% Low.
The block requiring the most attention is District Alpha / Madhopur (mean risk 68.4,
9 schools in the High band).

## District Health Score

**Health score: 40/100** (weighted blend of target attainment, data quality, and risk
band mix; see `outputs/audit_log.json` for the formula version).

## KPI Snapshot (target vs actual)

| KPI                                       | Actual | Target | Status        | Source                                       |
| ----------------------------------------- | -----: | -----: | ------------- | -------------------------------------------- |
| Avg weekly DIKSHA sessions per school     |   34.5 |     50 | below target  | Digital Learning Adoption Guideline          |
| Teacher training completion               |   42.7 |     80 | below target  | Teacher Training Circular 2025 (NISHTHA/FLN) |
| FLN proficiency (children at grade level) |   11.3 |     60 | below target  | NIPUN Bharat Mission                         |
| FLN improvement (baseline to endline)     |    5.5 |     12 | below target  | NIPUN Bharat / FLN Goals                     |
| Open critical field issues                |     10 |      0 | above target  | District Review Circular                     |
| Usage reporting coverage                  |   92.5 |     90 | on track      | District Review Circular                     |

## Top Risky Blocks

| Rank | Block                       | Mean risk | Band   | High-risk schools |
| ---: | --------------------------- | --------: | ------ | ----------------: |
|    1 | District Alpha / Madhopur   |      68.4 | Medium |                 9 |
|    2 | District Alpha / Bhojpur    |      39.8 | Low    |                 2 |
|    3 | District Alpha / Kheda      |      37.4 | Low    |                 2 |

## Root-Cause Hypotheses

- **Hypothesis (D01_B03_C0_S08 in District Alpha / Sundarpur):** Weak FLN improvement
  and below-target proficiency suggest gaps in foundational pedagogy.
  _Evidence: learning_outcome=86.5; digital_usage=97.7; teacher_training=100.0;
  infrastructure=98.0; field_issue=73.0; data_availability=12.5; data_quality=0.0_
- **Hypothesis (D01_B01_C0_S00 in District Alpha / Kheda):** Weak FLN improvement and
  below-target proficiency suggest gaps in foundational pedagogy.
  _Evidence: learning_outcome=86.1; digital_usage=95.3; teacher_training=90.7;
  infrastructure=91.0; field_issue=44.0; data_availability=25.0; data_quality=0.0_

> Every hypothesis is labelled **Hypothesis** intentionally. These explain a pattern
> in the data and require **field verification** before being treated as causal.

## Assumptions and Limitations

This memo was generated from SYNTHETIC, public-safe data (see disclaimer above).
Numbers are deterministic for a fixed seed. The risk score follows model v1.0 with
weights documented in the audit log. Root causes are labelled hypotheses and require
field verification. Policy targets are loaded from `data/policy_map.yaml`. The LLM
provider for this run was mock.

---

**End of excerpt.** The full memo also contains "What Changed Since Last Period",
"Top Risky Schools" (with full per-component breakdown), "Data Quality Warnings",
"Policy-Linked Observations", "Recommended Actions", draft stakeholder messages, and
review meeting questions. Run the demo to see all sections.
