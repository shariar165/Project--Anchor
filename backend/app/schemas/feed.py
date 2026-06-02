import uuid
from datetime import datetime
from typing import Literal, Any

from pydantic import BaseModel, ConfigDict, Field


# ─── Request schemas ──────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    scope: Literal["campus", "national"]
    category: Literal["incident", "missing_person", "road", "safety", "civic_event"]
    title: str = Field(min_length=5, max_length=100)
    body: str = Field(min_length=20, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=5)
    geo_lat: float | None = Field(default=None, ge=-90, le=90)
    geo_lng: float | None = Field(default=None, ge=-180, le=180)
    geo_address: str | None = Field(default=None, max_length=300)


class PostEdit(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=100)
    body: str | None = Field(default=None, min_length=20, max_length=1000)
    tags: list[str] | None = Field(default=None, max_length=5)
    geo_lat: float | None = Field(default=None, ge=-90, le=90)
    geo_lng: float | None = Field(default=None, ge=-180, le=180)
    geo_address: str | None = Field(default=None, max_length=300)


class SignalRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class FlagRequest(BaseModel):
    flag_reason: Literal[
        "harassment", "off_topic", "wrong_category", "illegal_content", "spam", "other"
    ]
    note: str | None = Field(default=None, max_length=500)


class AdminActionRequest(BaseModel):
    internal_note: str | None = Field(default=None, max_length=2000)
    public_note: str | None = Field(default=None, max_length=500)


class PromoteToZoneRequest(AdminActionRequest):
    zone_id: uuid.UUID


# ─── Response schemas ─────────────────────────────────────────────────────────

class AttachmentInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_hash_sha256: str
    content_type: str
    file_size_bytes: int
    uploaded_at: datetime


class SignalCountsResponse(BaseModel):
    corroborate: int = 0
    challenge: int = 0
    flags: int = 0
    user_signal: str | None = None


class TrustBadgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    trust_tier: str
    confirmed_accurate_count: int
    confirmed_fake_count: int


class PostListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_number: str
    scope: str
    category: str
    title: str
    state: str
    admin_confirmed: bool
    created_at: datetime
    signal_counts: SignalCountsResponse | None = None


class PostDetail(PostListItem):
    publisher_user_id: uuid.UUID
    body: str
    tags: list[str] = []
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_address: str | None = None
    admin_confirmed_at: datetime | None = None
    zone_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    updated_at: datetime
    attachments: list[AttachmentInfo] = []


class FeedProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    trust_tier: str
    confirmed_accurate_count: int
    confirmed_fake_count: int
    last_recalculated_at: datetime


class PublishResponse(BaseModel):
    post_id: uuid.UUID
    post_number: str
    state: str
    ai_verdict: str | None
    message: str


class SignalResponse(BaseModel):
    action: str
    signal_type: str
    counts: SignalCountsResponse


class AdminQueueItem(PostListItem):
    flag_count: int = 0
    publisher_trust_tier: str = "none"
    tenant_id: uuid.UUID | None = None


class AdminPostReview(PostDetail):
    flags: list[dict[str, Any]] = []
    moderation_history: list[dict[str, Any]] = []
    publisher_trust: TrustBadgeResponse | None = None
    tenant_id: uuid.UUID | None = None
