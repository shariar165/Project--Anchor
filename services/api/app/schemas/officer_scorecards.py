from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid


class StationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    district: str
    division: str | None
    address: str | None
    lat: float | None
    lng: float | None
    # Aggregate (approved ratings only) — populated by the service
    total_count: int = 0
    avg_overall: float | None = None


class OfficerSummary(BaseModel):
    id: uuid.UUID
    name: str
    rank: str | None
    badge_no: str | None
    total_count: int
    avg_overall: float | None


class StationSummary(BaseModel):
    id: uuid.UUID
    name: str
    district: str
    division: str | None
    address: str | None
    total_count: int
    avg_overall: float | None
    avg_responsiveness: float | None
    avg_conduct: float | None
    avg_integrity: float | None
    histogram: dict[str, int]
    officers: list[OfficerSummary]


class OfficerRatingCreate(BaseModel):
    station_id: uuid.UUID
    officer_id: uuid.UUID | None = None
    responsiveness: int = Field(ge=1, le=5)
    conduct: int = Field(ge=1, le=5)
    integrity: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    anonymous: bool = False


class OfficerRatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rater_user_id: uuid.UUID | None
    station_id: uuid.UUID
    officer_id: uuid.UUID | None
    responsiveness: int
    conduct: int
    integrity: int
    overall: int
    comment: str | None
    anonymous: bool
    status: str
    created_at: datetime

    @classmethod
    def from_orm_masked(cls, obj) -> "OfficerRatingResponse":
        data = cls.model_validate(obj)
        if data.anonymous:
            data.rater_user_id = None
        return data


class RatingModerationItem(BaseModel):
    """Admin-facing view of a rating awaiting moderation (identity always visible)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    station_id: uuid.UUID
    station_name: str | None = None
    officer_id: uuid.UUID | None
    officer_name: str | None = None
    responsiveness: int
    conduct: int
    integrity: int
    overall: int
    comment: str | None
    anonymous: bool
    status: str
    created_at: datetime


class ModerateRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
