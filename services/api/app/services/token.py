import uuid
from datetime import datetime, timezone, timedelta
import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from app.config import get_settings

ALGORITHM = "EdDSA"

SCOPE_MAP: dict[str, list[str]] = {
    "user":    ["national.read", "national.write"],
    "student": ["national.read", "national.write", "campus.read", "campus.write"],
}

_private_key_cache = None
_public_key_cache = None


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _normalize_pem(content: str) -> bytes:
    # Railway/Heroku-style env vars often store the PEM with escaped "\n"
    # instead of real newlines. Restore them so the parser accepts the key.
    return content.replace("\\n", "\n").strip().encode()


def _private_key():
    global _private_key_cache
    if _private_key_cache is None:
        settings = get_settings()
        if settings.jwt_private_key_content.strip():
            _private_key_cache = load_pem_private_key(
                _normalize_pem(settings.jwt_private_key_content), password=None
            )
        else:
            with open(settings.jwt_private_key_path, "rb") as f:
                _private_key_cache = load_pem_private_key(f.read(), password=None)
    return _private_key_cache


def _public_key():
    global _public_key_cache
    if _public_key_cache is None:
        settings = get_settings()
        if settings.jwt_public_key_content.strip():
            _public_key_cache = load_pem_public_key(
                _normalize_pem(settings.jwt_public_key_content)
            )
        else:
            with open(settings.jwt_public_key_path, "rb") as f:
                _public_key_cache = load_pem_public_key(f.read())
    return _public_key_cache


def create_access_token(user_id: str, role: str, tenant_id: str | None = None) -> tuple[str, str, datetime]:
    settings = get_settings()
    jti = str(uuid.uuid4())
    exp = _now() + timedelta(seconds=settings.access_token_ttl)
    payload: dict = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "exp": exp,
        "iat": _now(),
        "type": "access",
    }
    payload["scope"] = SCOPE_MAP.get(role, ["national.read", "national.write"])
    if tenant_id:
        payload["tenant_id"] = str(tenant_id)
    token = jwt.encode(payload, _private_key(), algorithm=ALGORITHM)
    return token, jti, exp


def create_refresh_token(user_id: str, role: str, tenant_id: str | None = None) -> tuple[str, str, datetime]:
    settings = get_settings()
    jti = str(uuid.uuid4())
    ttl = settings.refresh_token_ttl_student if role == "student" else settings.refresh_token_ttl_user
    exp = _now() + timedelta(seconds=ttl)
    payload: dict = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "exp": exp,
        "iat": _now(),
        "type": "refresh",
    }
    if tenant_id:
        payload["tenant_id"] = str(tenant_id)
    token = jwt.encode(payload, _private_key(), algorithm=ALGORITHM)
    return token, jti, exp


def create_token_with_type(user_id: str, role: str, token_type: str, ttl_seconds: int, tenant_id: str | None = None) -> tuple[str, str, datetime]:
    jti = str(uuid.uuid4())
    exp = _now() + timedelta(seconds=ttl_seconds)
    payload: dict = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "exp": exp,
        "iat": _now(),
        "type": token_type,
    }
    if tenant_id:
        payload["tenant_id"] = str(tenant_id)
    token = jwt.encode(payload, _private_key(), algorithm=ALGORITHM)
    return token, jti, exp


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _public_key(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ValueError(str(exc)) from exc


async def blacklist_jti(redis, jti: str, remaining_seconds: int):
    await redis.set(f"jti:{jti}", "1", ex=max(remaining_seconds, 1))


async def is_blacklisted(redis, jti: str) -> bool:
    return bool(await redis.exists(f"jti:{jti}"))
