import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class DMSRecord(Base, TimestampMixin):
    """Dead Man's Switch — periodic check-in to prevent auto-delete of account."""
    __tablename__ = "dms_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    check_in_interval_days: Mapped[int] = mapped_column(nullable=False, default=30)
    last_check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="notify")
