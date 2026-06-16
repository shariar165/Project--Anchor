from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid

from app.models.notice import NoticeScope


class NoticeCreate(BaseModel):
    scope: NoticeScope
    dept: str | None = Field(default=None, max_length=100)
    batch: str | None = Field(default=None, max_length=20)
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1)
    tenant_id: uuid.UUID | None = None
    expires_at: datetime | None = None


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    scope: NoticeScope | None = None
    dept: str | None = Field(default=None, max_length=100)
    batch: str | None = Field(default=None, max_length=20)
    expires_at: datetime | None = None


class NoticeGenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    language: str = Field(default="en", pattern="^(en|bn)$")
    tone: str | None = Field(default=None, max_length=100)
    audience: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, max_length=200)


class NoticeGenerateResponse(BaseModel):
    subject: str
    body: str
    language: str
    ai_generated: bool


class NoticeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    scope: str
    dept: str | None
    batch: str | None
    title: str
    body: str
    published_by_user_id: uuid.UUID
    is_active: bool
    status: str
    published_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
