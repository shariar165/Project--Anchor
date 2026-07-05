import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


# ── Terms ────────────────────────────────────────────────────────────────────

class TermCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    tenant_id: uuid.UUID | None = None

class TermPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None

class TermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Batches / Sections / Lab Groups ──────────────────────────────────────────

class BatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    program: str = Field(default="SWE", max_length=20)
    tenant_id: uuid.UUID | None = None

class BatchPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    program: str | None = Field(default=None, max_length=20)
    active: bool | None = None

class LabGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    section_id: uuid.UUID
    name: str

class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    batch_id: uuid.UUID
    name: str
    lab_groups: list[LabGroupOut] = []

class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    program: str
    active: bool
    sections: list[SectionOut] = []

class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=10)

class LabGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=10)

class GenerateStructureRequest(BaseModel):
    count: int = Field(ge=1, le=26)
    lab_split: bool = True


# ── Rooms ─────────────────────────────────────────────────────────────────────

class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    room_type: str = Field(pattern="^(THEORY|LAB|ONLINE)$")
    capacity: int = Field(default=30, ge=1)
    tenant_id: uuid.UUID | None = None

class RoomPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    room_type: str | None = Field(default=None, pattern="^(THEORY|LAB|ONLINE)$")
    capacity: int | None = Field(default=None, ge=1)

class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    room_type: str
    capacity: int


# ── Courses ───────────────────────────────────────────────────────────────────

class CourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    credits: int = Field(ge=1, le=10)
    is_lab: bool
    weekly_classes: int = Field(ge=1, le=10)
    tenant_id: uuid.UUID | None = None

class CoursePatch(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    credits: int | None = Field(default=None, ge=1, le=10)
    is_lab: bool | None = None
    weekly_classes: int | None = Field(default=None, ge=1, le=10)

class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    code: str
    name: str
    credits: int
    is_lab: bool
    weekly_classes: int


# ── Faculty profiles ──────────────────────────────────────────────────────────

VALID_RANKS = {
    "LECTURER", "SENIOR_LECTURER", "ASSISTANT_PROF",
    "ASSOCIATE_PROF", "PROFESSOR", "HOD",
    "PHD_STUDENT", "MASTERS_STUDENT",
}

class FacultyProfileCreate(BaseModel):
    user_id: uuid.UUID | None = None          # optional — link a login account when one exists
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    rank: str = Field(min_length=1, max_length=30)
    min_credits: int | None = Field(default=None, ge=0)
    max_credits: int | None = Field(default=None, ge=0)
    pref_slot: int | None = Field(default=None, ge=0)
    off_days: list[int] = Field(default_factory=list)
    max_per_day: int = Field(default=4, ge=1, le=10)
    tenant_id: uuid.UUID | None = None

class FacultyProfilePatch(BaseModel):
    rank: str | None = Field(default=None, min_length=1, max_length=30)
    min_credits: int | None = Field(default=None, ge=0)
    max_credits: int | None = Field(default=None, ge=0)
    pref_slot: int | None = None
    off_days: list[int] | None = None
    max_per_day: int | None = Field(default=None, ge=1, le=10)
    active: bool | None = None

class FacultyProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID | None
    tenant_id: uuid.UUID | None
    name: str | None
    email: str | None
    rank: str
    min_credits: int | None
    max_credits: int | None
    pref_slot: int | None
    off_days: list[Any]
    max_per_day: int
    active: bool


# ── Offerings & eligibility ───────────────────────────────────────────────────

class OfferingCreate(BaseModel):
    term_id: uuid.UUID
    course_id: uuid.UUID
    batch_id: uuid.UUID

class OfferingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    term_id: uuid.UUID
    course_id: uuid.UUID
    batch_id: uuid.UUID
    # Human-readable labels for the admin table (populated by the service layer).
    course_code: str | None = None
    batch_name: str | None = None
    term_name: str | None = None

class EligibilityCreate(BaseModel):
    faculty_id: uuid.UUID
    course_id: uuid.UUID

class EligibilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    faculty_id: uuid.UUID
    course_id: uuid.UUID
    # Human-readable labels for the admin table (populated by the service layer).
    course_code: str | None = None
    faculty_name: str | None = None


# ── Schedule config ───────────────────────────────────────────────────────────

class ScheduleConfigUpsert(BaseModel):
    days: list[str] = Field(min_length=1)
    slots: list[str] = Field(min_length=1)
    off_days: list[str] = Field(default_factory=list)
    term_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None

class ScheduleConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    term_id: uuid.UUID | None
    days: list[Any]
    slots: list[Any]
    off_days: list[Any]


# ── Constraints ───────────────────────────────────────────────────────────────

class ConstraintCreate(BaseModel):
    constraint_type: str = Field(min_length=1, max_length=50)
    scope: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)
    enforcement: str = Field(pattern="^(hard|soft)$")
    weight: int | None = Field(default=None, ge=1, le=1000)
    term_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None

class ConstraintPatch(BaseModel):
    enabled: bool | None = None
    weight: int | None = Field(default=None, ge=1, le=1000)
    enforcement: str | None = Field(default=None, pattern="^(hard|soft)$")
    params: dict | None = None

class ConstraintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    term_id: uuid.UUID | None
    constraint_type: str
    scope: dict
    params: dict
    enforcement: str
    weight: int | None
    enabled: bool
    created_by: uuid.UUID | None
    created_at: datetime


# ── Solve jobs ────────────────────────────────────────────────────────────────

class SolveRequest(BaseModel):
    term_id: uuid.UUID
    time_limit_s: int = Field(default=60, ge=10, le=600)
    seed_from_version: int | None = None

class SolveJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_id: uuid.UUID
    status: str
    progress: int
    solver_status: str | None
    infeasible_core: list[str] | None
    result_version: int | None
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_orm_job(cls, job):
        return cls(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            solver_status=job.solver_status,
            infeasible_core=[str(x) for x in job.infeasible_core] if job.infeasible_core else None,
            result_version=job.result_version,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


# ── Entries ───────────────────────────────────────────────────────────────────

class EntryEdit(BaseModel):
    entry_id: uuid.UUID | None = None
    new_day: int | None = Field(default=None, ge=0, le=5)
    new_slot: int | None = Field(default=None, ge=0)
    new_faculty_id: uuid.UUID | None = None
    new_room_id: uuid.UUID | None = None
    lock: bool = True

class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    term_id: uuid.UUID
    result_version: int
    course_id: uuid.UUID
    section_id: uuid.UUID
    lab_group_id: uuid.UUID | None
    faculty_id: uuid.UUID
    room_id: uuid.UUID
    day: int
    slot: int
    is_lab: bool
    locked: bool
    source: str
    published: bool

class EntryDetailOut(BaseModel):
    """Entry with resolved names for grid display."""
    id: uuid.UUID
    term_id: uuid.UUID
    result_version: int
    course_code: str
    course_name: str
    section_name: str
    batch_name: str
    lab_group_name: str | None
    faculty_name: str
    room_name: str
    room_type: str
    day: int
    slot: int
    is_lab: bool
    locked: bool
    source: str
    published: bool
    # raw IDs for edit forms
    course_id: uuid.UUID
    section_id: uuid.UUID
    lab_group_id: uuid.UUID | None
    faculty_id: uuid.UUID
    room_id: uuid.UUID


# ── Resolve / NL edit ─────────────────────────────────────────────────────────

class ResolveRequest(BaseModel):
    term_id: uuid.UUID
    base_version: int
    change: EntryEdit
    keep_locked: bool = True
    time_limit_s: int = Field(default=60, ge=10, le=600)

class NLEditRequest(BaseModel):
    term_id: uuid.UUID
    base_version: int
    text: str = Field(min_length=1, max_length=500)


# ── Publish / Validate ────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    term_id: uuid.UUID
    version: int

class ConflictOut(BaseModel):
    conflict_type: str
    entry_ids: list[uuid.UUID]
    description: str

class ValidateOut(BaseModel):
    version: int
    conflicts: list[ConflictOut]
    hard_count: int
    soft_count: int

class PublishOut(BaseModel):
    published_routines: int
    routine_ids: list[uuid.UUID]


# ── Import ────────────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    entity: str
    created: int
    total: int = 0           # rows parsed (excluding header + blank rows)
    error_count: int = 0     # true number of errors (errors[] below may be capped)
    errors: list[str]
