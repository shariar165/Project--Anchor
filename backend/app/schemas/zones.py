from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid


class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zone_type: str
    center_lat: float
    center_lng: float
    radius_m: int
    description_public: str | None
    status: str
    expires_at: datetime | None
    label: str | None
    tenant_id: uuid.UUID | None
    created_at: datetime
