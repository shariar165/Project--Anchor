import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, LargeBinary, func, Text, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class AuditLog(Base):
    """Append-only audit log with SHA-256 hash chain. No updated_at — immutable rows."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    row_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user = relationship("User", back_populates="audit_logs")
