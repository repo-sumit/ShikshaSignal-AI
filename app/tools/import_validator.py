"""Import validator — reads the five CSVs against ``schemas/input_schemas.yaml`` and
writes a readiness report to ``outputs/import_validation_report.{md,json}``.

What it checks per file:
  * presence + row count
  * required columns present
  * unexpected columns (warning, never fatal)
  * primary-key uniqueness
  * foreign-key resolution against ``schools.csv``
  * null / out-of-range / invalid-enum values per column (sampled, capped)
  * ISO-week strings, date validity, future-dated rows

Output:
  * outputs/import_validation_report.md   — human-readable report
  * outputs/import_validation_report.json — machine-readable summary

Verdict (top-level):
  * "Ready"               — no errors, no warnings
  * "Ready with warnings" — warnings only
  * "Not ready"           — at least one error

This tool does NOT auto-fix anything. It is the gate between "you have CSVs"
and "you can confidently run the review compiler against them."

Run:
    python -m app.tools.import_validator
    python -m app.tools.import_validator --source-dir data/synthetic --outputs-dir outputs
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import CSV_FILES, OUTPUTS_DIR, REFERENCE_DATE, SYNTHETIC_DIR
from app.services.config_loader import InputSchemas, load_input_schemas

logger = logging.getLogger(__name__)


VERDICT_READY = "Ready"
VERDICT_READY_WITH_WARNINGS = "Ready with warnings"
VERDICT_NOT_READY = "Not ready"

_ISO_WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")
_MAX_OFFENDER_SAMPLES = 5


@dataclass
class Finding:
    severity: str         # "error" | "warning" | "info"
    file: str             # logical file key (schools / diksha_usage / ...)
    column: str | None    # affected column, or None for whole-file findings
    code: str             # short machine-readable code (e.g. "missing_required_column")
    detail: str
    sample: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileReport:
    file: str
    path: str
    present: bool
    rows: int
    required_columns_present: list[str]
    required_columns_missing: list[str]
    unexpected_columns: list[str]
    primary_key_unique: bool | None
    foreign_key_match_rate: float | None  # for files that reference schools.school_id
    findings: list[Finding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "file": self.file,
            "path": self.path,
            "present": self.present,
            "rows": self.rows,
            "required_columns_present": self.required_columns_present,
            "required_columns_missing": self.required_columns_missing,
            "unexpected_columns": self.unexpected_columns,
            "primary_key_unique": self.primary_key_unique,
            "foreign_key_match_rate": self.foreign_key_match_rate,
            "findings": [f.as_dict() for f in self.findings],
        }


@dataclass
class ValidationReport:
    verdict: str
    summary: dict
    files: list[FileReport]
    schema_source: str
    source_dir: str
    reference_date: str

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "summary": dict(self.summary),
            "schema_source": self.schema_source,
            "source_dir": self.source_dir,
            "reference_date": self.reference_date,
            "files": [f.as_dict() for f in self.files],
        }


# -----------------------------------------------------------------------------
# Per-column validators
# -----------------------------------------------------------------------------


def _sample(values: pd.Series, n: int = _MAX_OFFENDER_SAMPLES) -> list[str]:
    return [str(v) for v in values.head(n).tolist()]


def _validate_column(
    df: pd.DataFrame,
    col_spec: dict,
    findings: list[Finding],
    file_key: str,
) -> None:
    name = col_spec["name"]
    if name not in df.columns:
        return  # missing-column case is already recorded by the caller
    typ = col_spec.get("type", "string")
    nullable = bool(col_spec.get("nullable", False))
    series = df[name]
    null_mask = series.isna()

    n_nulls = int(null_mask.sum())
    if n_nulls and not nullable:
        findings.append(
            Finding(
                severity="error",
                file=file_key,
                column=name,
                code="null_in_non_nullable_column",
                detail=f"{n_nulls} null/NaN value(s) in non-nullable column",
                sample=[],
            )
        )

    non_null = series[~null_mask]
    if non_null.empty:
        return

    if typ in {"int", "float"}:
        coerced = pd.to_numeric(non_null, errors="coerce")
        bad_numeric = non_null[coerced.isna()]
        if not bad_numeric.empty:
            findings.append(
                Finding(
                    severity="error",
                    file=file_key,
                    column=name,
                    code="non_numeric_in_numeric_column",
                    detail=f"{len(bad_numeric)} non-numeric value(s) in {typ} column",
                    sample=_sample(bad_numeric),
                )
            )
        else:
            lo = col_spec.get("min")
            hi = col_spec.get("max")
            if lo is not None:
                below = non_null[coerced < lo]
                if not below.empty:
                    findings.append(
                        Finding(
                            severity="error",
                            file=file_key,
                            column=name,
                            code="value_below_min",
                            detail=f"{len(below)} value(s) below min {lo}",
                            sample=_sample(below),
                        )
                    )
            if hi is not None:
                above = non_null[coerced > hi]
                if not above.empty:
                    findings.append(
                        Finding(
                            severity="error",
                            file=file_key,
                            column=name,
                            code="value_above_max",
                            detail=f"{len(above)} value(s) above max {hi}",
                            sample=_sample(above),
                        )
                    )

    elif typ == "bool":
        valid = non_null.astype(str).str.lower().isin({"true", "false", "1", "0", "yes", "no"})
        bad = non_null[~valid]
        if not bad.empty:
            findings.append(
                Finding(
                    severity="error",
                    file=file_key,
                    column=name,
                    code="non_boolean_value",
                    detail=f"{len(bad)} non-boolean value(s)",
                    sample=_sample(bad),
                )
            )

    elif typ == "enum":
        enums = set(map(str, col_spec.get("enums") or []))
        if enums:
            bad = non_null[~non_null.astype(str).isin(enums)]
            if not bad.empty:
                findings.append(
                    Finding(
                        severity="error",
                        file=file_key,
                        column=name,
                        code="invalid_enum_value",
                        detail=f"{len(bad)} value(s) not in {sorted(enums)}",
                        sample=_sample(bad),
                    )
                )

    elif typ == "iso_week":
        bad = non_null[~non_null.astype(str).str.match(_ISO_WEEK_RE)]
        if not bad.empty:
            findings.append(
                Finding(
                    severity="error",
                    file=file_key,
                    column=name,
                    code="invalid_iso_week",
                    detail=f"{len(bad)} value(s) do not parse as YYYY-Www",
                    sample=_sample(bad),
                )
            )

    elif typ == "date":
        parsed = pd.to_datetime(non_null, errors="coerce")
        bad = non_null[parsed.isna()]
        if not bad.empty:
            findings.append(
                Finding(
                    severity="error",
                    file=file_key,
                    column=name,
                    code="invalid_date",
                    detail=f"{len(bad)} value(s) are not parseable dates",
                    sample=_sample(bad),
                )
            )
        else:
            future = non_null[parsed > pd.Timestamp(REFERENCE_DATE)]
            if not future.empty:
                findings.append(
                    Finding(
                        severity="error" if name == "created_at" else "warning",
                        file=file_key,
                        column=name,
                        code="future_dated_value",
                        detail=(
                            f"{len(future)} value(s) are after the reference date "
                            f"{REFERENCE_DATE.isoformat()}"
                        ),
                        sample=_sample(future),
                    )
                )


# -----------------------------------------------------------------------------
# Per-file validators
# -----------------------------------------------------------------------------


def _check_columns(
    df: pd.DataFrame,
    schema: dict,
    file_key: str,
    findings: list[Finding],
) -> tuple[list[str], list[str], list[str]]:
    required = [c["name"] for c in (schema.get("required_columns") or [])]
    optional = [c["name"] for c in (schema.get("optional_columns") or [])]
    known = set(required) | set(optional)
    present = [c for c in required if c in df.columns]
    missing = [c for c in required if c not in df.columns]
    unexpected = [c for c in df.columns if c not in known]

    for m in missing:
        findings.append(
            Finding(
                severity="error",
                file=file_key,
                column=m,
                code="missing_required_column",
                detail=f"required column {m!r} is missing",
            )
        )
    for u in unexpected:
        findings.append(
            Finding(
                severity="warning",
                file=file_key,
                column=u,
                code="unexpected_column",
                detail=f"column {u!r} is not declared in input_schemas.yaml",
            )
        )
    return present, missing, unexpected


def _check_primary_key(
    df: pd.DataFrame,
    schema: dict,
    file_key: str,
    findings: list[Finding],
) -> bool | None:
    pk = schema.get("primary_key")
    if pk is None:
        return None
    cols = [pk] if isinstance(pk, str) else list(pk)
    if any(c not in df.columns for c in cols):
        return None  # missing-column case already recorded
    dup_count = int(df.duplicated(subset=cols).sum())
    if dup_count:
        findings.append(
            Finding(
                severity="error",
                file=file_key,
                column=",".join(cols),
                code="duplicate_primary_key",
                detail=f"{dup_count} duplicate primary-key row(s) on {cols}",
            )
        )
    return dup_count == 0


def _check_foreign_keys(
    df: pd.DataFrame,
    schema: dict,
    file_key: str,
    schools_ids: set[str],
    findings: list[Finding],
) -> float | None:
    fks = schema.get("foreign_keys") or []
    match_rate: float | None = None
    for fk in fks:
        col = fk.get("column")
        ref = fk.get("references")
        if not col or not ref or col not in df.columns:
            continue
        if ref.startswith("schools."):
            unmatched = df[~df[col].isin(schools_ids)]
            n_unmatched = int(len(unmatched))
            n_total = int(len(df))
            match_rate = round(((n_total - n_unmatched) / n_total) * 100, 2) if n_total else 100.0
            if n_unmatched:
                findings.append(
                    Finding(
                        severity="error",
                        file=file_key,
                        column=col,
                        code="unmatched_foreign_key",
                        detail=(
                            f"{n_unmatched} row(s) reference a {ref} that is absent from "
                            f"schools.csv (match rate {match_rate}%)"
                        ),
                        sample=_sample(unmatched[col]),
                    )
                )
    return match_rate


def _validate_file(
    name: str,
    schema: dict,
    source_dir: Path,
    schools_ids: set[str] | None,
) -> FileReport:
    file_path = source_dir / schema.get("file", f"{name}.csv")
    findings: list[Finding] = []
    rep = FileReport(
        file=name,
        path=str(file_path),
        present=False,
        rows=0,
        required_columns_present=[],
        required_columns_missing=[],
        unexpected_columns=[],
        primary_key_unique=None,
        foreign_key_match_rate=None,
    )

    if not file_path.exists():
        findings.append(
            Finding(
                severity="error",
                file=name,
                column=None,
                code="missing_file",
                detail=f"expected CSV not found at {file_path}",
            )
        )
        rep.findings = findings
        return rep

    rep.present = True
    try:
        df = pd.read_csv(file_path)
    except pd.errors.EmptyDataError:
        findings.append(
            Finding(
                severity="error",
                file=name,
                column=None,
                code="empty_file",
                detail="CSV is empty",
            )
        )
        rep.findings = findings
        return rep
    except Exception as e:
        findings.append(
            Finding(
                severity="error",
                file=name,
                column=None,
                code="unreadable_file",
                detail=f"could not read CSV: {e}",
            )
        )
        rep.findings = findings
        return rep

    rep.rows = int(len(df))

    present, missing, unexpected = _check_columns(df, schema, name, findings)
    rep.required_columns_present = present
    rep.required_columns_missing = missing
    rep.unexpected_columns = unexpected

    for col_spec in schema.get("required_columns") or []:
        _validate_column(df, col_spec, findings, name)
    for col_spec in schema.get("optional_columns") or []:
        _validate_column(df, col_spec, findings, name)

    rep.primary_key_unique = _check_primary_key(df, schema, name, findings)
    rep.foreign_key_match_rate = _check_foreign_keys(
        df, schema, name, schools_ids or set(), findings
    )

    rep.findings = findings
    return rep


# -----------------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------------


def _verdict(reports: list[FileReport]) -> str:
    has_error = any(f.severity == "error" for r in reports for f in r.findings)
    has_warning = any(f.severity == "warning" for r in reports for f in r.findings)
    if has_error:
        return VERDICT_NOT_READY
    if has_warning:
        return VERDICT_READY_WITH_WARNINGS
    return VERDICT_READY


def _summary(reports: list[FileReport]) -> dict:
    files_present = sum(1 for r in reports if r.present)
    files_missing = sum(1 for r in reports if not r.present)
    rows = sum(r.rows for r in reports)
    errors = sum(1 for r in reports for f in r.findings if f.severity == "error")
    warnings = sum(1 for r in reports for f in r.findings if f.severity == "warning")
    return {
        "files_present": files_present,
        "files_missing": files_missing,
        "total_rows": rows,
        "errors": errors,
        "warnings": warnings,
    }


def validate(source_dir: Path) -> ValidationReport:
    schemas = load_input_schemas()
    source_dir = Path(source_dir)

    # Load schools first so foreign-key checks downstream can resolve.
    schools_ids: set[str] | None = None
    reports: list[FileReport] = []
    schools_path = source_dir / CSV_FILES["schools"]
    if schools_path.exists():
        try:
            schools_df = pd.read_csv(schools_path, usecols=["school_id"])
            schools_ids = set(schools_df["school_id"].dropna().astype(str))
        except Exception:
            schools_ids = set()

    for name, _fname in CSV_FILES.items():
        spec = schemas.files.get(name) or {}
        reports.append(_validate_file(name, spec, source_dir, schools_ids))

    return ValidationReport(
        verdict=_verdict(reports),
        summary=_summary(reports),
        files=reports,
        schema_source=schemas.source_path,
        source_dir=str(source_dir),
        reference_date=REFERENCE_DATE.isoformat(),
    )


# -----------------------------------------------------------------------------
# Renderers
# -----------------------------------------------------------------------------


def _render_markdown(report: ValidationReport) -> str:
    lines: list[str] = []
    lines.append("# Import Validation Report")
    lines.append("")
    lines.append(
        "> ⚠ **SYNTHETIC DATA.** This report is produced for the synthetic CSV "
        "dataset in `data/synthetic/`. When you map real aggregate exports, the "
        "same report will tell you which columns / values still need work before "
        "the review compiler can be run. See "
        "[docs/REAL_USE_READINESS.md](../docs/REAL_USE_READINESS.md)."
    )
    lines.append("")
    lines.append(f"**Verdict:** **{report.verdict}**")
    lines.append("")
    lines.append("## Summary")
    s = report.summary
    lines.append(
        f"- Files present: **{s['files_present']}** / "
        f"{s['files_present'] + s['files_missing']}"
    )
    lines.append(f"- Total rows: **{s['total_rows']:,}**")
    lines.append(f"- Errors: **{s['errors']}**")
    lines.append(f"- Warnings: **{s['warnings']}**")
    lines.append(f"- Schema spec: `{report.schema_source}`")
    lines.append(f"- Source directory: `{report.source_dir}`")
    lines.append(f"- Reference date: {report.reference_date}")
    lines.append("")

    lines.append("## Per-file results")
    lines.append("")
    lines.append("| File | Present | Rows | Missing cols | Unexpected cols | PK unique | FK match % | Errors | Warnings |")
    lines.append("| --- | :-: | ---: | ---: | ---: | :-: | ---: | ---: | ---: |")
    for r in report.files:
        e_count = sum(1 for f in r.findings if f.severity == "error")
        w_count = sum(1 for f in r.findings if f.severity == "warning")
        pk = "—" if r.primary_key_unique is None else ("yes" if r.primary_key_unique else "no")
        fk = "—" if r.foreign_key_match_rate is None else f"{r.foreign_key_match_rate}"
        lines.append(
            f"| {r.file} | {'yes' if r.present else 'no'} | {r.rows} | "
            f"{len(r.required_columns_missing)} | {len(r.unexpected_columns)} | "
            f"{pk} | {fk} | {e_count} | {w_count} |"
        )
    lines.append("")

    lines.append("## Findings (top to bottom)")
    lines.append("")
    any_finding = False
    for r in report.files:
        if not r.findings:
            continue
        any_finding = True
        lines.append(f"### {r.file}")
        for f in r.findings:
            sample = f" — sample: {f.sample}" if f.sample else ""
            col = f"`{f.column}`" if f.column else "(file-level)"
            lines.append(f"- **{f.severity.upper()}** [{f.code}] {col}: {f.detail}{sample}")
        lines.append("")
    if not any_finding:
        lines.append("_No findings — every check passed._")
        lines.append("")

    lines.append("## Recommended fixes")
    lines.append("")
    if report.verdict == VERDICT_READY:
        lines.append(
            "- None. Run the review compiler: "
            "`python -m app.review --district \"District Alpha\" --period 2026-05`."
        )
    else:
        lines.append(
            "- Resolve every **ERROR** above before running the review compiler. "
            "Warnings are advisory and will not block the run."
        )
        lines.append(
            "- For real aggregate exports, fill in "
            "`docs/templates/real_data_mapping_template.csv` so each column has a "
            "documented source + transformation."
        )
        lines.append(
            "- For ID-reconciliation errors (`unmatched_foreign_key`), confirm that "
            "every fact-table school_id corresponds to a row in `schools.csv`."
        )

    return "\n".join(lines) + "\n"


def write_report(report: ValidationReport, outputs_dir: Path) -> dict[str, Path]:
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    md_path = outputs_dir / "import_validation_report.md"
    json_path = outputs_dir / "import_validation_report.json"
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    return {"markdown": md_path, "json": json_path}


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the input CSVs against schemas/input_schemas.yaml and "
                    "write a markdown + JSON readiness report.",
    )
    parser.add_argument("--source-dir", type=Path, default=SYNTHETIC_DIR,
                        help="Directory containing the five input CSVs.")
    parser.add_argument("--outputs-dir", type=Path, default=OUTPUTS_DIR,
                        help="Where to write the validation report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
    args = _parse_args(argv)

    report = validate(args.source_dir)
    paths = write_report(report, args.outputs_dir)

    print("=" * 72)
    print("  ShikshaSignal AI - import validation")
    print("=" * 72)
    print(f"  Source         : {args.source_dir}")
    print(f"  Schema spec    : {report.schema_source}")
    print(f"  Verdict        : {report.verdict}")
    s = report.summary
    print(f"  Files          : {s['files_present']} present / {s['files_missing']} missing")
    print(f"  Rows           : {s['total_rows']:,}")
    print(f"  Errors         : {s['errors']}")
    print(f"  Warnings       : {s['warnings']}")
    print(f"  Markdown report: {paths['markdown']}")
    print(f"  JSON report    : {paths['json']}")

    # Exit nonzero only when the dataset is NOT READY (errors). Warnings still exit 0
    # so this can be wired into pre-commit / CI loops without false-positives.
    if report.verdict == VERDICT_NOT_READY:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
