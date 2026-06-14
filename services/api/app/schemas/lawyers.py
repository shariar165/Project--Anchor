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


class LawyerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    bar_number: str | None
    phone: str | None
    email: str | None
    district: str | None
    specializations: list[str]
    bio: str | None
    verified: bool
    tenant_id: uuid.UUID | None
    created_at: datetime
