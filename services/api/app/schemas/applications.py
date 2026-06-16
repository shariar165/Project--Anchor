import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    template_id: uuid.UUID
    field_values: dict = Field(default_factory=dict)
    language: Literal["en", "bn"] = "en"


class ApplicationUpdate(BaseModel):
    field_values: dict | None = None
    letter_body: str | None = None
    language: Literal["en", "bn"] | None = None


class SubmitRequest(BaseModel):
    first_approver_choice: Literal["mentor", "department_head"]


class ResubmitRequest(BaseModel):
    pass


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected", "changes_requested"]
    notes: str | None = None


class CampusSettingsPatch(BaseModel):
    mentor_user_id: uuid.UUID | None = None
    department: str | None = None


class AIDraftRequest(BaseModel):
    language: Literal["en", "bn"] | None = None


# ── Responses ─────────────────────────────────────────────────────────────────

class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    name_bn: str
    skill_reference: str
    default_escalation_days: int
    requires_accounts_approval: bool
    proof_hint: str | None
    active: bool


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    sha256_hash: str
    explain_cache: str | None
    uploaded_at: datetime


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reviewer_role: str
    decision: str
    notes: str | None
    reviewed_at: datetime


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_id: uuid.UUID
    field_values: dict
    letter_body: str | None
    language: str
    state: str
    first_approver_type: str | None
    current_approver_level: str | None
    round_count: int
    escalated_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    pdf_ref: str | None
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentResponse] = []
    reviews: list[ReviewResponse] = []
    template: TemplateResponse | None = None


class ApplicationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    state: str
    language: str
    current_approver_level: str | None
    round_count: int
    created_at: datetime
    updated_at: datetime
    template: TemplateResponse | None = None


class AdminApplicationListItem(BaseModel):
    """Row in the admin application queue."""
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str | None = None
    state: str
    language: str
    current_approver_level: str | None
    requires_accounts_approval: bool = False
    round_count: int
    template_name: str | None = None
    template_key: str | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationStatsResponse(BaseModel):
    mentor: int = 0
    department_head: int = 0
    dean: int = 0
    accounts: int = 0
    decided: int = 0


class CampusSettingsResponse(BaseModel):
    user_id: uuid.UUID
    department: str | None
    mentor_user_id: uuid.UUID | None
    mentor_name: str | None = None
    department_locked: bool
    updated_at: datetime


class AvailableMentorItem(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str | None


class AIDraftResponse(BaseModel):
    letter_body: str
    generated_at: datetime


class ExplainResponse(BaseModel):
    explanation: str
    document_type_detected: str
    language: str


class TimelineEntry(BaseModel):
    event: str
    actor_role: str | None
    note: str | None
    timestamp: datetime


class TimelineResponse(BaseModel):
    application_id: uuid.UUID
    state: str
    entries: list[TimelineEntry]
