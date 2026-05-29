"""Risk rankings + "what changed since last week", written to CSV artifacts.

Joins the decomposed risk scores with KPI context, ranks schools and blocks, flags usage
"decliners" (latest week well below the school's recent mean — distinct from a seasonal dip),
and writes:
    outputs/risk_ranking.csv         (one row per school, full component breakdown + context)
    outputs/block_risk_ranking.csv   (block roll-up)

Run:  python -m app.tools.rankings [--district "District Alpha"]
"""

from __future__ import annotations

import argparse

import pandas as pd

from app.config import FOCUS_DISTRICT, OUTPUTS_DIR
from app.tools.csv_loader import Tables, load_all
from app.tools.kpi_calculator import compute_school_kpis
from app.tools.risk_score import COMPONENTS, compute_block_risk, compute_school_risk

# A "decliner" is a real drop, not noise: recent mean must be material and the latest week
# must fall well below it.
DECLINER_MIN_PRIOR_MEAN = 8.0
DECLINER_RATIO = 0.6


def build_school_ranking(tables: Tables) -> pd.DataFrame:
    risk = compute_school_risk(tables)
    kpis = compute_school_kpis(tables)
    names = tables.schools_dedup[["school_id", "school_name"]]

    ctx_cols = [
        "school_id", "sessions_latest", "reported_latest", "sessions_prior_mean",
        "sessions_wow_pct", "fln_gain", "fln_proficiency", "training_completion_pct",
        "open_issues", "open_critical", "weeks_reported", "enrollment",
    ]
    df = risk.merge(kpis[ctx_cols], on="school_id", how="left").merge(names, on="school_id", how="left")

    prior_mean = df["sessions_prior_mean"].fillna(0)
    df["drop_vs_recent_pct"] = [
        round(100 * (lat - pm) / pm, 1) if (pd.notna(lat) and pm and pm > 0) else None
        for lat, pm in zip(df["sessions_latest"], prior_mean)
    ]
    # A decliner must have REPORTED the latest week — a missing row is a data-coverage gap,
    # not a decline, and is surfaced separately by the data-quality tool.
    df["is_decliner"] = (
        df["reported_latest"].fillna(False)
        & (prior_mean >= DECLINER_MIN_PRIOR_MEAN)
        & (df["sessions_latest"] < DECLINER_RATIO * prior_mean)
    )
    df = df.sort_values("risk_score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    ordered = (
        ["rank", "school_id", "school_name", "district", "block", "cluster",
         "risk_score", "risk_band"]
        + COMPONENTS
        + ["sessions_latest", "sessions_prior_mean", "drop_vs_recent_pct", "is_decliner",
           "fln_gain", "fln_proficiency", "training_completion_pct",
           "open_issues", "open_critical", "weeks_reported", "enrollment",
           "top_drivers", "explanation", "risk_model_version"]
    )
    return df[ordered]


def whats_changed(school_ranking: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    decliners = school_ranking[school_ranking["is_decliner"]].copy()
    return decliners.sort_values("drop_vs_recent_pct").head(top)[
        ["school_id", "school_name", "block", "sessions_prior_mean", "sessions_latest",
         "drop_vs_recent_pct", "risk_band"]
    ]


def write_outputs(tables: Tables, outdir=OUTPUTS_DIR) -> dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    school = build_school_ranking(tables)
    block = compute_block_risk(compute_school_risk(tables))

    school_path = outdir / "risk_ranking.csv"
    block_path = outdir / "block_risk_ranking.csv"
    school.to_csv(school_path, index=False)
    block.to_csv(block_path, index=False)
    return {"risk_ranking": str(school_path), "block_risk_ranking": str(block_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and write risk rankings.")
    parser.add_argument("--district", default=None)
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    tables = load_all()
    paths = write_outputs(tables)
    school = build_school_ranking(tables)
    if args.district:
        school = school[school["district"] == args.district].reset_index(drop=True)

    print("=" * 72)
    print("  ShikshaSignal AI - rankings written")
    print("=" * 72)
    for label, path in paths.items():
        print(f"  {label:<20}: {path}")

    changed = whats_changed(school, top=args.top)
    print(f"\n  What changed - top usage decliners (latest week vs recent mean):")
    if changed.empty:
        print("    (no material decliners this week)")
    for _, r in changed.iterrows():
        print(f"    {r['drop_vs_recent_pct']:>7}%  {r['school_id']:<18} {r['block']:<28} "
              f"({r['sessions_prior_mean']:.0f} -> {r['sessions_latest']:.0f} sessions)")

    print(f"\n  Top {args.top} highest-risk schools:")
    for _, r in school.head(args.top).iterrows():
        print(f"    {r['risk_score']:5.1f} [{r['risk_band']:<6}] {r['school_id']:<18} "
              f"{r['block']:<26} | {r['explanation']}")


if __name__ == "__main__":
    main()
