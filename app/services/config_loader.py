"""Load + validate the YAML config files added in Milestone 7.

Three files, all optional with sensible fallbacks to in-code constants:

    config/risk_weights.yaml   -> risk model weights + bands + version
    config/kpi_targets.yaml    -> KPI targets (mirrors data/policy_map.yaml)
    schemas/input_schemas.yaml -> per-CSV column contract for the validator

If a YAML file is present but invalid, we RAISE — silently falling back to
defaults on a broken config file would mask exactly the failure mode this
layer is meant to surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from app.config import (
    DATA_DIR,
    RISK_BANDS,
    RISK_MODEL_VERSION,
    RISK_WEIGHTS,
    ROOT_DIR,
)


CONFIG_DIR: Path = ROOT_DIR / "config"
SCHEMAS_DIR: Path = ROOT_DIR / "schemas"

RISK_WEIGHTS_PATH: Path = CONFIG_DIR / "risk_weights.yaml"
KPI_TARGETS_PATH: Path = CONFIG_DIR / "kpi_targets.yaml"
LEGACY_POLICY_MAP_PATH: Path = DATA_DIR / "policy_map.yaml"
INPUT_SCHEMAS_PATH: Path = SCHEMAS_DIR / "input_schemas.yaml"


WEIGHT_SUM_TOLERANCE: float = 0.001


class ConfigError(ValueError):
    """Raised when a YAML config is present but malformed."""


# -------------------------------------------------------------------------------------
# Risk weights
# -------------------------------------------------------------------------------------


# The in-code component name (used by app/tools/risk_score.py) for the field-issue
# weight is `field_issue` (singular); the YAML uses `field_issues` (plural) because
# that reads more naturally in config. Alias both so callers can use either.
_RISK_KEY_ALIASES: dict[str, str] = {"field_issues": "field_issue"}


def _alias_key(k: str) -> str:
    return _RISK_KEY_ALIASES.get(k, k)


@dataclass(frozen=True)
class RiskConfig:
    weights: dict[str, float]
    version: str
    bands: tuple[tuple[float, float, str], ...]
    source_path: str         # absolute path of the file that produced this config
    source_kind: str         # "yaml" | "builtin"

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "weights": dict(self.weights),
            "bands": [
                {"label": lab, "min": lo, "max": hi} for (lo, hi, lab) in self.bands
            ],
            "source_path": self.source_path,
            "source_kind": self.source_kind,
        }


def _normalise_weights(raw: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in raw.items():
        key = _alias_key(str(k))
        try:
            out[key] = float(v)
        except (TypeError, ValueError) as e:
            raise ConfigError(f"risk weight {k!r} is not numeric: {v!r}") from e
    return out


def _validate_risk_weights(weights: dict[str, float]) -> None:
    expected = set(RISK_WEIGHTS.keys())
    got = set(weights.keys())
    missing = expected - got
    extra = got - expected
    if missing:
        raise ConfigError(f"risk weights are missing components: {sorted(missing)}")
    if extra:
        raise ConfigError(
            f"risk weights contain unknown components: {sorted(extra)}; "
            f"expected {sorted(expected)}"
        )
    for name, w in weights.items():
        if w < 0.0 or w > 1.0:
            raise ConfigError(f"risk weight {name!r} = {w} is outside [0, 1]")
    total = sum(weights.values())
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise ConfigError(f"risk weights must sum to 1.0 (got {total:.6f})")


def _parse_bands(raw: Any) -> tuple[tuple[float, float, str], ...]:
    if raw is None:
        return RISK_BANDS
    if not isinstance(raw, list):
        raise ConfigError(f"`bands:` must be a list, got {type(raw).__name__}")
    out: list[tuple[float, float, str]] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict) or not {"label", "min", "max"}.issubset(row):
            raise ConfigError(f"bands[{i}] must be a mapping with label/min/max")
        out.append((float(row["min"]), float(row["max"]), str(row["label"])))
    return tuple(out)


def load_risk_config(path: Path | None = None) -> RiskConfig:
    """Return the active risk model config. Falls back to in-code constants
    if no YAML file exists; raises if YAML exists but is malformed."""
    target = path if path is not None else RISK_WEIGHTS_PATH
    if not target.exists():
        return RiskConfig(
            weights=dict(RISK_WEIGHTS),
            version=RISK_MODEL_VERSION,
            bands=tuple(RISK_BANDS),
            source_path=f"builtin:app.config.RISK_WEIGHTS",
            source_kind="builtin",
        )

    try:
        loaded = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{target} is not valid YAML: {e}") from e

    raw_weights = loaded.get("weights")
    if not isinstance(raw_weights, dict) or not raw_weights:
        raise ConfigError(f"{target} is missing a non-empty `weights:` mapping")

    weights = _normalise_weights(raw_weights)
    _validate_risk_weights(weights)
    bands = _parse_bands(loaded.get("bands"))
    version = str(loaded.get("version") or RISK_MODEL_VERSION)
    return RiskConfig(
        weights=weights,
        version=version,
        bands=bands,
        source_path=str(target),
        source_kind="yaml",
    )


# -------------------------------------------------------------------------------------
# KPI targets
# -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class KpiTargetsConfig:
    targets: dict[str, dict]
    version: str
    source_path: str
    source_kind: str  # "yaml" | "legacy" | "empty"


def load_kpi_targets(path: Path | None = None) -> KpiTargetsConfig:
    """Prefer ``config/kpi_targets.yaml``; fall back to ``data/policy_map.yaml``."""
    explicit = path is not None
    candidates: list[Path] = (
        [path]  # explicit override wins
        if explicit
        else [KPI_TARGETS_PATH, LEGACY_POLICY_MAP_PATH]
    )

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            loaded = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"{candidate} is not valid YAML: {e}") from e
        targets = loaded.get("targets") or {}
        if not isinstance(targets, dict):
            raise ConfigError(f"{candidate}: `targets:` must be a mapping")
        version = str(loaded.get("version") or "")
        kind = "yaml" if candidate == KPI_TARGETS_PATH else "legacy"
        return KpiTargetsConfig(
            targets=targets,
            version=version,
            source_path=str(candidate),
            source_kind=kind,
        )

    return KpiTargetsConfig(
        targets={},
        version="",
        source_path="",
        source_kind="empty",
    )


# -------------------------------------------------------------------------------------
# Input schemas spec
# -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class InputSchemas:
    version: str
    files: dict[str, dict]   # name -> spec
    invariants: list[str]
    forbidden_fields: list[str]
    source_path: str

    def required_columns(self, name: str) -> list[str]:
        spec = self.files.get(name) or {}
        return [c["name"] for c in (spec.get("required_columns") or []) if "name" in c]

    def optional_columns(self, name: str) -> list[str]:
        spec = self.files.get(name) or {}
        return [c["name"] for c in (spec.get("optional_columns") or []) if "name" in c]

    def known_columns(self, name: str) -> set[str]:
        return set(self.required_columns(name)) | set(self.optional_columns(name))

    def file_specs(self) -> Iterable[tuple[str, dict]]:
        return self.files.items()


def load_input_schemas(path: Path | None = None) -> InputSchemas:
    target = path if path is not None else INPUT_SCHEMAS_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"Input schema spec not found at {target}. This file is required by "
            f"the import validator (Milestone 7)."
        )
    try:
        loaded = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{target} is not valid YAML: {e}") from e

    files = loaded.get("files") or {}
    if not isinstance(files, dict) or not files:
        raise ConfigError(f"{target} is missing `files:` mapping")

    # Light validation per file spec.
    for name, spec in files.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"{target}: files.{name} must be a mapping")
        req = spec.get("required_columns") or []
        if not isinstance(req, list):
            raise ConfigError(f"{target}: files.{name}.required_columns must be a list")
        for col in req:
            if not isinstance(col, dict) or "name" not in col:
                raise ConfigError(f"{target}: files.{name} has a column without `name`")

    return InputSchemas(
        version=str(loaded.get("version") or ""),
        files=files,
        invariants=list(loaded.get("invariants") or []),
        forbidden_fields=list(loaded.get("forbidden_fields") or []),
        source_path=str(target),
    )
