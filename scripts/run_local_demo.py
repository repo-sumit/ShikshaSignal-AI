"""One-command local demo of ShikshaSignal AI.

Runs the full Phase 1-3 pipeline end-to-end against the offline MockLLM
provider, then prints the artifacts and the Streamlit command to launch the
viewer. Streamlit itself is intentionally NOT started — that is a blocking
foreground process; the user runs it themselves when ready.

Run:
    python scripts/run_local_demo.py
    python scripts/run_local_demo.py --district "District Alpha" --period 2026-05
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make `app` and sibling scripts importable when invoked as a plain file.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))


def _heading(label: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n  {label}\n{bar}")


def step_generate_synthetic_data(seed: int) -> None:
    _heading(f"Step 1/3  generate synthetic data (seed={seed})")
    # Imported here so a partial environment (e.g. missing optional deps) still lets
    # the script import and surface a clean error rather than failing at import time.
    from generate_synthetic_data import generate
    from app.config import SCALES, SYNTHETIC_DIR

    report = generate(seed=seed, scale_name="demo", outdir=SYNTHETIC_DIR)
    print(f"  Wrote {sum(report.counts.values())} rows across "
          f"{len(report.counts)} CSVs at {SYNTHETIC_DIR}")
    print(f"  Band split: " + "  ".join(f"{b} {f:.0%}" for b, f in report.band_split.items()))


def step_ingest_policy_docs() -> None:
    _heading("Step 2/3  ingest policy layer (data/policy_map.yaml)")
    from scripts.ingest_policy_docs import main as ingest_main  # type: ignore
    rc = ingest_main([])
    if rc != 0:
        raise RuntimeError(f"Policy ingest exited with code {rc}.")


def step_run_review(district: str, period: str, llm_provider: str) -> dict[str, Path]:
    _heading(f"Step 3/3  compile review (district={district!r}, period={period}, provider={llm_provider})")
    from app.review import run_review

    arts = run_review(
        district=district,
        period=period,
        llm_provider=llm_provider,
    )
    paths = {
        "Monthly review memo": arts.monthly_district_review_md,
        "Action tracker":       arts.action_tracker_csv,
        "Audit log":            arts.audit_log_json,
        "Review facts":         arts.review_facts_json,
    }
    for label, p in paths.items():
        print(f"  {label:<22}: {p}")
    return paths


def print_next_steps(paths: dict[str, Path]) -> None:
    _heading("All done. What to do next")
    print("  1. Inspect the memo (markdown):")
    print(f"       {paths['Monthly review memo']}")
    print("  2. Open the action tracker (CSV) in your editor or Excel.")
    print("  3. Launch the local Streamlit viewer to browse everything:")
    print("       python -m streamlit run frontend/streamlit_app.py")
    print("     (on macOS/Linux, `streamlit run frontend/streamlit_app.py` also works)")
    print("  4. Re-run with a real LLM provider (optional):")
    print("       python -m app.review --district \"District Alpha\" --period 2026-05 --llm-provider gemini")
    print()
    print("  All inputs are SYNTHETIC. No real student, teacher, school, or district data.")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ShikshaSignal AI local demo end-to-end.")
    parser.add_argument("--district", default="District Alpha")
    parser.add_argument("--period", default="2026-05")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--llm-provider",
        choices=["mock", "gemini", "groq", "ollama"],
        default="mock",
        help="Default 'mock' runs fully offline. Other providers fall back to mock if unavailable.",
    )
    parser.add_argument(
        "--skip-data",
        action="store_true",
        help="Skip synthetic data generation (use whatever is already in data/synthetic/).",
    )
    parser.add_argument(
        "--skip-policy",
        action="store_true",
        help="Skip policy-layer ingest (use the existing data/policy_map.yaml as-is).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    print("=" * 72)
    print("  ShikshaSignal AI - Monthly District Review Agent - LOCAL DEMO")
    print("=" * 72)
    print("  All inputs are SYNTHETIC and public-safe. Local-first; no paid APIs.")

    if not args.skip_data:
        step_generate_synthetic_data(args.seed)
    if not args.skip_policy:
        step_ingest_policy_docs()
    paths = step_run_review(args.district, args.period, args.llm_provider)
    print_next_steps(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
