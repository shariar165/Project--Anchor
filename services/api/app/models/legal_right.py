import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey,
    Boolean, Text, Uuid, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class LegalRight(Base):
    """A single Bangladesh-law explainer card shown in the national-mode
    "Know your rights" feature. Content is bilingual (EN + BN); the frontend
    picks the active language from the app-wide lang toggle."""

    __tablename__ = "legal_rights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # Bilingual content — *_en is canonical, *_bn optional (frontend falls back to EN)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    title_bn: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary_en: Mapped[str] = mapped_column(Text, nullable=False)
    summary_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    full_text_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    penalty_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    penalty_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    where_to_invoke_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    where_to_invoke_bn: Mapped[str | None] = mapped_column(Text, nullable=True)

    citation: Mapped[str] = mapped_column(String(200), nullable=False)
    # steps: list of {"en": str, "bn": str} action items
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Frontend keys: selects the SVG infographic scene + accent color
    illustration: Mapped[str] = mapped_column(String(40), nullable=False, default="scale")
    accent: Mapped[str] = mapped_column(String(9), nullable=False, default="#C44536")

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
