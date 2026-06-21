"""Platform incident tracker (super-admin operations).

A lightweight, persistent incident log: severity, lifecycle status, the affected
component, and an append-only timeline of updates. Platform-wide by default
(``tenant_id`` nullable) since incidents usually span the whole platform, but a
tenant can be attached when an incident is scoped to one university.

Status strings are kept as a plain ``String`` column (not a DB enum) to mirror
the project's draft/publish pattern (see notes in services/api/CLAUDE.md) and to
keep the SQLite test path free of enum DDL.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

# Valid value sets — validated in the router, stored as plain strings.
INCIDENT_SEVERITIES = ("sev1", "sev2", "sev3", "sev4")
INCIDENT_STATUSES = ("investigating", "identified", "monitoring", "resolved")
OPEN_STATUSES = ("investigating", "identified", "monitoring")


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # sev1 (critical) … sev4 (low)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, server_default="sev3", index=True)
    # investigating | identified | monitoring | resolved
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="investigating", index=True)
    # Affected subsystem label, e.g. "RAG", "API", "Push", "Database".
    component: Mapped[str | None] = mapped_column(String(60), nullable=True)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    postmortem: Mapped[str | None] = mapped_column(Text, nullable=True)

    updates = relationship(
        "IncidentUpdate",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentUpdate.created_at",
    )


class IncidentUpdate(Base):
    """One entry in an incident's timeline — a status change and/or a note."""
    __tablename__ = "incident_updates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    incident = relationship("Incident", back_populates="updates")
