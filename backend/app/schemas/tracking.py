from pydantic import BaseModel


class TrackingLookupResponse(BaseModel):
    code: str
    status: str
    status_message: str | None
    found: bool
