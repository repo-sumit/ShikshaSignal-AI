"""Typed, validated loading of the five synthetic CSVs.

`load_all()` returns a `Tables` object that every downstream tool consumes. It verifies that
required columns are present and coerces obvious types (booleans, numerics) but does NOT drop
or "fix" bad rows — that is the data-quality tool's job. The planted duplicate school row is
preserved in `schools` (so DQ can find it); use `schools_dedup` for safe joins.

Run:  python -m app.tools.csv_loader
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.config import CSV_FILES, SYNTHETIC_DIR
from app.schemas import TABLE_SCHEMAS

_BOOL_COLUMNS = {
    "schools": ["internet_available", "device_available"],
}
_BOOL_MAP = {"True": True, "False": False, "true": True, "false": False, True: True, False: False}


@dataclass
class Tables:
    """The five loaded tables + convenience accessors."""

    schools: pd.DataFrame
    diksha_usage: pd.DataFrame
    assessments: pd.DataFrame
    teacher_training: pd.DataFrame
    field_issues: pd.DataFrame
    source_dir: Path

    @property
    def schools_dedup(self) -> pd.DataFrame:
        """Schools with duplicate `school_id` collapsed (keep first) — safe for joins."""
        return self.schools.drop_duplicates("school_id", keep="first")

    @property
    def weeks(self) -> list[str]:
        return sorted(self.diksha_usage["week"].dropna().unique().tolist())

    @property
    def latest_week(self) -> str | None:
        w = self.weeks
        return w[-1] if w else None

    @property
    def prior_week(self) -> str | None:
        w = self.weeks
        return w[-2] if len(w) >= 2 else None

    def as_dict(self) -> dict[str, pd.DataFrame]:
        return {
            "schools": self.schools,
            "diksha_usage": self.diksha_usage,
            "assessments": self.assessments,
            "teacher_training": self.teacher_training,
            "field_issues": self.field_issues,
        }


def _load_one(name: str, path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing data file: {path}\n"
            f"Run `python scripts/generate_synthetic_data.py --seed 42` first."
        )
    df = pd.read_csv(path)

    required = TABLE_SCHEMAS[name]["required_columns"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {missing}")

    for col in _BOOL_COLUMNS.get(name, []):
        df[col] = df[col].map(_BOOL_MAP).astype("boolean")
    return df


def load_all(source_dir: Path = SYNTHETIC_DIR) -> Tables:
    """Load all five tables from `source_dir` into a validated `Tables` object."""
    source_dir = Path(source_dir)
    frames = {name: _load_one(name, source_dir / fname) for name, fname in CSV_FILES.items()}
    return Tables(source_dir=source_dir, **frames)


def main() -> None:
    tables = load_all()
    print("=" * 60)
    print("  ShikshaSignal AI - loaded tables")
    print("=" * 60)
    for name, df in tables.as_dict().items():
        print(f"  {name:<18}: {len(df):>5} rows x {df.shape[1]} cols")
    print(f"  weeks              : {len(tables.weeks)} "
          f"({tables.weeks[0]} .. {tables.latest_week})")
    print(f"  prior / latest week: {tables.prior_week} / {tables.latest_week}")
    print(f"  unique schools     : {tables.schools_dedup['school_id'].nunique()} "
          f"(raw rows {len(tables.schools)} -> duplicate keys flagged by data_quality)")


if __name__ == "__main__":
    main()
