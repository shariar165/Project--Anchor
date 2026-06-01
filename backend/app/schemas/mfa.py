from pydantic import BaseModel
import uuid


class TOTPEnrollResponse(BaseModel):
    method_id: uuid.UUID
    secret: str
    otpauth_uri: str
    qr_data_url: str


class MFAEnrollVerifyRequest(BaseModel):
    method_id: uuid.UUID
    code: str


class MFAEnrollVerifyResponse(BaseModel):
    activated: bool
    recovery_codes: list[str]


class MFAVerifyRequest(BaseModel):
    mfa_token: str
    code: str


class MFARecoveryRequest(BaseModel):
    mfa_token: str
    recovery_code: str
