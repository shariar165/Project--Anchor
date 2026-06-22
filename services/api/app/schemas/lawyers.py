from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid


class LawyerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    bar_number: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    district: str | None = Field(default=None, max_length=100)
    specializations: list[str] = Field(default_factory=list)
    bio: str | None = None
    tenant_id: uuid.UUID | None = None


class LawyerApplicationCreate(BaseModel):
    """Self-service lawyer application. `name` is taken from the user's profile."""
    bar_number: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    district: str = Field(min_length=2, max_length=100)
    specializations: list[str] = Field(default_factory=list)
    bio: str | None = Field(default=None, max_length=4000)


class LawyerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    name: str
    bar_number: str | None
    phone: str | None
    email: str | None
    district: str | None
    specializations: list[str]
    bio: str | None
    status: str
    verified: bool
    tenant_id: uuid.UUID | None
    created_at: datetime


class LawyerAdminResponse(LawyerResponse):
    verified_at: datetime | None
    verified_by: uuid.UUID | None
    rejection_reason: str | None


class LawyerRejectRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)
