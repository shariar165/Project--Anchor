from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any
import uuid


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mode: str | None
    type: str
    title: str
    body: str
    route: str | None
    params: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationPrefs(BaseModel):
    """Student feed-category toggles (gate generation) + optional admin channels blob."""
    model_config = ConfigDict(from_attributes=True)

    alerts: bool = True
    cases: bool = True
    notices: bool = True
    feed: bool = True
    marketing: bool = False


class NotificationPrefsUpdate(BaseModel):
    alerts: bool | None = None
    cases: bool | None = None
    notices: bool | None = None
    feed: bool | None = None
    marketing: bool | None = None


class AdminChannelPrefs(BaseModel):
    """Free-form admin notification channel settings (push/email/sms + quiet hours)."""
    model_config = ConfigDict(extra="allow")

    channels: dict[str, Any] = Field(default_factory=dict)
