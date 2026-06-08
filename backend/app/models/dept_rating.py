import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, ForeignKey,
    Boolean, Text, Uuid, Integer, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class DepartmentRating(Base):
    __tablename__ = "department_ratings"
    __table_args__ = (
        UniqueConstraint("rater_user_id", "department", "period", name="uq_dept_rating_per_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rater_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True,
    )
    department: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(50), nullable=False)
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    teaching_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resources: Mapped[int | None] = mapped_column(Integer, nullable=True)
    environment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
