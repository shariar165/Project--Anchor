import uuid
from sqlalchemy import String, Boolean, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Display/onboarding metadata. status shown in the admin UI is derived:
    # not active -> "Suspended"; tier == "pilot" -> "Pilot"; else "Active".
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", default="active")
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, server_default="Bangladesh")
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # RAG/ChromaDB namespace for this tenant's documents (defaults to slug).
    vector_namespace: Mapped[str | None] = mapped_column(String(100), nullable=True)

    email_domains = relationship("TenantEmailDomain", back_populates="tenant", cascade="all, delete-orphan")


class TenantEmailDomain(Base):
    __tablename__ = "tenant_email_domains"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(253), unique=True, nullable=False, index=True)

    tenant = relationship("Tenant", back_populates="email_domains")
