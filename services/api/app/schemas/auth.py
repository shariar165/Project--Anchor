from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from typing import Literal
import uuid


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^01[3-9]\d{8}$")
    password: str = Field(min_length=8, max_length=128)
    role: Literal["user", "student"] = "user"
    tenant_id: uuid.UUID | None = None
    terms: bool
    data_consent: bool

    @model_validator(mode="after")
    def require_email_or_phone(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        if not self.terms:
            raise ValueError("Must accept terms")
        if not self.data_consent:
            raise ValueError("Must consent to data processing")
        return self


class LoginRequest(BaseModel):
    identifier: str = Field(description="Email or phone")
    password: str
    device_fingerprint: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class MFAPendingResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str
    methods: list[str]


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    identifier: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyPhoneRequest(BaseModel):
    phone: str
    code: str = Field(min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    identifier: str


class StepUpRequest(BaseModel):
    password: str


class StepUpResponse(BaseModel):
    stepup_token: str
    expires_in: int


class SessionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_fingerprint: str | None
    user_agent: str | None
    ip_address: str | None
    created_at: str
    expires_at: str
    current: bool = False


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    role: str
    tenant_id: uuid.UUID | None
    mfa_enabled: bool
    email_verified: bool
    phone_verified: bool
    total_filings: int = 0
    resolved_filings: int = 0
    department: str | None = None


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, pattern=r"^01[3-9]\d{8}$")
    department: str | None = Field(default=None, max_length=200)
