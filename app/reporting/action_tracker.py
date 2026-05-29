"""Build the action tracker — one row per high-risk school's primary driver.

Action wording, owner role, and policy reference are all driven by a small lookup
keyed on the risk component name. Every row carries the *evidence* (the components
that drove the action) so a reviewer can audit "why is this action here?" without
re-running anything.

All actions start at status=`proposed`; approval is a downstream workflow concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# Stable column order — referenced by tests and downstream consumers.
ACTION_COLUMNS: list[str] = [
    "action_id",
    "district",
    "block",
    "school_id",
    "school_name",
    "risk_area",
    "recommended_action",
    "suggested_owner",
    "priority",
    "evidence",
    "policy_reference",
    "status",
]


@dataclass(frozen=True)
class ActionRule:
    """How a single risk component maps onto a concrete proposed action."""

    risk_area: str           # human label, e.g. "Low DIKSHA usage"
    recommended_action: str
    suggested_owner: str
    policy_reference: str


# Keys mirror the component names produced by `app.tools.risk_score.compute_school_risk`.
RULES: dict[str, ActionRule] = {
    "learning_outcome": ActionRule(
        risk_area="Learning outcome gap (FLN)",
        recommended_action=(
            "Schedule diagnostic FLN assessment and targeted re-teaching; assign an academic "
            "mentor visit within two weeks."
        ),
        suggested_owner="Block Resource Coordinator + Academic Mentor",
        policy_reference="NIPUN Bharat Mission / FLN Goals",
    ),
    "digital_usage": ActionRule(
        risk_area="Low DIKSHA usage",
        recommended_action=(
            "Conduct a 20-minute DIKSHA model lesson on-site; verify QR-textbook coverage and "
            "device/connectivity status; pair with a high-adoption peer school in the block."
        ),
        suggested_owner="Block Resource Coordinator + Cluster Resource Coordinator (CRC)",
        policy_reference="Digital Learning Adoption Guideline",
    ),
    "teacher_training": ActionRule(
        risk_area="Teacher training gap",
        recommended_action=(
            "Call every teacher stalled in In Progress for >60 days; reassign mismatched "
            "courses; book a Saturday peer-learning slot to clear the mandatory bundle."
        ),
        suggested_owner="Block Resource Coordinator",
        policy_reference="Teacher Training Circular 2025 (NISHTHA / FLN)",
    ),
    "infrastructure": ActionRule(
        risk_area="Infrastructure / connectivity weakness",
        recommended_action=(
            "Raise infra ticket for the failing device/connectivity items; verify with school "
            "head; escalate via the district maintenance cell if open >7 days."
        ),
        suggested_owner="District Engineering Cell + School Head",
        policy_reference="Digital Learning Adoption Guideline",
    ),
    "field_issue": ActionRule(
        risk_area="Open field issues",
        recommended_action=(
            "Triage every open Critical and High issue at this school; assign owner and "
            "closure deadline; close or escalate within the next review cycle."
        ),
        suggested_owner="Block Resource Coordinator",
        policy_reference="District Review Circular",
    ),
    "data_availability": ActionRule(
        risk_area="Patchy data submission",
        recommended_action=(
            "Follow up with the school head and CRC on missing weekly DIKSHA submissions; "
            "deadline = end of the current review cycle."
        ),
        suggested_owner="Cluster Resource Coordinator (CRC)",
        policy_reference="District Review Circular",
    ),
    "data_quality": ActionRule(
        risk_area="Data quality flags",
        recommended_action=(
            "Reconcile invalid records (completion% out of range, duplicate IDs, blank "
            "assessment scores) with the source register before the next review."
        ),
        suggested_owner="PMU Analyst (District)",
        policy_reference="District Review Circular",
    ),
}


_PRIORITY_BY_BAND: dict[str, str] = {"High": "P1", "Medium": "P2", "Low": "P3"}


def _evidence_for_row(row: pd.Series) -> str:
    """Build the evidence string from the school's component breakdown."""
    parts: list[str] = []
    score = row.get("risk_score")
    band = row.get("risk_band")
    if pd.notna(score) and band:
        parts.append(f"risk_score={float(score):.1f} ({band})")
    # Top drivers come pre-sorted from risk_score._explain.
    drivers = str(row.get("top_drivers", "")).split(", ")
    for d in drivers[:2]:
        if d in RULES:
            comp_val = row.get(d)
            if pd.notna(comp_val):
                parts.append(f"{d}={float(comp_val):.0f}/100")
    fln = row.get("fln_gain")
    if pd.notna(fln):
        parts.append(f"fln_gain={float(fln):.1f}")
    sess = row.get("sessions_latest")
    if pd.notna(sess):
        parts.append(f"sessions_latest={float(sess):.0f}")
    weeks = row.get("weeks_reported")
    if pd.notna(weeks):
        parts.append(f"weeks_reported={int(weeks)}/8")
    open_crit = row.get("open_critical")
    if pd.notna(open_crit) and float(open_crit) > 0:
        parts.append(f"open_critical={int(open_crit)}")
    return "; ".join(parts)


def build_action_tracker(
    school_ranking: pd.DataFrame,
    district: str,
    top_n: int = 10,
) -> pd.DataFrame:
    """Return the top-N schools' action tracker rows. `school_ranking` is the output
    of `app.tools.rankings.build_school_ranking` (already sorted highest-risk first)."""
    if school_ranking is None or school_ranking.empty:
        return pd.DataFrame(columns=ACTION_COLUMNS)

    scoped = school_ranking[school_ranking["district"] == district].head(top_n).copy()
    rows: list[dict] = []
    for i, (_, r) in enumerate(scoped.iterrows(), start=1):
        primary_driver = str(r.get("top_drivers", "")).split(", ")[0] or "data_quality"
        rule = RULES.get(primary_driver) or RULES["data_quality"]
        rows.append(
            {
                "action_id": f"ACT_{i:04d}",
                "district": r.get("district"),
                "block": r.get("block"),
                "school_id": r.get("school_id"),
                "school_name": r.get("school_name"),
                "risk_area": rule.risk_area,
                "recommended_action": rule.recommended_action,
                "suggested_owner": rule.suggested_owner,
                "priority": _PRIORITY_BY_BAND.get(str(r.get("risk_band")), "P3"),
                "evidence": _evidence_for_row(r),
                "policy_reference": rule.policy_reference,
                "status": "proposed",
            }
        )
    return pd.DataFrame(rows, columns=ACTION_COLUMNS)


def write_action_tracker(actions: pd.DataFrame, path: Path) -> Path:
    """Write `actions` to `path` (creating parents) and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    actions.to_csv(path, index=False)
    return path
