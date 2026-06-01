from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://anchor:anchor_dev_password@localhost/anchor_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT Ed25519 key paths
    jwt_private_key_path: str = ".keys/ed25519_private.pem"
    jwt_public_key_path: str = ".keys/ed25519_public.pem"

    # Password pepper — hex-encoded 32 bytes
    password_pepper: str = Field(default="0" * 64)

    # App
    secret_key: str = Field(default="0" * 64)
    environment: str = "development"
    cors_origins: str = "http://localhost:8080,http://localhost:3000"

    # Token TTLs (seconds)
    access_token_ttl: int = 900          # 15 min
    refresh_token_ttl_user: int = 604800  # 7 days
    refresh_token_ttl_student: int = 2592000  # 30 days
    mfa_pending_ttl: int = 120           # 2 min
    stepup_token_ttl: int = 300          # 5 min

    # OTP
    otp_ttl: int = 300                   # 5 min
    otp_max_attempts: int = 5

    # Email (Brevo)
    brevo_api_key: str = ""
    brevo_sender_email: str = "noreply@anchor.example.com"
    brevo_sender_name: str = "Anchor AI"

    # Email fallback — Gmail SMTP (needs a Google App Password, not your regular password)
    gmail_user: str = ""
    gmail_app_password: str = ""

    # SMS
    sms_api_url: str = ""
    sms_api_key: str = ""
    sms_sender_id: str = "AnchorAI"

    # HIBP
    hibp_check_enabled: bool = True

    @model_validator(mode="after")
    def require_real_secrets_in_production(self) -> "Settings":
        if self.environment == "production":
            if self.password_pepper == "0" * 64:
                raise ValueError("PASSWORD_PEPPER must be set in production — default value is insecure")
            if self.secret_key == "0" * 64:
                raise ValueError("SECRET_KEY must be set in production — default value is insecure")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def jwt_private_key(self) -> str:
        with open(self.jwt_private_key_path, "r") as f:
            return f.read()

    @property
    def jwt_public_key(self) -> str:
        with open(self.jwt_public_key_path, "r") as f:
            return f.read()

    @property
    def pepper_bytes(self) -> bytes:
        return bytes.fromhex(self.password_pepper)


@lru_cache
def get_settings() -> Settings:
    return Settings()
