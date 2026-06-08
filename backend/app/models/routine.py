import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    String, DateTime, Enum, ForeignKey,
    Text, Uuid, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class RoutineStatus(str, PyEnum):
    draft     = "draft"
    published = "published"
    archived  = "archived"


class AcademicRoutine(Base):
    __tablename__ = "academic_routines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True,
    )
    department: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    batch: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    semester: Mapped[str | None] = mapped_column(String(100), nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[RoutineStatus] = mapped_column(
        Enum(RoutineStatus, name="routinestatus"), nullable=False,
        default=RoutineStatus.draft, index=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
