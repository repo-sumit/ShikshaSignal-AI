"""Tests for the declarative input schema spec in ``schemas/input_schemas.yaml``."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas import TABLE_SCHEMAS
from app.services.config_loader import (
    INPUT_SCHEMAS_PATH,
    ConfigError,
    InputSchemas,
    load_input_schemas,
)


# ---------------------------------------------------------------------------
# Presence + shape
# ---------------------------------------------------------------------------


def test_input_schemas_file_exists():
    assert INPUT_SCHEMAS_PATH.exists(), (
        f"input_schemas.yaml is required by Milestone 7 but is missing at {INPUT_SCHEMAS_PATH}"
    )


def test_input_schemas_loads_cleanly():
    schemas = load_input_schemas()
    assert isinstance(schemas, InputSchemas)
    assert schemas.version
    assert schemas.files


def test_input_schemas_covers_every_csv_in_table_schemas():
    """The declarative YAML must describe every CSV the Pydantic registry knows about."""
    schemas = load_input_schemas()
    assert set(schemas.files.keys()) == set(TABLE_SCHEMAS.keys()), (
        f"YAML files set {set(schemas.files.keys())} differs from TABLE_SCHEMAS "
        f"{set(TABLE_SCHEMAS.keys())}"
    )


def test_each_file_has_required_columns():
    schemas = load_input_schemas()
    for name, spec in schemas.files.items():
        req = spec.get("required_columns") or []
        assert req, f"{name}: required_columns is empty"
        for col in req:
            assert "name" in col, f"{name}: every column needs a `name` field"


def test_yaml_required_columns_match_pydantic_models():
    """Drift between YAML and Pydantic would be silent. Verify per file."""
    schemas = load_input_schemas()
    for name, registry in TABLE_SCHEMAS.items():
        yaml_cols = set(schemas.required_columns(name))
        pydantic_cols = set(registry["required_columns"])
        assert yaml_cols == pydantic_cols, (
            f"{name}: required columns drift\n"
            f"  YAML only:     {yaml_cols - pydantic_cols}\n"
            f"  Pydantic only: {pydantic_cols - yaml_cols}"
        )


# ---------------------------------------------------------------------------
# Per-file specifics
# ---------------------------------------------------------------------------


def test_schools_has_pk_school_id():
    schemas = load_input_schemas()
    assert schemas.files["schools"]["primary_key"] == "school_id"


def test_diksha_usage_has_composite_pk_and_fk_to_schools():
    schemas = load_input_schemas()
    spec = schemas.files["diksha_usage"]
    assert spec["primary_key"] == ["school_id", "week"]
    fks = spec.get("foreign_keys") or []
    assert any(fk.get("references") == "schools.school_id" for fk in fks)


def test_assessment_round_has_enum_values():
    schemas = load_input_schemas()
    spec = schemas.files["assessments"]
    cols = {c["name"]: c for c in spec["required_columns"]}
    round_spec = cols.get("assessment_round")
    assert round_spec is not None
    assert round_spec.get("type") == "enum"
    assert set(round_spec.get("enums", [])) == {"baseline", "midline", "endline"}


def test_field_issues_severity_enum():
    schemas = load_input_schemas()
    spec = schemas.files["field_issues"]
    cols = {c["name"]: c for c in spec["required_columns"]}
    sev = cols.get("severity")
    assert sev is not None and sev.get("type") == "enum"
    assert {"low", "med", "high", "critical"}.issubset(set(sev.get("enums", [])))


# ---------------------------------------------------------------------------
# Invariants + safety
# ---------------------------------------------------------------------------


def test_input_schemas_lists_cross_file_invariants():
    schemas = load_input_schemas()
    assert schemas.invariants, "invariants list should not be empty"
    # The two most important invariants are explicit.
    blob = " ".join(schemas.invariants).lower()
    assert "school_id" in blob
    assert "future" in blob or "reference_date" in blob


def test_input_schemas_lists_forbidden_fields():
    schemas = load_input_schemas()
    # Safety position: synthetic-only / no PII / no government student IDs.
    forbidden_blob = " ".join(schemas.forbidden_fields).lower()
    assert "aadhaar" in forbidden_blob
    assert "apaar" in forbidden_blob or "real teacher" in forbidden_blob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_known_columns_helper():
    schemas = load_input_schemas()
    known = schemas.known_columns("schools")
    assert "school_id" in known
    assert "school_name" in known


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_input_schemas(tmp_path / "absent.yaml")


def test_malformed_yaml_raises_config_error(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("not: [valid: yaml", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_input_schemas(p)


def test_missing_files_block_raises_config_error(tmp_path):
    p = tmp_path / "no_files.yaml"
    p.write_text("version: '1.0'\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="files"):
        load_input_schemas(p)
