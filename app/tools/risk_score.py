"""Decomposed, explainable risk scoring (risk model v1.0).

Each school gets seven 0-100 component risks (higher = worse), combined with the fixed weights
in `app.config.RISK_WEIGHTS` into a 0-100 score and a band. Nothing here is a black box: every
component maps from a raw, named metric, and each school carries the 2 drivers that contributed
most, with the underlying numbers. The score is deterministic and hand-recomputable.

Run:  python -m app.tools.risk_score [--district "District Alpha"] [--top 5]
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from app.config import (
    FLN_GAIN_FLOOR,
    FLN_GAIN_PER_POINT,
    FOCUS_DISTRICT,
    RISK_MODEL_VERSION,
    RISK_WEIGHTS,
    USAGE_SESSIONS_BENCHMARK,
    band_for_score,
)
from app.services.config_loader import RiskConfig, load_risk_config
from app.tools.csv_loader import Tables, load_all
from app.tools.data_quality import assess_quality
from app.tools.kpi_calculator import compute_school_kpis

# Component order is fixed by the in-code RISK_WEIGHTS dict; the YAML config just
# overrides the values. Tests verify the YAML and the in-code dict use the same keys.
COMPONENTS = list(RISK_WEIGHTS.keys())

# Cached lazily so we read the YAML at most once per process. Tests can force a
# reload by calling `set_active_risk_config(load_risk_config(...))`.
_ACTIVE_RISK_CONFIG: RiskConfig | None = None


def get_active_risk_config() -> RiskConfig:
    """Return the currently active RiskConfig (YAML if present, else builtin)."""
    global _ACTIVE_RISK_CONFIG
    if _ACTIVE_RISK_CONFIG is None:
        _ACTIVE_RISK_CONFIG = load_risk_config()
    return _ACTIVE_RISK_CONFIG


def set_active_risk_config(config: RiskConfig) -> None:
    """Override the active config (useful for tests / CLI flags)."""
    global _ACTIVE_RISK_CONFIG
    _ACTIVE_RISK_CONFIG = config

# Human-readable metric snippets used in the per-school explanation.
_DRIVER_LABEL = {
    "learning_outcome": "FLN",
    "digital_usage": "DIKSHA usage",
    "teacher_training": "training",
    "infrastructure": "infrastructure",
    "field_issue": "field issues",
    "data_availability": "data coverage",
    "data_quality": "data quality",
}


def _clip(s):
    return np.clip(s, 0.0, 100.0)


def compute_school_risk(tables: Tables) -> pd.DataFrame:
    kpis = compute_school_kpis(tables)
    dq = assess_quality(tables).per_school[
        ["school_id", "missing_usage_entirely", "missing_assessment", "dq_invalid_count"]
    ]
    df = kpis.merge(dq, on="school_id", how="left")
    weeks_expected = max(1, len(tables.weeks))

    # ---- Component risks (0-100; higher = worse) ---------------------------------------
    gain_risk = _clip(FLN_GAIN_FLOOR - df["fln_gain"].fillna(0) * FLN_GAIN_PER_POINT)
    prof_risk = _clip(100 - df["fln_proficiency"].fillna(0) * 1.4)
    lo = 0.6 * gain_risk + 0.4 * prof_risk
    lo = lo.where(~df["missing_assessment"].fillna(False), 85.0)
    df["learning_outcome"] = _clip(lo)

    du = _clip(100 * (1 - df["sessions_mean"] / USAGE_SESSIONS_BENCHMARK))
    du = du.where(df["internet_available"].fillna(True), _clip(du + 10))
    du = du.where(~df["missing_usage_entirely"].fillna(False), 100.0)
    df["digital_usage"] = _clip(du)

    df["teacher_training"] = _clip(100 - df["training_completion_pct"].fillna(30))

    df["infrastructure"] = _clip(100 - df["infrastructure_score"])

    df["field_issue"] = _clip(
        df["open_critical"] * 35 + df["open_high"] * 18 + df["open_issues"] * 4
    )

    da = _clip(100 * (1 - df["weeks_reported"] / weeks_expected))
    da = da.where(~df["missing_assessment"].fillna(False), _clip(da + 25))
    da = da.where(~df["missing_usage_entirely"].fillna(False), 100.0)
    df["data_availability"] = _clip(da)

    df["data_quality"] = _clip(df["dq_invalid_count"].fillna(0) * 30)

    # ---- Weighted score + band ---------------------------------------------------------
    cfg = get_active_risk_config()
    weights = cfg.weights
    df["risk_score"] = sum(df[c] * weights[c] for c in COMPONENTS).round(1)
    df["risk_band"] = df["risk_score"].apply(band_for_score)
    df["risk_model_version"] = cfg.version

    # ---- Top 2 weighted drivers + explanation ------------------------------------------
    contrib = pd.DataFrame({c: df[c] * weights[c] for c in COMPONENTS}, index=df.index)
    df["top_drivers"] = [
        ", ".join(contrib.loc[i].sort_values(ascending=False).head(2).index) for i in df.index
    ]
    df["explanation"] = df.apply(lambda r: _explain(r), axis=1)
    df[COMPONENTS] = df[COMPONENTS].round(1)

    cols = (
        ["school_id", "district", "block", "cluster", "risk_score", "risk_band"]
        + COMPONENTS
        + ["top_drivers", "explanation", "risk_model_version"]
    )
    return df[cols].sort_values("risk_score", ascending=False).reset_index(drop=True)


def _explain(r: pd.Series) -> str:
    drivers = r["top_drivers"].split(", ")
    parts = []
    for d in drivers:
        if d == "learning_outcome":
            parts.append(f"FLN gain {r.get('learning_outcome', 0):.0f}/100 risk")
        elif d == "digital_usage":
            parts.append(f"avg {r.get('sessions_mean', 0):.0f} sessions/wk")
        elif d == "teacher_training":
            parts.append("low training completion")
        elif d == "infrastructure":
            parts.append("weak infrastructure")
        elif d == "field_issue":
            parts.append(f"{int(r.get('open_critical', 0))} open critical issues")
        elif d == "data_availability":
            parts.append("missing/low data coverage")
        elif d == "data_quality":
            parts.append("data-quality flags")
    label = ", ".join(_DRIVER_LABEL.get(d, d) for d in drivers)
    return f"{r['risk_band']} risk - driven by {label} ({'; '.join(parts)})"


def compute_block_risk(school_risk: pd.DataFrame) -> pd.DataFrame:
    """Mean school risk per block (the unit officials triage on)."""
    agg = school_risk.groupby(["district", "block"]).agg(
        schools=("school_id", "nunique"),
        mean_risk=("risk_score", "mean"),
        high_risk_schools=("risk_band", lambda s: int((s == "High").sum())),
    ).round(1).reset_index()
    agg["risk_band"] = agg["mean_risk"].apply(band_for_score)
    return agg.sort_values("mean_risk", ascending=False).reset_index(drop=True)


def band_split(school_risk: pd.DataFrame) -> dict[str, float]:
    counts = school_risk["risk_band"].value_counts(normalize=True)
    return {b: round(float(counts.get(b, 0.0)), 3) for b in ("Low", "Medium", "High")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute decomposed risk scores.")
    parser.add_argument("--district", default=None, help="Filter to one district (default: all).")
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    tables = load_all()
    risk = compute_school_risk(tables)
    if args.district:
        risk = risk[risk["district"] == args.district].reset_index(drop=True)

    split = band_split(risk)
    print("=" * 72)
    print(f"  ShikshaSignal AI - risk scores (model v{RISK_MODEL_VERSION})  "
          f"[{args.district or 'all districts'}]")
    print("=" * 72)
    print(f"  Schools scored: {len(risk)}")
    print("  Band split    : " + "  ".join(f"{b} {f:.0%}" for b, f in split.items()))

    blocks = compute_block_risk(risk)
    if args.district:
        blocks = blocks[blocks["district"] == args.district]
    print(f"\n  Top {args.top} highest-risk BLOCKS:")
    for _, b in blocks.head(args.top).iterrows():
        print(f"    {b['mean_risk']:5.1f} [{b['risk_band']:<6}] {b['block']:<32} "
              f"({b['high_risk_schools']} high-risk schools)")

    print(f"\n  Top {args.top} highest-risk SCHOOLS:")
    for _, s in risk.head(args.top).iterrows():
        print(f"    {s['risk_score']:5.1f} [{s['risk_band']:<6}] {s['school_id']:<18} "
              f"{s['block']:<28} | {s['explanation']}")


if __name__ == "__main__":
    main()
