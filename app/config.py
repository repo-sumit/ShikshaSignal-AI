"""Central configuration: paths, hierarchy scale, the risk model, and the academic calendar.

This is the single shared contract. The synthetic-data generator and every analytics tool
import constants from here so they never drift out of sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Reference "today" for the demo (matches the project's current date). Stale-record and
# future-date data-quality checks are computed relative to this so results are reproducible.
REFERENCE_DATE: date = date(2026, 5, 29)
STALE_DAYS: int = 45  # a teacher-training record with no activity for longer is "stale"

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = ROOT_DIR / "data"
SYNTHETIC_DIR: Path = DATA_DIR / "synthetic"
POLICY_DIR: Path = DATA_DIR / "policy_documents"
OUTPUTS_DIR: Path = ROOT_DIR / "outputs"

CSV_FILES: dict[str, str] = {
    "schools": "schools.csv",
    "diksha_usage": "diksha_usage.csv",
    "assessments": "assessments.csv",
    "teacher_training": "teacher_training.csv",
    "field_issues": "field_issues.csv",
}

DEFAULT_SEED: int = 42

# --------------------------------------------------------------------------------------
# Hierarchy scale
# --------------------------------------------------------------------------------------
FOCUS_DISTRICT: str = "District Alpha"
COMPARISON_DISTRICT: str = "District Beta"
STATE_NAME: str = "Pradesh North"


@dataclass(frozen=True)
class ScaleConfig:
    """Controls how much synthetic data is generated.

    The `demo` default is intentionally small so a risk ranking is readable in a memo and
    iteration is instant. `full` reproduces the CONTEXT.md scale for a one-off "it scales"
    screenshot. Switch with `--scale full` on the generator.
    """

    name: str
    blocks_focus: int
    blocks_comparison: int
    clusters_per_block: int
    schools_per_cluster: int
    teachers_per_school: tuple[int, int]  # (min, max) inclusive
    n_weeks: int
    grades: tuple[int, ...]
    subjects: tuple[str, ...]
    field_issues: int


SCALES: dict[str, ScaleConfig] = {
    "demo": ScaleConfig(
        name="demo",
        blocks_focus=6,
        blocks_comparison=2,
        clusters_per_block=2,
        schools_per_cluster=10,
        teachers_per_school=(3, 7),
        n_weeks=8,
        grades=(1, 2, 3),
        subjects=("Literacy", "Numeracy"),
        field_issues=150,
    ),
    "full": ScaleConfig(
        name="full",
        blocks_focus=40,
        blocks_comparison=10,
        clusters_per_block=4,
        schools_per_cluster=5,
        teachers_per_school=(4, 12),
        n_weeks=12,
        grades=(1, 2, 3, 4, 5),
        subjects=("Literacy", "Numeracy"),
        field_issues=1200,
    ),
}

# --------------------------------------------------------------------------------------
# Academic calendar (8-week demo window). Multipliers scale DIKSHA usage to model
# exam-period troughs and vacation, so the tool recognises seasonal dips instead of
# flagging them as decline. Index = week offset within the generated window.
# --------------------------------------------------------------------------------------
# Window anchored so "today" (2026-05-29) sits just after the latest week.
WINDOW_START_ISO_YEAR: int = 2026
WINDOW_START_ISO_WEEK: int = 18  # 2026-W18 .. 2026-W25 for an 8-week demo

# week_offset -> (seasonal_multiplier, label)
SEASON_BY_WEEK_OFFSET: dict[int, tuple[float, str]] = {
    0: (1.00, "normal"),
    1: (1.00, "normal"),
    2: (0.95, "normal"),
    3: (0.90, "normal"),
    4: (0.50, "exam_period"),   # half-yearly exams -> sharp dip (expected, not risk)
    5: (0.45, "exam_period"),
    6: (0.80, "recovery"),
    7: (0.92, "recovery"),
}

EXAM_WEEK_OFFSETS: tuple[int, ...] = (4, 5)

# --------------------------------------------------------------------------------------
# Risk model v1.0 — weights MUST sum to 1.0. Every score is hand-recomputable.
# Each component is a 0-100 sub-score where HIGHER = MORE risk.
# --------------------------------------------------------------------------------------
RISK_MODEL_VERSION: str = "1.0"

RISK_WEIGHTS: dict[str, float] = {
    "learning_outcome": 0.25,
    "digital_usage": 0.20,
    "teacher_training": 0.15,
    "infrastructure": 0.15,
    "field_issue": 0.10,
    "data_availability": 0.10,
    "data_quality": 0.05,
}

# Risk bands: [lower_inclusive, upper_exclusive) so the 0-100 continuum has no gaps.
# Low: <40, Medium: 40-<70, High: >=70.
RISK_BANDS: tuple[tuple[float, float, str], ...] = (
    (0.0, 40.0, "Low"),
    (40.0, 70.0, "Medium"),
    (70.0, 100.0001, "High"),
)

# Benchmarks used to map raw metrics -> 0-100 component risk (see risk_score.py).
USAGE_SESSIONS_BENCHMARK: float = 50.0   # weekly sessions considered "healthy"
FLN_GAIN_FLOOR: float = 80.0             # risk when gain == 0
FLN_GAIN_PER_POINT: float = 4.0          # risk reduction per point of FLN gain

# Acceptable band-split tolerance for the generated demo data (asserted in tests).
TARGET_BAND_SPLIT: dict[str, tuple[float, float]] = {
    "Low": (0.45, 0.68),
    "Medium": (0.20, 0.40),
    "High": (0.08, 0.24),
}


def band_for_score(score: float) -> str:
    """Map a 0-100 risk score to its band label (half-open intervals, no gaps)."""
    for lo, hi, label in RISK_BANDS:
        if lo <= score < hi:
            return label
    return "High" if score >= 70 else "Low"


@dataclass
class GeneratorReport:
    """Lightweight summary returned by the generator for logging/tests."""

    seed: int
    scale: str
    counts: dict[str, int] = field(default_factory=dict)
    band_split: dict[str, float] = field(default_factory=dict)
    problem_block: str | None = None
