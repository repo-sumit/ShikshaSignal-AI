"""Pydantic schemas for each synthetic CSV.

These document the contract and provide strict row validation used by tests. The loader
(`app.tools.csv_loader`) checks that required columns are present and loads via pandas; the
data-quality tool (`app.tools.data_quality`) flags rows that violate these constraints —
deliberately, since the generator plants a small fraction of broken rows.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

GradeBand = Literal["below", "approaching", "meets", "exceeds"]
TrainingStatus = Literal["not_started", "in_progress", "completed"]
IssueType = Literal["infra", "content", "device", "attendance", "training", "other"]
Severity = Literal["low", "med", "high", "critical"]
IssueStatus = Literal["open", "in_progress", "resolved"]
AssessmentRound = Literal["baseline", "midline", "endline"]


class SchoolRow(BaseModel):
    school_id: str
    school_name: str
    state: str
    district: str
    block: str
    cluster: str
    school_type: str
    lowest_grade: int = Field(ge=1, le=12)
    highest_grade: int = Field(ge=1, le=12)
    enrollment: int = Field(gt=0)
    teachers_count: int = Field(gt=0)
    internet_available: bool
    device_available: bool
    infrastructure_score: float = Field(ge=0, le=100)


class DikshaUsageRow(BaseModel):
    school_id: str
    week: str  # ISO week, e.g. "2026-W18"
    qr_scans: int = Field(ge=0)
    sessions: int = Field(ge=0)
    learning_minutes: int = Field(ge=0)
    active_teachers: int = Field(ge=0)
    active_students_proxy: int = Field(ge=0)


class AssessmentRow(BaseModel):
    school_id: str
    grade: int = Field(ge=1, le=12)
    subject: str
    assessment_round: AssessmentRound
    baseline_score: float = Field(ge=0, le=100)
    current_score: float = Field(ge=0, le=100)
    district_average: float = Field(ge=0, le=100)
    proficiency_band: GradeBand


class TeacherTrainingRow(BaseModel):
    teacher_id: str
    school_id: str
    course_name: str
    status: TrainingStatus
    completion_percent: float = Field(ge=0, le=100)
    assessment_score: float | None = Field(default=None, ge=0, le=100)
    last_activity_date: date


class FieldIssueRow(BaseModel):
    issue_id: str
    school_id: str
    issue_type: IssueType
    severity: Severity
    status: IssueStatus
    reported_by: str
    description: str
    created_at: date
    resolved_at: date | None = None


# Registry consumed by the loader: required columns + the foreign key + the row model.
TABLE_SCHEMAS: dict[str, dict] = {
    "schools": {
        "model": SchoolRow,
        "key": "school_id",
        "required_columns": list(SchoolRow.model_fields.keys()),
    },
    "diksha_usage": {
        "model": DikshaUsageRow,
        "key": "school_id",
        "required_columns": list(DikshaUsageRow.model_fields.keys()),
    },
    "assessments": {
        "model": AssessmentRow,
        "key": "school_id",
        "required_columns": list(AssessmentRow.model_fields.keys()),
    },
    "teacher_training": {
        "model": TeacherTrainingRow,
        "key": "school_id",
        "required_columns": list(TeacherTrainingRow.model_fields.keys()),
    },
    "field_issues": {
        "model": FieldIssueRow,
        "key": "school_id",
        "required_columns": list(FieldIssueRow.model_fields.keys()),
    },
}
