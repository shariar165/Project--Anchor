import uuid
from sqlalchemy import String, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class PlatformConfig(Base, TimestampMixin):
    """Platform-wide super-admin configuration, stored one row per section.

    Each row holds a JSON blob for a config section (e.g. "escalation",
    "rate_limits", "ai_thresholds"). Reads deep-merge stored rows over
    DEFAULT_PLATFORM_CONFIG so the API always returns sensible values, even
    before anything has been saved. These values are *stored & managed* here;
    wiring them into live runtime enforcement is a separate concern.

    JSON column type works on both PostgreSQL and the SQLite test path.
    """
    __tablename__ = "platform_config"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
