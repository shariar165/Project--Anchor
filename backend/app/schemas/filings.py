import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class AdminFilingReviewRequest(BaseModel):
    action: Literal["mark_under_review", "resolve", "dismiss", "escalate", "request_more_info"]
    public_note: str | None = None
    internal_note: str | None = None


class FilingCreate(BaseModel):
    template_key: str
    language: Literal["en", "bn"] = "en"


class FilingUpdate(BaseModel):
    body: str | None = None
    field_values: dict | None = None
    language: Literal["en", "bn"] | None = None


class FilingSubmitRequest(BaseModel):
    pass


class AnonymousLookupRequest(BaseModel):
    tracking_code: str


class SubjectRespondRequest(BaseModel):
    response_text: str = Field(..., min_length=10)


class ClassroomReportCreate(BaseModel):
    classroom_ref: str = Field(..., min_length=1, max_length=100)
    issue_type: Literal["projector", "ac", "seating", "lighting", "door", "cleanliness", "sound", "other"]
    notes: str | None = None


# ── Responses ─────────────────────────────────────────────────────────────────

class FilingTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    name_bn: str
    category: str
    anonymity_mode: str
    routing_target: str
    requires_stepup: bool
    goes_to_moderation_queue: bool
    proof_required: bool
    proof_hint: str | None
    subject_response_window_days: int
    default_escalation_days: int
    active: bool


class FilingAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    sha256_hash: str
    explain_cache: str | None
    uploaded_at: datetime


class FilingReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reviewer_role: str
    action: str
    public_note: str | None
    reviewed_at: datetime


class SubjectResponseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    response_text: str
    notified_at: datetime
    responded_at: datetime | None
    response_window_ends_at: datetime


class FilingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filing_number: str | None
    category: str
    language: str
    body: str | None
    field_values: dict
    ai_assisted: bool
    state: str
    priority: str
    anonymous_tracking_code: str | None
    subject_descriptor: str | None
    escalation_level: int
    state_entered_at: datetime | None
    submitted_at: datetime | None
    finalized_at: datetime | None
    final_outcome_note: str | None
    created_at: datetime
    updated_at: datetime
    template: FilingTemplateResponse | None = None
    attachments: list[FilingAttachmentResponse] = []
    reviews: list[FilingReviewResponse] = []
    subject_responses: list[SubjectResponseResponse] = []


class FilingListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filing_number: str | None
    category: str
    state: str
    language: str
    created_at: datetime
    updated_at: datetime
    template: FilingTemplateResponse | None = None


class AnonymousLookupResponse(BaseModel):
    filing_number: str
    state: str
    final_outcome_note: str | None


class ClassroomReportAgg(BaseModel):
    classroom_ref: str
    issue_type: str
    count: int


class FilingTimelineEntry(BaseModel):
    event: str
    actor_role: str | None
    note: str | None
    timestamp: datetime


class FilingTimelineResponse(BaseModel):
    filing_id: uuid.UUID
    state: str
    entries: list[FilingTimelineEntry]


class ExplainResponse(BaseModel):
    explanation: str
    document_type_detected: str
    language: str
