import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, ForeignKey, Boolean, Text, JSON, Uuid, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


# Notification "type" — matches the NOTIF_TYPE_META keys in apps/student/src/screens-2.jsx.
NOTIFICATION_TYPES = frozenset({"alert", "case", "notice", "rating", "lawyer", "zone"})

# Notification "mode" — campus | country. NULL means "show in both modes" (e.g. safety alerts).
NOTIFICATION_MODES = frozenset({"campus", "country"})

# type -> preference category used for enforcement (see NotificationPreference).
TYPE_PREF_MAP: dict[str, str] = {
    "alert": "alerts",
    "zone": "alerts",
    "case": "cases",
    "lawyer": "cases",
    "notice": "notices",
    "rating": "notices",
}


class Notification(Base):
    """A single in-app notification delivered to one user."""
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # campus | country | NULL (NULL = visible in both modes)
    mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # In-app navigation target (route name + params consumed by the student app router).
    route: Mapped[str | None] = mapped_column(String(50), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )


class NotificationPreference(Base):
    """Per-user notification preferences. One row per user, lazily created.

    The five boolean columns gate generation of the matching notification types
    (see TYPE_PREF_MAP). `channels` holds free-form admin channel toggles
    (push/email/sms) persisted from the admin settings panel — stored-but-inert
    where no delivery channel exists yet.
    """
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
    )
    alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    cases: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notices: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    feed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Admin channel prefs (free-form JSON) — push/email/sms toggles + quiet hours.
    channels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
