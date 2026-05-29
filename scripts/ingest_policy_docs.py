"""Validate and report on the local policy layer (``data/policy_map.yaml``).

Phase context (see `plan.md`): the validation report deliberately rescoped the
original "RAG over policy PDFs" idea down to a deterministic YAML lookup for
this milestone — six short rows beat a vector store of six short docs. This
script is the corresponding ingest step: it loads the YAML, validates every
target has the required keys, and prints a one-line summary per row so a
demo viewer can see at a glance which policy mandates back which KPI.

Run:
    python scripts/ingest_policy_docs.py
    python scripts/ingest_policy_docs.py --path data/policy_map.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow `python scripts/ingest_policy_docs.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from app.config import DATA_DIR  # noqa: E402


REQUIRED_KEYS: tuple[str, ...] = ("label", "target", "direction", "source")
ALLOWED_DIRECTIONS: tuple[str, ...] = ("higher_is_better", "lower_is_better")


def load_policy_map(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Policy map not found at {path}. The deterministic policy layer is "
            f"a single YAML file in this milestone — see plan.md for the rationale."
        )
    with open(path, "r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    return loaded


def validate(loaded: dict) -> list[str]:
    """Return a list of validation errors. Empty list = clean."""
    errors: list[str] = []
    targets = loaded.get("targets")
    if not isinstance(targets, dict) or not targets:
        return ["`targets:` block is missing or empty."]
    for key, spec in targets.items():
        if not isinstance(spec, dict):
            errors.append(f"{key}: row is not a mapping.")
            continue
        for required in REQUIRED_KEYS:
            if required not in spec:
                errors.append(f"{key}: missing required key '{required}'.")
        if "direction" in spec and spec["direction"] not in ALLOWED_DIRECTIONS:
            errors.append(
                f"{key}: direction must be one of {ALLOWED_DIRECTIONS}, got {spec['direction']!r}."
            )
    return errors


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the deterministic policy layer (data/policy_map.yaml)."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DATA_DIR / "policy_map.yaml",
        help="Path to the policy YAML.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        loaded = load_policy_map(args.path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    errors = validate(loaded)
    targets = loaded.get("targets") or {}

    print("=" * 72)
    print("  ShikshaSignal AI — policy layer ingest")
    print("=" * 72)
    print(f"  Source : {args.path}")
    print(f"  Mode   : deterministic YAML lookup (no RAG, by design - see plan.md)")
    print(f"  Targets: {len(targets)}")
    print()

    for kpi, spec in targets.items():
        direction = spec.get("direction", "?")
        target = spec.get("target", "?")
        label = spec.get("label", kpi)
        source = spec.get("source", "?")
        print(f"  - {kpi:<40} target={target!s:<6} {direction:<18} from: {source}")
        if label and label != kpi:
            print(f"      label : {label}")

    print()
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {len(targets)} policy target(s) validated. The review compiler can consume "
          f"this YAML directly; no vector store or embedding model is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
