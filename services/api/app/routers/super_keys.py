"""Super-admin encryption & key health (read-only).

Route: GET /v1/super-admin/keys/health
Auth: super_admin role only.

Reports metadata about the platform's cryptographic material — it NEVER returns
any secret/private key bytes. Surfaces known gaps honestly (e.g. SEC-12: TOTP
secrets are stored unencrypted) rather than reporting a false "OK".
"""
import hashlib
import logging
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.e2ee import UserE2EEKey
from app.redis import get_redis
from app.services.audit import verify_chain
from app.services import token as token_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/super-admin/keys", tags=["super-admin-keys"])

_DEFAULT_SECRET = "0" * 64


def _jwt_info() -> dict:
    """Public-key fingerprint, algorithm, source and (file-backed) age. No secrets."""
    settings = get_settings()
    info: dict = {
        "algorithm": token_svc.ALGORITHM,  # EdDSA
        "curve": "Ed25519",
        "rotation": "manual — not automated",
        "fingerprint": None,
        "source": None,
        "age_days": None,
    }
    try:
        pub = token_svc._public_key()
        pem = pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        info["fingerprint"] = "SHA256:" + hashlib.sha256(pem).hexdigest()[:32]
    except Exception as e:
        logger.warning("Could not load JWT public key for fingerprint: %s", e)

    if settings.jwt_public_key_content.strip():
        info["source"] = "env (inline content)"
    else:
        info["source"] = "file"
        try:
            mtime = os.path.getmtime(settings.jwt_public_key_path)
            age = datetime.now(tz=timezone.utc) - datetime.fromtimestamp(mtime, tz=timezone.utc)
            info["age_days"] = round(age.total_seconds() / 86400, 1)
        except OSError:
            pass
    return info


@router.get("/health")
@limiter.limit("30/minute")
async def keys_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    settings = get_settings()

    # Audit hash-chain integrity (reuses the same verifier as the audit explorer).
    try:
        chain = await verify_chain(db, limit=5000)
    except Exception as e:
        logger.warning("Audit chain verify failed: %s", e)
        chain = {"ok": None, "checked": 0, "first_tampered_id": None, "error": str(e)}

    # E2EE public keys held server-side (public only — private keys are user-held).
    e2ee_count = (await db.execute(
        select(func.count()).select_from(UserE2EEKey)
    )).scalar() or 0

    # JTI deny-list size (revoked tokens awaiting natural expiry).
    jti_count = None
    try:
        redis = get_redis()
        keys = await redis.keys("jti:*")
        jti_count = len(keys)
    except Exception as e:
        logger.warning("Could not count JTI deny-list: %s", e)

    fcm_configured = bool(
        settings.fcm_service_account_json_path.strip()
        or settings.fcm_service_account_json.strip()
    )

    return {
        "jwt": _jwt_info(),
        "password": {
            "algorithm": "Argon2id + HMAC-SHA256 pepper",
            "pepper_configured": settings.password_pepper != _DEFAULT_SECRET,
        },
        "totp": {
            # SEC-12: secret_encrypted column stores the base32 secret in PLAINTEXT.
            "encrypted_at_rest": False,
            "note": "SEC-12 — TOTP secrets are stored unencrypted; needs KMS/envelope encryption.",
        },
        "audit_chain": chain,
        "e2ee": {
            "stored_public_keys": int(e2ee_count),
            "private_keys_server_side": False,
        },
        "token_denylist": {
            "revoked_jti_count": jti_count,
            "backend": "redis",
        },
        "push": {
            "fcm_configured": fcm_configured,
            "fcm_project_id": settings.fcm_project_id or None,
        },
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }
