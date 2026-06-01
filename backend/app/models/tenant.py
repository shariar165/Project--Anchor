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

    email_domains = relationship("TenantEmailDomain", back_populates="tenant", cascade="all, delete-orphan")


class TenantEmailDomain(Base):
    __tablename__ = "tenant_email_domains"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(253), unique=True, nullable=False, index=True)

    tenant = relationship("Tenant", back_populates="email_domains")
