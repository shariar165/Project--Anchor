import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, ForeignKey,
    Boolean, Text, Uuid, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Lawyer(Base):
    __tablename__ = "lawyers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Links the directory entry to its login account. Null for legacy directory-only rows.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    bar_number: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    specializations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Application workflow: pending -> verified | rejected. `verified` bool stays in sync with
    # status == "verified" and remains the canonical public-directory flag.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending", index=True,
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
