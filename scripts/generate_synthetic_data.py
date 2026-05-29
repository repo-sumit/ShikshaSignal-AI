"""Generate the synthetic ShikshaSignal AI dataset.

Design goals (see the validation report):
  * SEEDED & reproducible: same --seed => byte-identical CSVs.
  * CORRELATED, not random: a latent per-school "health" factor drives every metric, so a
    genuinely weak school is weak across usage, FLN gain, training, infra and field issues
    simultaneously (what a real PMU would recognise). 1-2 deliberate false-positives are
    planted so the explainability layer looks real.
  * SEASONAL: an exam-period trough (weeks 4-5 of the window) lowers DIKSHA usage so the
    tool can recognise an *expected* dip rather than flag it as decline.
  * A clear "problem block" clusters high-risk schools so the narrative has a villain.
  * ~5-8% DELIBERATELY BROKEN rows (missing latest week, completion_percent=140, enrollment=0,
    blank scores, future created_at, one duplicate school_id) so the data-quality layer has
    real findings.

Run:  python scripts/generate_synthetic_data.py --seed 42 [--scale demo|full]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Make `app` importable when run as a plain script (sys.path[0] is scripts/, not the root).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import (  # noqa: E402
    COMPARISON_DISTRICT,
    CSV_FILES,
    DEFAULT_SEED,
    FOCUS_DISTRICT,
    GeneratorReport,
    REFERENCE_DATE,
    SCALES,
    SEASON_BY_WEEK_OFFSET,
    STATE_NAME,
    SYNTHETIC_DIR,
    TARGET_BAND_SPLIT,
    WINDOW_START_ISO_WEEK,
    WINDOW_START_ISO_YEAR,
    ScaleConfig,
)

# Fictional-but-plausible Indian block names (clearly synthetic, no real districts).
BLOCK_NAME_POOL = [
    "Rampur", "Kheda", "Bhojpur", "Sundarpur", "Devgaon", "Madhopur", "Chandwa", "Bareli",
    "Kosamba", "Pipariya", "Tilda", "Narwar", "Sihora", "Ghatol", "Banswada", "Khairi",
    "Lakhanpur", "Mohanpur", "Raisen", "Sehore", "Amla", "Beohari", "Dindori", "Katni",
    "Niwari", "Panna", "Shahpura", "Umaria", "Vidisha", "Waraseoni", "Ajaigarh", "Berasia",
    "Chhindwara", "Datia", "Edalabad", "Fatehpur", "Gohad", "Harda", "Itarsi", "Jaora",
    "Kannod", "Lateri", "Mungaoli", "Nalkheda", "Orchha", "Pichhore", "Raghogarh", "Sironj",
    "Tendukheda", "Ujjain", "Vijaypur", "Waidhan",
]
SCHOOL_TYPES = ["Primary", "Upper Primary", "Composite"]
TYPE_HIGHEST_GRADE = {"Primary": 5, "Upper Primary": 8, "Composite": 10}
COURSE_POOL = [
    "FLN Foundational Course",
    "NISHTHA Module 3 (Numeracy)",
    "NIPUN Literacy Pedagogy",
    "Assessment & Remediation",
]
ISSUE_TYPES = ["infra", "content", "device", "attendance", "training", "other"]
SEVERITIES = ["low", "med", "high", "critical"]


def clip(arr, lo, hi):
    return np.clip(arr, lo, hi)


def iso_week_labels(n_weeks: int) -> list[str]:
    """Return n ISO-week labels 'YYYY-Www' starting at the configured window start."""
    base = pd.Timestamp.fromisocalendar(WINDOW_START_ISO_YEAR, WINDOW_START_ISO_WEEK, 1)
    labels = []
    for k in range(n_weeks):
        d = (base + timedelta(weeks=k)).isocalendar()
        labels.append(f"{d.year}-W{d.week:02d}")
    return labels


def _proficiency_band(score: float) -> str:
    if score < 35:
        return "below"
    if score < 50:
        return "approaching"
    if score < 70:
        return "meets"
    return "exceeds"


def build_schools(rng: np.random.Generator, scale: ScaleConfig) -> tuple[pd.DataFrame, dict]:
    """Create the school dimension table + a {school_id: latent_health} map.

    Returns the schools DataFrame and a dict of generation metadata (problem block, the
    false-positive school ids, the injected-decliner and missing-latest-week ids).
    """
    rows = []
    health: dict[str, float] = {}

    districts = [
        (1, FOCUS_DISTRICT, scale.blocks_focus, 0.0),
        # Comparison district is modestly healthier so a district comparison is meaningful.
        (2, COMPARISON_DISTRICT, scale.blocks_comparison, 0.12),
    ]

    # The last block of the focus district is the deliberate "problem block".
    problem_block_name = BLOCK_NAME_POOL[scale.blocks_focus - 1]
    problem_block = f"{FOCUS_DISTRICT} / {problem_block_name}"

    block_cursor = 0
    for dist_idx, district, n_blocks, health_boost in districts:
        for b in range(n_blocks):
            block_name = BLOCK_NAME_POOL[block_cursor % len(BLOCK_NAME_POOL)]
            block_cursor += 1
            is_problem = dist_idx == 1 and block_name == problem_block_name
            for c in range(scale.clusters_per_block):
                for s in range(scale.schools_per_cluster):
                    sid = f"D{dist_idx:02d}_B{b:02d}_C{c}_S{s:02d}"
                    # Latent health ~ Beta skewed toward healthy; boosted for comparison
                    # district, penalised hard inside the problem block (so it clusters High).
                    h = float(rng.beta(2.3, 1.8)) + health_boost
                    if is_problem:
                        h *= 0.25
                    h = float(clip(h, 0.02, 0.99))
                    health[sid] = h

                    stype = SCHOOL_TYPES[rng.integers(0, len(SCHOOL_TYPES))]
                    infra = float(clip(h * 90 + rng.normal(0, 8), 2, 100))
                    enrollment = int(clip(rng.normal(160, 70), 30, 600))
                    teachers = int(
                        clip(
                            round(enrollment / rng.uniform(28, 42)),
                            scale.teachers_per_school[0],
                            scale.teachers_per_school[1],
                        )
                    )
                    rows.append(
                        {
                            "school_id": sid,
                            "school_name": f"GPS {block_name} No.{s + 1}",
                            "state": STATE_NAME,
                            "district": district,
                            "block": f"{district} / {block_name}",
                            "cluster": f"{block_name} Cluster {c + 1}",
                            "school_type": stype,
                            "lowest_grade": 1,
                            "highest_grade": TYPE_HIGHEST_GRADE[stype],
                            "enrollment": enrollment,
                            "teachers_count": teachers,
                            "internet_available": bool(rng.random() < (0.25 + 0.6 * h)),
                            "device_available": bool(rng.random() < (0.4 + 0.45 * h)),
                            "infrastructure_score": round(infra, 1),
                        }
                    )

    schools = pd.DataFrame(rows)

    # False-positive schools: low usage but strong FLN (decorrelate later). Pick 2 healthy-ish.
    healthy_ids = [sid for sid, h in health.items() if 0.5 < h < 0.8]
    false_positive_ids = list(rng.choice(healthy_ids, size=min(2, len(healthy_ids)), replace=False))

    # Injected sharp decliners (latest-week usage crash) — pick previously-active schools.
    active_ids = [sid for sid, h in health.items() if h > 0.5]
    decliner_ids = list(rng.choice(active_ids, size=min(4, len(active_ids)), replace=False))

    # Schools missing their latest DIKSHA week entirely (drives data-availability risk + DQ).
    weak_ids = [sid for sid, h in health.items() if h < 0.45]
    missing_latest_ids = list(
        rng.choice(weak_ids, size=min(10, len(weak_ids)), replace=False)
    ) if weak_ids else []

    meta = {
        "problem_block": problem_block,
        "false_positive_ids": false_positive_ids,
        "decliner_ids": decliner_ids,
        "missing_latest_ids": missing_latest_ids,
    }
    return schools, {"health": health, **meta}


def build_diksha_usage(
    rng: np.random.Generator, schools: pd.DataFrame, meta: dict, scale: ScaleConfig
) -> pd.DataFrame:
    weeks = iso_week_labels(scale.n_weeks)
    health = meta["health"]
    decliners = set(meta["decliner_ids"])
    missing_latest = set(meta["missing_latest_ids"])
    false_positives = set(meta["false_positive_ids"])
    last_week = weeks[-1]

    rows = []
    for _, srow in schools.iterrows():
        sid = srow["school_id"]
        h = health[sid]
        teachers = srow["teachers_count"]
        # Healthy school ~ 80 sessions/wk; non-starter (low h) ~ 0.
        base = h * 85.0
        if h < 0.18:
            base *= rng.uniform(0.0, 0.3)  # genuine non-starters
        if sid in false_positives:
            base *= 0.25  # low usage despite being otherwise healthy
        slope = rng.normal(0, 0.015)  # mild per-school trend

        # Weak schools also report data sparsely (realistic): drop 1-2 non-latest weeks.
        skip_weeks: set[str] = set()
        if h < 0.25:
            candidates = [w for w in weeks if w != last_week]
            n_skip = int(rng.integers(1, 3))
            skip_weeks = set(rng.choice(candidates, size=min(n_skip, len(candidates)), replace=False))

        for offset, week in enumerate(weeks):
            if week == last_week and sid in missing_latest:
                continue  # planted: missing latest-week row
            if week in skip_weeks:
                continue  # weak-school sparse reporting -> raises data-availability risk
            season = SEASON_BY_WEEK_OFFSET.get(offset, (1.0, "normal"))[0]
            trend = 1.0 + slope * offset
            level = base * season * trend
            if week == last_week and sid in decliners:
                level *= 0.30  # injected sharp decline in the latest week
            sessions = int(max(0, round(level + rng.normal(0, 4))))
            qr = int(max(0, round(sessions * rng.uniform(0.4, 0.8) + rng.normal(0, 2))))
            minutes = int(max(0, round(sessions * rng.uniform(11, 18))))
            act_teachers = int(clip(round(h * teachers * season + rng.normal(0, 0.5)), 0, teachers))
            students = int(max(0, round(sessions * rng.uniform(2.0, 4.0))))
            rows.append(
                {
                    "school_id": sid,
                    "week": week,
                    "qr_scans": qr,
                    "sessions": sessions,
                    "learning_minutes": minutes,
                    "active_teachers": act_teachers,
                    "active_students_proxy": students,
                }
            )
    return pd.DataFrame(rows)


def build_assessments(
    rng: np.random.Generator, schools: pd.DataFrame, meta: dict, scale: ScaleConfig
) -> pd.DataFrame:
    health = meta["health"]
    false_positives = set(meta["false_positive_ids"])
    rows = []
    for _, srow in schools.iterrows():
        sid = srow["school_id"]
        h = health[sid]
        for grade in scale.grades:
            for subject in scale.subjects:
                baseline = float(clip(rng.normal(20 + 18 * h, 6), 5, 70))
                gain = h * 22 - 2 + rng.normal(0, 3)
                if sid in false_positives:
                    gain = abs(gain) + 12  # strong FLN despite low usage
                if subject == "Numeracy":
                    gain -= rng.uniform(3, 8)  # numeracy lags literacy
                current = float(clip(baseline + gain, 2, 99))
                rows.append(
                    {
                        "school_id": sid,
                        "grade": grade,
                        "subject": subject,
                        "assessment_round": "endline",
                        "baseline_score": round(baseline, 1),
                        "current_score": round(current, 1),
                        "district_average": np.nan,  # filled below
                        "proficiency_band": _proficiency_band(current),
                    }
                )
    df = pd.DataFrame(rows)
    # District average per (district, grade, subject) computed from actual current scores.
    df = df.merge(schools[["school_id", "district"]], on="school_id", how="left")
    avg = (
        df.groupby(["district", "grade", "subject"])["current_score"]
        .transform("mean")
        .round(1)
    )
    df["district_average"] = avg
    df = df.drop(columns=["district"])

    # Planted broken: blank a few current_score values (data-quality: missing score).
    if len(df) > 0:
        blank_idx = rng.choice(df.index, size=max(2, len(df) // 250), replace=False)
        df.loc[blank_idx, "current_score"] = np.nan
    return df


def build_teacher_training(
    rng: np.random.Generator, schools: pd.DataFrame, meta: dict, scale: ScaleConfig
) -> pd.DataFrame:
    health = meta["health"]
    rows = []
    tid = 0
    for _, srow in schools.iterrows():
        sid = srow["school_id"]
        h = health[sid]
        for _ in range(int(srow["teachers_count"])):
            tid += 1
            comp = float(clip(h * 92 + rng.normal(0, 12), 0, 100))
            if comp < 5:
                status, comp = "not_started", 0.0
            elif comp >= 96:
                status, comp = "completed", 100.0
            else:
                status = "in_progress"
            assessment = (
                round(float(clip(45 + 45 * h + rng.normal(0, 8), 0, 100)), 1)
                if status == "completed"
                else np.nan
            )
            # Recent activity for engaged schools; older for weak ones (some become stale).
            days_ago = int(clip(rng.normal(60 * (1 - h), 25), 1, 200))
            last_activity = REFERENCE_DATE - timedelta(days=days_ago)
            rows.append(
                {
                    "teacher_id": f"TCH_{tid:05d}",
                    "school_id": sid,
                    "course_name": COURSE_POOL[rng.integers(0, len(COURSE_POOL))],
                    "status": status,
                    "completion_percent": round(comp, 1),
                    "assessment_score": assessment,
                    "last_activity_date": last_activity.isoformat(),
                }
            )
    df = pd.DataFrame(rows)
    # Planted broken: a few completion_percent = 140 (invalid > 100).
    if len(df) > 0:
        bad_idx = rng.choice(df.index, size=max(3, len(df) // 200), replace=False)
        df.loc[bad_idx, "completion_percent"] = 140.0
    return df


def build_field_issues(
    rng: np.random.Generator, schools: pd.DataFrame, meta: dict, scale: ScaleConfig
) -> pd.DataFrame:
    health = meta["health"]
    ids = schools["school_id"].tolist()
    # Sample target schools with weight proportional to (1 - health): risky schools get more.
    weights = np.array([1.0 - health[s] + 0.05 for s in ids])
    weights = weights / weights.sum()

    rows = []
    for i in range(scale.field_issues):
        sid = str(rng.choice(ids, p=weights))
        h = health[sid]
        # Weak schools skew toward severe + open issues.
        sev_p = [0.40 - 0.25 * (1 - h), 0.30, 0.20 + 0.15 * (1 - h), 0.10 + 0.10 * (1 - h)]
        sev_p = list(np.array(sev_p) / np.sum(sev_p))
        severity = str(rng.choice(SEVERITIES, p=sev_p))
        status = str(
            rng.choice(
                ["open", "in_progress", "resolved"],
                p=[0.25 + 0.4 * (1 - h), 0.25, 0.50 - 0.4 * (1 - h)]
                if h < 1
                else [0.2, 0.3, 0.5],
            )
        )
        created = REFERENCE_DATE - timedelta(days=int(rng.integers(1, 75)))
        resolved = None
        if status == "resolved":
            resolved = (created + timedelta(days=int(rng.integers(1, 25)))).isoformat()
        rows.append(
            {
                "issue_id": f"ISS_{i:04d}",
                "school_id": sid,
                "issue_type": ISSUE_TYPES[rng.integers(0, len(ISSUE_TYPES))],
                "severity": severity,
                "status": status,
                "reported_by": rng.choice(["BRC", "CRC", "HeadTeacher", "FieldApp"]),
                "description": f"{severity.title()} {ISSUE_TYPES[rng.integers(0, len(ISSUE_TYPES))]} issue reported at school",
                "created_at": created.isoformat(),
                "resolved_at": resolved,
            }
        )
    df = pd.DataFrame(rows)
    # Planted broken: a couple of future created_at dates (impossible).
    if len(df) > 1:
        fut_idx = rng.choice(df.index, size=2, replace=False)
        df.loc[fut_idx, "created_at"] = (REFERENCE_DATE + timedelta(days=10)).isoformat()
    return df


def _plant_duplicate_school(rng: np.random.Generator, schools: pd.DataFrame) -> pd.DataFrame:
    """Append one duplicate school_id row (data-quality: duplicate key)."""
    dup = schools.sample(1, random_state=int(rng.integers(0, 10_000))).copy()
    return pd.concat([schools, dup], ignore_index=True)


def _plant_orphans(
    rng: np.random.Generator, diksha: pd.DataFrame, issues: pd.DataFrame, scale: ScaleConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add fact rows for school_ids that do not exist in the schools dimension."""
    orphan_ids = [f"D09_B{99 - i:02d}_C9_S99" for i in range(3)]
    latest = iso_week_labels(scale.n_weeks)[-1]
    d_rows = [
        {
            "school_id": oid,
            "week": latest,
            "qr_scans": int(rng.integers(0, 30)),
            "sessions": int(rng.integers(0, 40)),
            "learning_minutes": int(rng.integers(0, 400)),
            "active_teachers": int(rng.integers(0, 4)),
            "active_students_proxy": int(rng.integers(0, 80)),
        }
        for oid in orphan_ids
    ]
    i_rows = [
        {
            "issue_id": f"ISS_ORPH{i}",
            "school_id": orphan_ids[i % len(orphan_ids)],
            "issue_type": "other",
            "severity": "med",
            "status": "open",
            "reported_by": "FieldApp",
            "description": "Issue from an unrecognised school id (ID mismatch)",
            "created_at": (REFERENCE_DATE - timedelta(days=5)).isoformat(),
            "resolved_at": None,
        }
        for i in range(2)
    ]
    diksha = pd.concat([diksha, pd.DataFrame(d_rows)], ignore_index=True)
    issues = pd.concat([issues, pd.DataFrame(i_rows)], ignore_index=True)
    return diksha, issues


def generate(seed: int = DEFAULT_SEED, scale_name: str = "demo", outdir=SYNTHETIC_DIR) -> GeneratorReport:
    scale = SCALES[scale_name]
    outdir = Path(outdir)
    rng = np.random.default_rng(seed)

    schools, meta = build_schools(rng, scale)
    diksha = build_diksha_usage(rng, schools, meta, scale)
    assessments = build_assessments(rng, schools, meta, scale)
    training = build_teacher_training(rng, schools, meta, scale)
    issues = build_field_issues(rng, schools, meta, scale)

    # Plant a few ORPHAN school_ids in fact tables (ids absent from the schools dimension) so
    # the ID-reconciliation report has real "unmatched" rows to surface — mirrors the #1 real
    # pain (UDISE vs DIKSHA vs internal IDs that don't join).
    diksha, issues = _plant_orphans(rng, diksha, issues, scale)

    # Plant one duplicate school row AFTER fact tables are built (so it's a pure DQ artifact).
    schools_out = _plant_duplicate_school(rng, schools)

    outdir.mkdir(parents=True, exist_ok=True)
    schools_out.to_csv(outdir / CSV_FILES["schools"], index=False)
    diksha.to_csv(outdir / CSV_FILES["diksha_usage"], index=False)
    assessments.to_csv(outdir / CSV_FILES["assessments"], index=False)
    training.to_csv(outdir / CSV_FILES["teacher_training"], index=False)
    issues.to_csv(outdir / CSV_FILES["field_issues"], index=False)

    report = GeneratorReport(
        seed=seed,
        scale=scale_name,
        counts={
            "schools": len(schools),
            "diksha_usage_rows": len(diksha),
            "assessments": len(assessments),
            "teachers": len(training),
            "field_issues": len(issues),
            "districts": schools["district"].nunique(),
            "blocks": schools["block"].nunique(),
        },
        problem_block=meta["problem_block"],
    )
    report.band_split = _estimate_band_split(seed, scale_name, outdir)
    return report


def _estimate_band_split(seed: int, scale_name: str, outdir) -> dict[str, float]:
    """Compute the real risk band split from the just-written CSVs, if the risk engine exists.

    Lazy/guarded import so the generator runs even before risk_score.py is created.
    """
    try:
        from app.tools.csv_loader import load_all
        from app.tools.risk_score import compute_school_risk
    except Exception:
        return {}
    try:
        tables = load_all(outdir)
        risk = compute_school_risk(tables)
        counts = risk["risk_band"].value_counts(normalize=True)
        return {b: round(float(counts.get(b, 0.0)), 3) for b in ("Low", "Medium", "High")}
    except Exception:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ShikshaSignal AI data.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scale", choices=list(SCALES.keys()), default="demo")
    args = parser.parse_args()

    report = generate(seed=args.seed, scale_name=args.scale)

    print("=" * 64)
    print(f"  ShikshaSignal AI - synthetic data generated (seed={report.seed}, scale={report.scale})")
    print("=" * 64)
    for k, v in report.counts.items():
        print(f"  {k:<22}: {v}")
    print(f"  problem_block         : {report.problem_block}")
    if report.band_split:
        print("  risk band split       :")
        for band, frac in report.band_split.items():
            lo, hi = TARGET_BAND_SPLIT[band]
            flag = "OK" if lo <= frac <= hi else "OUT-OF-RANGE"
            print(f"      {band:<7}: {frac:6.1%}  (target {lo:.0%}-{hi:.0%})  [{flag}]")
    else:
        print("  risk band split       : (risk engine not available yet - run risk_score later)")
    print(f"\n  Wrote 5 CSVs to: {SYNTHETIC_DIR}")
    print("  NOTE: synthetic demonstration data - not real government records.")


if __name__ == "__main__":
    main()
