from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid


class PoliceReportCreate(BaseModel):
    report_type: str = Field(default="gd", pattern="^(gd|fir)$")
    language: str = Field(default="en", pattern="^(en|bn)$")


class PoliceReportUpdate(BaseModel):
    complainant_name: str | None = Field(default=None, max_length=200)
    guardian_name: str | None = Field(default=None, max_length=200)
    address: str | None = None
    nid: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=40)
    subject: str | None = Field(default=None, max_length=300)
    incident_type: str | None = Field(default=None, max_length=40)
    incident_datetime: str | None = Field(default=None, max_length=120)
    location: str | None = None
    thana: str | None = Field(default=None, max_length=200)
    district: str | None = Field(default=None, max_length=100)
    narrative: str | None = None
    accused_details: str | None = None
    witnesses: str | None = None
    property_details: str | None = None
    language: str | None = Field(default=None, pattern="^(en|bn)$")


class PoliceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    report_type: str
    state: str
    reference_no: str | None
    complainant_name: str | None
    guardian_name: str | None
    address: str | None
    nid: str | None
    phone: str | None
    subject: str | None
    incident_type: str | None
    incident_datetime: str | None
    location: str | None
    thana: str | None
    district: str | None
    narrative: str | None
    accused_details: str | None
    witnesses: str | None
    property_details: str | None
    language: str
    ai_assisted: bool
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None


class PoliceReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_type: str
    state: str
    reference_no: str | None
    subject: str | None
    thana: str | None
    created_at: datetime
    updated_at: datetime


class AiDraftRequest(BaseModel):
    report_type: str = Field(default="gd", pattern="^(gd|fir)$")
    situation: str = Field(min_length=10, max_length=4000)
    language: str = Field(default="en", pattern="^(en|bn)$")
    # Optional structured hints to ground the draft
    complainant_name: str | None = Field(default=None, max_length=200)
    thana: str | None = Field(default=None, max_length=200)
    incident_type: str | None = Field(default=None, max_length=40)
    incident_datetime: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=500)


class AiDraftResponse(BaseModel):
    subject: str
    narrative: str
    ai_assisted: bool
    notice: str | None = None
