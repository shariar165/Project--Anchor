import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class EmergencyContact(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^\+?[0-9]{7,15}$")
    relationship: str = Field(min_length=1, max_length=50)


class Phase1SaveRequest(BaseModel):
    threat_description: str | None = Field(default=None, max_length=2000)
    emergency_contacts: list[EmergencyContact] = Field(default_factory=list, max_length=5)


class Phase1SaveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    updated_at: datetime


class AlertTriggerRequest(BaseModel):
    lat: float | None = None
    lng: float | None = None
    gps_accuracy_m: int | None = None
    gps_status: Literal["ok", "stale", "unavailable"] = "unavailable"


class AlertTriggerResponse(BaseModel):
    event_id: uuid.UUID
    state: str
    claim_token: str | None = None
    message: str


class AlertStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: uuid.UUID
    state: str
    created_at: datetime
    closed_at: datetime | None = None
    responder_count: int = 0
    lat: float | None = None
    lng: float | None = None


class RespondRequest(BaseModel):
    response_type: Literal["responding", "cannot_help", "flagged_fake"]
    distance_m: int | None = None


class EvidenceUploadRequest(BaseModel):
    encrypted_blob_ref: str = Field(min_length=1, max_length=500)
    sha256_hash: str = Field(min_length=64, max_length=64)
    capture_timestamp: datetime
    media_type: Literal["photo", "video", "audio", "document"]


class EvidenceUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sha256_hash: str
    uploaded_at: datetime


class NearbyAlertItem(BaseModel):
    event_id: uuid.UUID
    lat: float | None
    lng: float | None
    distance_m: int | None
    state: str
    created_at: datetime


class ResponderItem(BaseModel):
    # Distance only — responder coordinates are never exposed (privacy).
    model_config = ConfigDict(from_attributes=True)
    distance_m: int | None = None
    response_type: str
    created_at: datetime


class AlertRespondersResponse(BaseModel):
    event_id: uuid.UUID
    zone_radius_m: int | None = None   # actual Zone.radius_m, or null if no zone
    responder_count: int = 0           # count of response_type == "responding"
    responders: list[ResponderItem] = []


class PanicTriggerRequest(BaseModel):
    device_fingerprint: str = Field(min_length=1, max_length=200)
    lat: float | None = None
    lng: float | None = None
    gps_accuracy_m: int | None = None
    gps_status: Literal["ok", "stale", "unavailable"] = "unavailable"


class PanicClaimRequest(BaseModel):
    claim_token: str = Field(min_length=12, max_length=12)


class FCMTokenRegisterRequest(BaseModel):
    fcm_token: str = Field(min_length=1, max_length=500)
    device_id: str = Field(min_length=1, max_length=200)
    platform: Literal["android", "ios", "web"]


class LocationUpdateRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    geofence_consent: bool
