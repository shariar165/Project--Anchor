from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
import uuid


class DepartmentRatingCreate(BaseModel):
    department: str = Field(min_length=1, max_length=200)
    period: str = Field(min_length=1, max_length=50, description="e.g. 'Spring-2026' or 'Year-2025'")
    overall: int = Field(ge=1, le=5)
    teaching_quality: int | None = Field(default=None, ge=1, le=5)
    resources: int | None = Field(default=None, ge=1, le=5)
    environment: int | None = Field(default=None, ge=1, le=5)
    feedback: str | None = None
    anonymous: bool = False


class DepartmentRatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rater_user_id: uuid.UUID | None
    tenant_id: uuid.UUID | None
    department: str
    period: str
    overall: int
    teaching_quality: int | None
    resources: int | None
    environment: int | None
    feedback: str | None
    anonymous: bool
    created_at: datetime

    @classmethod
    def from_orm_masked(cls, obj) -> "DepartmentRatingResponse":
        data = cls.model_validate(obj)
        if data.anonymous:
            data.rater_user_id = None
        return data


class DepartmentSummary(BaseModel):
    department: str
    total_count: int
    avg_overall: float | None
    avg_teaching: float | None
    avg_resources: float | None
    avg_environment: float | None
    histogram: dict[str, int]
