from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any
import uuid

from app.models.routine import RoutineStatus


class SlotItem(BaseModel):
    day: str = Field(description="e.g. Monday")
    start_time: str = Field(description="e.g. 09:00")
    end_time: str = Field(description="e.g. 10:30")
    course_code: str | None = None
    course_name: str | None = None
    teacher: str | None = None
    room: str | None = None


class RoutineCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    batch: str | None = Field(default=None, max_length=50)
    semester: str | None = Field(default=None, max_length=100)
    academic_year: str | None = Field(default=None, max_length=20)
    slots: list[SlotItem] = Field(default_factory=list)
    tenant_id: uuid.UUID | None = None


class RoutineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    batch: str | None = Field(default=None, max_length=50)
    semester: str | None = Field(default=None, max_length=100)
    academic_year: str | None = Field(default=None, max_length=20)
    slots: list[SlotItem] | None = None


class RoutineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    department: str | None
    batch: str | None
    semester: str | None
    academic_year: str | None
    title: str
    slots: list[Any]
    status: str
    created_by_user_id: uuid.UUID
    published_by_user_id: uuid.UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
