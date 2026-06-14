import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    String, DateTime, Enum, ForeignKey,
    Boolean, Text, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class NoticeScope(str, PyEnum):
    university = "university"
    dept       = "dept"
    batch      = "batch"


class NoticeStatus(str, PyEnum):
    draft     = "draft"
    published = "published"
    archived  = "archived"


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True,
    )
    scope: Mapped[NoticeScope] = mapped_column(
        Enum(NoticeScope, name="noticescope"), nullable=False, index=True,
    )
    dept: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    batch: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    published_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    status: Mapped[NoticeStatus] = mapped_column(
        Enum(NoticeStatus, name="noticestatus"), nullable=False,
        default=NoticeStatus.draft, index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
