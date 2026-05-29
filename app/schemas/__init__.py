"""Pydantic schemas describing each synthetic CSV (the data contract)."""

from app.schemas.tables import (  # noqa: F401
    AssessmentRow,
    DikshaUsageRow,
    FieldIssueRow,
    SchoolRow,
    TeacherTrainingRow,
    TABLE_SCHEMAS,
)
