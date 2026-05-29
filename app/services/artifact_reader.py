"""Lightweight readers for the artifacts the Review Compiler produces.

Used by the Streamlit viewer (and any other thin client) so the UI never opens
files directly. Every reader is **defensive**: missing files return an empty
result rather than raising. The viewer can then decide what to show.

No Streamlit imports here — keep this module pure-Python + pandas so it's
trivially unit-testable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.config import OUTPUTS_DIR, SYNTHETIC_DIR
from app.tools.csv_loader import load_all


# ---------------------------------------------------------------------------
# Per-file readers — every one tolerates a missing path gracefully
# ---------------------------------------------------------------------------


def read_markdown(path: Path | str) -> str:
    """Read a markdown file. Returns '' if the file is missing or empty."""
    p = Path(path)
    if not p.exists() or p.is_dir():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def read_csv(path: Path | str) -> pd.DataFrame:
    """Read a CSV into a DataFrame. Returns an empty DataFrame if missing."""
    p = Path(path)
    if not p.exists() or p.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def read_json(path: Path | str) -> dict:
    """Read a JSON file. Returns {} if missing or unparseable."""
    p = Path(path)
    if not p.exists() or p.is_dir():
        return {}
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# ---------------------------------------------------------------------------
# Convenience accessors for the four known output files
# ---------------------------------------------------------------------------


def output_paths(outputs_dir: Path | str = OUTPUTS_DIR) -> dict[str, Path]:
    base = Path(outputs_dir)
    return {
        "review_md": base / "monthly_district_review.md",
        "action_tracker_csv": base / "action_tracker.csv",
        "audit_log_json": base / "audit_log.json",
        "review_facts_json": base / "review_facts.json",
        "risk_ranking_csv": base / "risk_ranking.csv",
        "block_risk_ranking_csv": base / "block_risk_ranking.csv",
    }


def all_outputs_present(outputs_dir: Path | str = OUTPUTS_DIR) -> bool:
    """True iff the four Review Compiler artifacts exist and are non-empty."""
    required = ("review_md", "action_tracker_csv", "audit_log_json", "review_facts_json")
    paths = output_paths(outputs_dir)
    return all(paths[k].exists() and paths[k].stat().st_size > 0 for k in required)


# ---------------------------------------------------------------------------
# Synthetic-data introspection (drives the district / period pickers)
# ---------------------------------------------------------------------------


def synthetic_data_present(synthetic_dir: Path | str = SYNTHETIC_DIR) -> bool:
    base = Path(synthetic_dir)
    return (base / "schools.csv").exists()


def list_available_districts(synthetic_dir: Path | str = SYNTHETIC_DIR) -> list[str]:
    """Return sorted unique district names from `schools.csv`, or [] if absent."""
    base = Path(synthetic_dir)
    schools_csv = base / "schools.csv"
    if not schools_csv.exists():
        return []
    try:
        tables = load_all(base)
    except (FileNotFoundError, ValueError, OSError):
        return []
    if "district" not in tables.schools.columns:
        return []
    return sorted(str(d) for d in tables.schools["district"].dropna().unique().tolist())


def list_available_periods(synthetic_dir: Path | str = SYNTHETIC_DIR) -> list[str]:
    """Return display-friendly period labels derived from synthetic weeks.

    Today the synthetic generator only produces ISO-week granularity; we map each
    distinct ``YYYY-Www`` to its ``YYYY-MM`` parent month so the viewer's period
    selector matches the CLI's ``--period`` argument shape (``2026-05``).
    Falls back to ``["2026-05"]`` when no synthetic data exists, so the viewer
    is never left with an empty selector.
    """
    base = Path(synthetic_dir)
    if not (base / "diksha_usage.csv").exists():
        return ["2026-05"]
    try:
        tables = load_all(base)
    except (FileNotFoundError, ValueError, OSError):
        return ["2026-05"]
    months: set[str] = set()
    for week in tables.weeks:
        # ISO weeks look like "2026-W18". Map to the calendar month of that week's Monday.
        try:
            year_str, w_str = week.split("-W")
            year, w = int(year_str), int(w_str)
            monday = pd.Timestamp.fromisocalendar(year, w, 1)
            months.add(f"{monday.year:04d}-{monday.month:02d}")
        except (ValueError, AttributeError):
            continue
    return sorted(months) or ["2026-05"]
