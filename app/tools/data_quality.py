"""Deterministic data-quality assessment.

Produces (a) a human-readable report for the CLI/memo and (b) a per-school signal frame that
the risk engine consumes for its `data_availability` and `data_quality` components. Government
users trust a tool that is honest about what it *cannot* see, so coverage %, unmatched IDs, and
counted invalid rows are first-class outputs — not hidden.

Run:  python -m app.tools.data_quality
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.config import REFERENCE_DATE, STALE_DAYS
from app.tools.csv_loader import Tables, load_all

_REF = pd.Timestamp(REFERENCE_DATE)
_STALE_CUTOFF = _REF - pd.Timedelta(days=STALE_DAYS)


@dataclass
class DataQualityReport:
    findings: list[dict] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    reconciliation: dict = field(default_factory=dict)
    per_school: pd.DataFrame = field(default_factory=pd.DataFrame)
    data_quality_score: int = 100
    weeks_expected: int = 0
    latest_week: str | None = None

    def add(self, check: str, severity: str, count: int, detail: str, penalty: float) -> None:
        if count > 0:
            self.findings.append(
                {"check": check, "severity": severity, "count": int(count),
                 "detail": detail, "penalty": round(penalty, 1)}
            )


def _reconcile(fact: pd.DataFrame, valid_ids: set[str], label: str) -> dict:
    refs = fact["school_id"]
    unmatched_mask = ~refs.isin(valid_ids)
    unmatched_ids = sorted(refs[unmatched_mask].unique().tolist())
    return {
        "table": label,
        "rows": int(len(fact)),
        "matched_rows": int((~unmatched_mask).sum()),
        "unmatched_rows": int(unmatched_mask.sum()),
        "unmatched_ids": unmatched_ids,
    }


def assess_quality(tables: Tables) -> DataQualityReport:
    rep = DataQualityReport()
    schools = tables.schools
    schools_dim = tables.schools_dedup
    valid_ids = set(schools_dim["school_id"])
    rep.weeks_expected = len(tables.weeks)
    rep.latest_week = tables.latest_week

    # ---- Coverage: % of schools reporting DIKSHA usage in the latest week --------------
    reporting_latest = set(
        tables.diksha_usage.loc[tables.diksha_usage["week"] == rep.latest_week, "school_id"]
    ) & valid_ids
    total = len(valid_ids)
    rep.coverage = {
        "latest_week": rep.latest_week,
        "schools_total": total,
        "schools_reporting": len(reporting_latest),
        "coverage_pct": round(100 * len(reporting_latest) / total, 1) if total else 0.0,
    }
    missing_latest = valid_ids - reporting_latest
    rep.add("missing_latest_week_usage", "warning", len(missing_latest),
            f"{len(missing_latest)} schools have no DIKSHA usage row for {rep.latest_week}",
            penalty=1.0 * len(missing_latest))

    # ---- ID reconciliation across fact tables ------------------------------------------
    rep.reconciliation = {
        "diksha_usage": _reconcile(tables.diksha_usage, valid_ids, "diksha_usage"),
        "assessments": _reconcile(tables.assessments, valid_ids, "assessments"),
        "teacher_training": _reconcile(tables.teacher_training, valid_ids, "teacher_training"),
        "field_issues": _reconcile(tables.field_issues, valid_ids, "field_issues"),
    }
    total_unmatched = sum(r["unmatched_rows"] for r in rep.reconciliation.values())
    rep.add("unmatched_school_ids", "error", total_unmatched,
            "fact rows reference school_ids absent from the schools directory (ID mismatch)",
            penalty=2.0 * total_unmatched)

    # ---- Duplicate keys ----------------------------------------------------------------
    dup_schools = int(schools["school_id"].duplicated().sum())
    rep.add("duplicate_school_id", "error", dup_schools,
            "duplicate school_id rows in schools.csv", penalty=3.0 * dup_schools)
    dup_teachers = int(tables.teacher_training["teacher_id"].duplicated().sum())
    rep.add("duplicate_teacher_id", "error", dup_teachers,
            "duplicate teacher_id rows", penalty=3.0 * dup_teachers)

    # ---- Invalid values ----------------------------------------------------------------
    tt = tables.teacher_training
    bad_completion = tt[(tt["completion_percent"] > 100) | (tt["completion_percent"] < 0)]
    rep.add("invalid_completion_percent", "error", len(bad_completion),
            "teacher_training.completion_percent outside 0-100", penalty=1.5 * len(bad_completion))

    blank_scores = tables.assessments["current_score"].isna().sum()
    rep.add("missing_assessment_score", "warning", int(blank_scores),
            "assessment rows with a blank current_score", penalty=0.5 * int(blank_scores))

    bad_enrollment = int((schools_dim["enrollment"] <= 0).sum())
    rep.add("nonpositive_enrollment", "error", bad_enrollment,
            "schools with enrollment <= 0", penalty=2.0 * bad_enrollment)

    # Future-dated field issues (created_at after 'today').
    created = pd.to_datetime(tables.field_issues["created_at"], errors="coerce")
    future_issues = int((created > _REF).sum())
    rep.add("future_dated_issue", "error", future_issues,
            f"field_issues with created_at after {REFERENCE_DATE.isoformat()}",
            penalty=2.0 * future_issues)

    # Stale teacher-training records (no activity for > STALE_DAYS).
    last_act = pd.to_datetime(tt["last_activity_date"], errors="coerce")
    stale = int((last_act < _STALE_CUTOFF).sum())
    rep.add("stale_training_record", "info", stale,
            f"teacher_training records with no activity since {_STALE_CUTOFF.date()}",
            penalty=0.1 * stale)

    # Abnormal: active_teachers exceeding the school's teacher count.
    du = tables.diksha_usage.merge(
        schools_dim[["school_id", "teachers_count"]], on="school_id", how="left"
    )
    abnormal = int((du["active_teachers"] > du["teachers_count"].fillna(1e9)).sum())
    rep.add("active_teachers_gt_count", "warning", abnormal,
            "DIKSHA active_teachers exceeds the school's teacher count", penalty=0.5 * abnormal)

    # ---- Per-school signal frame (consumed by risk_score) ------------------------------
    rep.per_school = _per_school_signals(tables, valid_ids)

    # ---- Blended data-quality score (transparent, capped penalties) --------------------
    total_penalty = min(100.0, sum(f["penalty"] for f in rep.findings))
    rep.data_quality_score = int(round(100 - total_penalty))
    return rep


def _per_school_signals(tables: Tables, valid_ids: set[str]) -> pd.DataFrame:
    schools_dim = tables.schools_dedup
    weeks_expected = len(tables.weeks)
    latest_week = tables.latest_week

    du = tables.diksha_usage[tables.diksha_usage["school_id"].isin(valid_ids)]
    weeks_reported = du.groupby("school_id")["week"].nunique()
    reporting_latest = set(du.loc[du["week"] == latest_week, "school_id"])

    assess = tables.assessments
    has_assessment = (
        assess[assess["current_score"].notna()].groupby("school_id").size()
    )

    tt = tables.teacher_training
    invalid_completion = (
        tt[(tt["completion_percent"] > 100) | (tt["completion_percent"] < 0)]
        .groupby("school_id").size()
    )
    blank_scores = assess[assess["current_score"].isna()].groupby("school_id").size()

    rows = []
    for sid in schools_dim["school_id"]:
        wr = int(weeks_reported.get(sid, 0))
        rows.append(
            {
                "school_id": sid,
                "weeks_reported": wr,
                "weeks_expected": weeks_expected,
                "missing_latest_week": sid not in reporting_latest,
                "missing_usage_entirely": wr == 0,
                "missing_assessment": int(has_assessment.get(sid, 0)) == 0,
                "dq_invalid_count": int(invalid_completion.get(sid, 0)) + int(blank_scores.get(sid, 0)),
            }
        )
    return pd.DataFrame(rows)


def _print(rep: DataQualityReport) -> None:
    print("=" * 64)
    print("  ShikshaSignal AI - data quality report")
    print("=" * 64)
    c = rep.coverage
    print(f"  Data quality score : {rep.data_quality_score}/100")
    print(f"  Latest week        : {c['latest_week']}")
    print(f"  Coverage           : {c['schools_reporting']}/{c['schools_total']} "
          f"schools reporting ({c['coverage_pct']}%)")
    print("\n  Findings:")
    if not rep.findings:
        print("    (none)")
    for f in sorted(rep.findings, key=lambda x: -x["penalty"]):
        print(f"    [{f['severity']:<7}] {f['check']:<28} x{f['count']:<4} - {f['detail']}")
    print("\n  ID reconciliation (fact rows referencing the schools directory):")
    for r in rep.reconciliation.values():
        extra = f"  unmatched ids: {r['unmatched_ids']}" if r["unmatched_ids"] else ""
        print(f"    {r['table']:<18}: {r['matched_rows']}/{r['rows']} matched, "
              f"{r['unmatched_rows']} unmatched{extra}")


def main() -> None:
    _print(assess_quality(load_all()))


if __name__ == "__main__":
    main()
