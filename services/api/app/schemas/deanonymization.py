import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ── Requests ────────────────────────────────────────────────────────────────

class DeanonRequestCreate(BaseModel):
    target_type: Literal["filing", "alert"]
    target_ref: str = Field(..., min_length=3, max_length=50, description="filing_number or alert event_id")
    legal_basis: str = Field(..., min_length=3, max_length=200)
    reason: str = Field(..., min_length=10)
    formal_letter_ref: str | None = Field(default=None, max_length=200)


class DeanonDecision(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class DeanonDenyRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


# ── Responses ───────────────────────────────────────────────────────────────

class DeanonApprover(BaseModel):
    user_id: str | None = None
    masked_email: str | None = None
    at: datetime | None = None


class DeanonRequestOut(BaseModel):
    id: str
    request_number: str
    target_type: str
    target_ref: str
    tenant_id: str | None = None
    requester_label: str
    requester_user_id: str | None = None
    legal_basis: str
    reason: str
    formal_letter_ref: str | None = None
    status: str
    first_approval: DeanonApprover | None = None
    second_approval: DeanonApprover | None = None
    denied_reason: str | None = None
    decided_at: datetime | None = None
    access_expires_at: datetime | None = None
    created_at: datetime


class DeanonListResponse(BaseModel):
    items: list[DeanonRequestOut]
    total: int
    limit: int
    offset: int


class DeanonStats(BaseModel):
    pending_review: int = 0
    awaiting_second_approval: int = 0
    approved: int = 0
    denied: int = 0
    expired: int = 0
    open_total: int = 0  # pending_review + awaiting_second_approval


class DeanonRevealResponse(BaseModel):
    request_id: str
    request_number: str
    user_id: str | None
    full_name: str | None
    email: str | None
    masked_email: str | None
    role: str | None
    tenant_id: str | None
    access_expires_at: datetime | None
