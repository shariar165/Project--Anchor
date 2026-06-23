import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, ForeignKey,
    Boolean, Text, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


# National-mode police report drafting (Bangladesh GD / FIR).
# Distinct from the campus Filing system: no tenant_id, no routing/moderation —
# the user drafts, finalizes, exports a print-ready document, and takes it to the
# thana themselves (there is no public police-filing API in Bangladesh).
#
# Lifecycle (string column, not a PG enum — mirrors lawyers.status):
#   draft -> finalized -> filed_by_user
REPORT_TYPES = ("gd", "fir")
REPORT_STATES = ("draft", "finalized", "filed_by_user")
INCIDENT_TYPES = (
    "theft", "snatching", "harassment", "threat",
    "lost_document", "cyber", "assault", "fraud", "other",
)


class PoliceReport(Base):
    __tablename__ = "police_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    report_type: Mapped[str] = mapped_column(String(8), nullable=False, default="gd")
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft", index=True,
    )
    reference_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    # Complainant
    complainant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    nid: Mapped[str | None] = mapped_column(String(40), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Incident
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    incident_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    incident_datetime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    thana: Mapped[str | None] = mapped_column(String(200), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)

    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    accused_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    witnesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    property_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    language: Mapped[str] = mapped_column(String(2), nullable=False, default="en", server_default="en")
    ai_assisted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
