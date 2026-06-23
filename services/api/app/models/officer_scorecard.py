import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, Float, ForeignKey,
    Boolean, Integer, Text, Uuid, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


# National-mode police accountability scorecard.
# Public read; ratings are submitted by authenticated users and held in a
# moderation queue (status string, not a PG enum) — only `approved` ratings
# count toward the public aggregate.
RATING_STATES = ("pending", "approved", "rejected")


class PoliceStation(Base):
    __tablename__ = "police_stations"
    __table_args__ = (
        UniqueConstraint("name", "district", name="uq_police_station_name_district"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    division: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class Officer(Base):
    __tablename__ = "officers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("police_stations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rank: Mapped[str | None] = mapped_column(String(100), nullable=True)
    badge_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class OfficerRating(Base):
    __tablename__ = "officer_ratings"
    __table_args__ = (
        UniqueConstraint(
            "rater_user_id", "station_id", "officer_id", name="uq_officer_rating_per_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rater_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("police_stations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    officer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("officers.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    responsiveness: Mapped[int] = mapped_column(Integer, nullable=False)
    conduct: Mapped[int] = mapped_column(Integer, nullable=False)
    integrity: Mapped[int] = mapped_column(Integer, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    anonymous: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="pending", server_default="pending", index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True,
    )
