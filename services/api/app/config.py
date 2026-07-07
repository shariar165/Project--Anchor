from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://anchor:anchor_dev_password@localhost/anchor_db"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        # Railway's PostgreSQL plugin provides postgres:// or postgresql://;
        # SQLAlchemy 2.x requires postgresql+asyncpg:// for the async driver.
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT Ed25519 key paths (local dev) or inline content (Railway/prod)
    jwt_private_key_path: str = ".keys/ed25519_private.pem"
    jwt_public_key_path: str = ".keys/ed25519_public.pem"
    jwt_private_key_content: str = ""
    jwt_public_key_content: str = ""

    # Password pepper — hex-encoded 32 bytes
    password_pepper: str = Field(default="0" * 64)

    # App
    secret_key: str = Field(default="0" * 64)
    environment: str = "development"
    cors_origins: str = "http://localhost:8080,http://localhost:3000"
    # Public base URL of the student web app — used to build clickable links in
    # notifications/emails (e.g. "{frontend_url}/?alert={event_id}"). Leave blank
    # to omit links where an absolute URL is required (the web push click handler
    # builds its own URL from the SW origin and does not need this).
    frontend_url: str = ""

    # Path to the unzipped skill source tree (skills/src), used by skill_loader to ground
    # AI prompts. Blank = repo default resolved relative to this service. Override with
    # SKILLS_DIR if the tree ships at a different path in prod.
    skills_dir: str = ""

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

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    notice_ai_model: str = "qwen3:1.7b"

    # Gemini (Google Generative Language API) — PRIMARY generator for the API's own
    # AI features (notice drafting, routine/timetable NL edits) when GEMINI_API_KEY is
    # set. Ollama stays as the fallback; both degrade to templated output if unreachable.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com"

    # RAG service (the /ai/chat proxy target). rag_internal_secret must match
    # RAG_INTERNAL_SECRET set on the services/rag side, or RAG returns 403.
    rag_service_url: str = "http://localhost:8001"
    rag_internal_secret: str = ""

    # Timetable solver
    # "process" runs each CP-SAT solve in a spawned subprocess so an OOM kill
    # hits the child, not the API (job fails as solver_oom instead of orphaning).
    # "thread" keeps the old in-process behavior (used by the test suite).
    solver_isolation: str = "process"
    solver_num_workers: int = 1        # CP-SAT search workers per solve
    solver_decompose_threshold: int = 2  # >N batches → per-batch decomposition
    # Real rosters mark 100+ teachers eligible per course; model size, peak
    # memory, and CP-SAT search plateaus all scale with that fan-out. Each
    # group solve keeps only the N least-reserved candidates per course
    # (teachers already used by base entries / pin targets are always kept);
    # a trimmed group that comes back infeasible/unknown retries with the full
    # pool, so this is a performance cap, never a correctness one. 0 disables.
    solver_max_candidates: int = 10

    # HIBP
    hibp_check_enabled: bool = True

    # FCM (Firebase Cloud Messaging)
    fcm_project_id: str = ""
    fcm_service_account_json_path: str = ""   # local dev: path to JSON file
    fcm_service_account_json: str = ""        # Railway/prod: full JSON content as string
    fcm_default_ttl_seconds: int = 300

    # Alert system — locked values per spec
    alert_hold_duration_seconds: int = 4
    alert_video_length_seconds: int = 10
    alert_daily_limit_per_user: int = 1
    alert_autoclose_hours: int = 24
    alert_zone_radius_m: int = 1000
    alert_zone_fallback_radius_m: int = 2000
    alert_nearby_batch_size: int = 50
    alert_nearby_pause_threshold: int = 3
    # Max age of a user's location snapshot to still target them in a fan-out. The web
    # client only posts location while foregrounded (watchPosition, throttled), so a
    # short window silently drops any phone that isn't actively open. 30 min keeps
    # recently-active devices eligible without targeting stale positions.
    alert_location_staleness_minutes: int = 30
    alert_false_ban_days: int = 30
    # Hex-encoded 32-byte keys — must be set in production
    alert_actor_hmac_key: str = Field(default="0" * 64)
    alert_encryption_key: str = Field(default="0" * 64)

    # ── Verification Feed ──────────────────────────────────────────
    feed_title_max_chars: int = 100
    feed_body_max_chars: int = 1000
    feed_tags_max_count: int = 5
    feed_max_attachments: int = 5
    feed_max_attachment_mb: int = 10
    ai_prescreen_timeout_seconds: int = 10
    trusted_source_bronze_weight: float = 1.2
    trusted_source_silver_weight: float = 1.5
    trusted_source_gold_weight: float = 2.0
    community_corroborate_indicator_min: int = 5
    challenge_review_ratio: float = 0.5
    flag_to_queue_threshold: int = 3
    confirmation_eligibility_min: int = 10
    trust_milestone_bronze: int = 5
    trust_milestone_silver: int = 10
    trust_milestone_gold: int = 15
    fake_news_strike_first_ban_days: int = 30
    fake_news_strike_second_ban_days: int = 60
    archive_incident_hours: int = 48
    archive_road_hours: int = 24
    archive_safety_hours: int = 72
    archive_civic_event_hours: int = 168
    archive_missing_person_hours: int = 720
    publish_rate_limit_per_user_per_hour: int = 3

    # ── Filing system ──────────────────────────────────────────────
    complaint_draft_min_body_chars: int = 10
    tracking_code_length: int = 12
    anonymous_moderation_max_hours: int = 72
    subject_response_window_days: int = 7
    filing_upload_dir: str = "data/filing_uploads"

    @model_validator(mode="after")
    def require_real_secrets_in_production(self) -> "Settings":
        if self.environment == "production":
            if self.password_pepper == "0" * 64:
                raise ValueError("PASSWORD_PEPPER must be set in production — default value is insecure")
            if self.secret_key == "0" * 64:
                raise ValueError("SECRET_KEY must be set in production — default value is insecure")
            if self.alert_actor_hmac_key == "0" * 64:
                raise ValueError("ALERT_ACTOR_HMAC_KEY must be set in production")
            if self.alert_encryption_key == "0" * 64:
                raise ValueError("ALERT_ENCRYPTION_KEY must be set in production")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def jwt_private_key(self) -> str:
        if self.jwt_private_key_content:
            return self.jwt_private_key_content.replace("\\n", "\n")
        with open(self.jwt_private_key_path, "r") as f:
            return f.read()

    @property
    def jwt_public_key(self) -> str:
        if self.jwt_public_key_content:
            return self.jwt_public_key_content.replace("\\n", "\n")
        with open(self.jwt_public_key_path, "r") as f:
            return f.read()

    @property
    def pepper_bytes(self) -> bytes:
        return bytes.fromhex(self.password_pepper)

    @property
    def alert_actor_hmac_key_bytes(self) -> bytes:
        return bytes.fromhex(self.alert_actor_hmac_key)

    @property
    def alert_encryption_key_bytes(self) -> bytes:
        return bytes.fromhex(self.alert_encryption_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
