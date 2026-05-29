"""Deterministic KPI calculation at school / block / district level.

Frames KPIs the way a review room reads them: actual vs target vs last-period. All arithmetic
lives here (never in an LLM). Weekly usage KPIs get a true period-over-period delta (latest vs
prior week); assessment/training KPIs are single-wave in the synthetic data, so their "prior"
is reported as N/A rather than faked.

Run:  python -m app.tools.kpi_calculator [--district "District Alpha"]
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import yaml

from app.config import DATA_DIR, FOCUS_DISTRICT
from app.tools.csv_loader import Tables, load_all

POLICY_MAP_PATH = DATA_DIR / "policy_map.yaml"

# Threshold on the 0-100 FLN score above which a child is counted "at grade level".
FLN_AT_GRADE_LEVEL = 50.0


def load_policy_targets() -> dict:
    """Return KPI targets. Prefers ``config/kpi_targets.yaml`` (Milestone 7);
    falls back to the legacy ``data/policy_map.yaml`` so older tests pass."""
    # Imported lazily to avoid a circular import with app.services.
    from app.services.config_loader import load_kpi_targets

    cfg = load_kpi_targets()
    if cfg.targets:
        return dict(cfg.targets)
    # Legacy direct read kept for environments without either config file.
    if not POLICY_MAP_PATH.exists():
        return {}
    with open(POLICY_MAP_PATH, "r", encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("targets", {})


def _safe_pct_change(latest: float, prior: float) -> float | None:
    if latest is None or pd.isna(latest):
        return None
    if prior is None or prior == 0 or pd.isna(prior):
        return None
    return round(100.0 * (latest - prior) / prior, 1)


def compute_school_kpis(tables: Tables) -> pd.DataFrame:
    """One row per school with the raw KPI metrics every other tool consumes."""
    schools = tables.schools_dedup
    valid_ids = set(schools["school_id"])
    latest, prior = tables.latest_week, tables.prior_week

    du = tables.diksha_usage[tables.diksha_usage["school_id"].isin(valid_ids)]
    reported_latest_ids = set(du.loc[du["week"] == latest, "school_id"])

    # ---- DIKSHA usage (weekly, with period-over-period) --------------------------------
    sess_latest = du[du["week"] == latest].set_index("school_id")["sessions"]
    sess_prior = du[du["week"] == prior].set_index("school_id")["sessions"] if prior else pd.Series(dtype=float)
    sess_mean = du.groupby("school_id")["sessions"].mean()
    weeks_reported = du.groupby("school_id")["week"].nunique()
    # Mean over all weeks except the latest — the baseline a sharp drop is measured against.
    non_latest = du[du["week"] != latest]
    sess_prior_mean = non_latest.groupby("school_id")["sessions"].mean()

    # ---- Teacher training (exclude invalid >100 / <0 from the KPI) ---------------------
    tt = tables.teacher_training[tables.teacher_training["school_id"].isin(valid_ids)].copy()
    valid_tt = tt[(tt["completion_percent"] >= 0) & (tt["completion_percent"] <= 100)]
    completion_pct = valid_tt.groupby("school_id")["completion_percent"].mean()
    pct_completed = (
        tt.assign(done=(tt["status"] == "completed")).groupby("school_id")["done"].mean() * 100
    )

    # ---- FLN assessments ---------------------------------------------------------------
    asmt = tables.assessments[tables.assessments["school_id"].isin(valid_ids)].copy()
    asmt = asmt[asmt["current_score"].notna()]
    fln_prof = asmt.groupby("school_id")["current_score"].mean()
    asmt = asmt.assign(gain=asmt["current_score"] - asmt["baseline_score"])
    fln_gain = asmt.groupby("school_id")["gain"].mean()
    at_grade = (
        asmt.assign(ok=asmt["current_score"] >= FLN_AT_GRADE_LEVEL)
        .groupby("school_id")["ok"].mean() * 100
    )

    # ---- Field issues ------------------------------------------------------------------
    fi = tables.field_issues[tables.field_issues["school_id"].isin(valid_ids)].copy()
    fi_open = fi[fi["status"] != "resolved"]
    open_issues = fi_open.groupby("school_id").size()
    open_high = fi_open[fi_open["severity"] == "high"].groupby("school_id").size()
    open_critical = fi_open[fi_open["severity"] == "critical"].groupby("school_id").size()

    df = schools[["school_id", "state", "district", "block", "cluster",
                  "internet_available", "device_available", "infrastructure_score",
                  "enrollment", "teachers_count"]].copy()

    def col(series, default=0.0):
        return df["school_id"].map(series).fillna(default)

    # Missing latest-week row => NaN (NOT 0). "Data not reported" must never look like
    # "zero usage" — that would distort rankings and decliner detection.
    df["sessions_latest"] = col(sess_latest, default=np.nan)
    df["reported_latest"] = df["school_id"].isin(reported_latest_ids)
    df["sessions_prior"] = col(sess_prior, default=np.nan)
    df["sessions_mean"] = col(sess_mean)
    df["sessions_prior_mean"] = col(sess_prior_mean, default=np.nan)
    df["sessions_wow_pct"] = [
        _safe_pct_change(l, p) for l, p in zip(df["sessions_latest"], df["sessions_prior"])
    ]
    df["weeks_reported"] = col(weeks_reported).astype(int)
    df["training_completion_pct"] = col(completion_pct, default=np.nan)
    df["pct_completed"] = col(pct_completed, default=np.nan)
    df["fln_proficiency"] = col(fln_prof, default=np.nan)
    df["fln_gain"] = col(fln_gain, default=np.nan)
    df["fln_at_grade_pct"] = col(at_grade, default=np.nan)
    df["open_issues"] = col(open_issues).astype(int)
    df["open_high"] = col(open_high).astype(int)
    df["open_critical"] = col(open_critical).astype(int)
    return df


def aggregate(school_kpis: pd.DataFrame, by: str = "district") -> pd.DataFrame:
    """Roll school KPIs up to block or district level (simple, transparent group means/sums)."""
    agg = school_kpis.groupby(by).agg(
        schools=("school_id", "nunique"),
        sessions_latest=("sessions_latest", "mean"),
        sessions_mean=("sessions_mean", "mean"),
        training_completion_pct=("training_completion_pct", "mean"),
        fln_proficiency=("fln_proficiency", "mean"),
        fln_gain=("fln_gain", "mean"),
        fln_at_grade_pct=("fln_at_grade_pct", "mean"),
        open_issues=("open_issues", "sum"),
        open_critical=("open_critical", "sum"),
    ).round(1)
    return agg.reset_index()


def _status(actual: float, target: float, direction: str) -> str:
    if actual is None or pd.isna(actual):
        return "N/A"
    if direction == "higher_is_better":
        return "on track" if actual >= target else "below target"
    return "on track" if actual <= target else "above target"


def district_summary(tables: Tables, district: str = FOCUS_DISTRICT) -> dict:
    """Target-vs-actual summary for one district, plus a usage period-over-period delta."""
    kpis = compute_school_kpis(tables)
    targets = load_policy_targets()
    d = kpis[kpis["district"] == district]
    n = d["school_id"].nunique()

    # Usage coverage = share of schools with a reported latest-week row (matches the DQ tool).
    reporting_latest = round(100 * d["reported_latest"].mean(), 1) if n else 0.0
    coverage = reporting_latest

    actuals = {
        "diksha_sessions_per_school_weekly": round(d["sessions_latest"].mean(), 1),
        "teacher_training_completion_pct": round(d["training_completion_pct"].mean(), 1),
        "fln_proficiency_pct": round(d["fln_at_grade_pct"].mean(), 1),
        "fln_gain_points": round(d["fln_gain"].mean(), 1),
        "open_critical_issues": int(d["open_critical"].sum()),
        "usage_coverage_pct": reporting_latest,
    }

    kpi_rows = []
    for key, spec in targets.items():
        actual = actuals.get(key)
        kpi_rows.append({
            "kpi": key,
            "label": spec.get("label", key),
            "actual": actual,
            "target": spec.get("target"),
            "direction": spec.get("direction"),
            "status": _status(actual, spec.get("target"), spec.get("direction", "higher_is_better")),
            "source": spec.get("source"),
        })

    # District-wide weekly usage delta (latest vs prior week, mean per school).
    sess_latest_mean = round(d["sessions_latest"].mean(), 1)
    sess_prior_mean = round(d["sessions_prior"].mean(), 1)
    return {
        "district": district,
        "schools": n,
        "blocks": d["block"].nunique(),
        "coverage_pct": coverage,
        "kpis": kpi_rows,
        "usage_delta": {
            "latest_week": tables.latest_week,
            "prior_week": tables.prior_week,
            "sessions_latest_mean": sess_latest_mean,
            "sessions_prior_mean": sess_prior_mean,
            "wow_pct": _safe_pct_change(sess_latest_mean, sess_prior_mean),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a district KPI summary.")
    parser.add_argument("--district", default=FOCUS_DISTRICT)
    args = parser.parse_args()

    tables = load_all()
    s = district_summary(tables, args.district)

    print("=" * 70)
    print(f"  ShikshaSignal AI - KPI summary: {s['district']}")
    print(f"  {s['schools']} schools across {s['blocks']} blocks | usage coverage {s['coverage_pct']}%")
    print("=" * 70)
    print(f"  {'KPI':<42}{'Actual':>9}{'Target':>9}  Status")
    print("  " + "-" * 66)
    for k in s["kpis"]:
        actual = "N/A" if k["actual"] is None or pd.isna(k["actual"]) else f"{k['actual']}"
        print(f"  {k['label'][:42]:<42}{actual:>9}{str(k['target']):>9}  {k['status']}")
    ud = s["usage_delta"]
    wow = "N/A" if ud["wow_pct"] is None else f"{ud['wow_pct']:+}%"
    print("  " + "-" * 66)
    print(f"  Weekly usage {ud['prior_week']} -> {ud['latest_week']}: "
          f"{ud['sessions_prior_mean']} -> {ud['sessions_latest_mean']} sessions/school ({wow})")
    print("\n  (Targets sourced from data/policy_map.yaml; all KPIs computed deterministically.)")


if __name__ == "__main__":
    main()
