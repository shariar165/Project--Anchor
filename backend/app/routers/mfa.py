import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.limiter import limiter

from app.database import get_db
from app.redis import get_redis
from app.deps import get_current_user, require_stepup, TokenData
from app.models.user import User
from app.models.mfa import MFAMethod, MFARecoveryCode, MFAType
from app.schemas.auth import TokenResponse
from app.schemas.mfa import (
    TOTPEnrollResponse, MFAEnrollVerifyRequest, MFAEnrollVerifyResponse,
    MFAVerifyRequest, MFARecoveryRequest,
)
from app.services import mfa as mfa_svc, audit as audit_svc
from app.services.device import get_ip

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


async def _resolve_mfa_user(redis, mfa_token: str, db: AsyncSession) -> User:
    user_id_str = await redis.get(f"mfa_pending:{mfa_token}")
    if not user_id_str:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="MFA token invalid or expired")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/enroll/totp", response_model=TOTPEnrollResponse)
async def enroll_totp(db: AsyncSession = Depends(get_db), token: TokenData = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    secret = mfa_svc.generate_totp_secret()
    identifier = user.email or user.phone or str(user.id)
    uri = mfa_svc.make_otpauth_uri(secret, identifier)
    qr = mfa_svc.make_qr_data_url(uri)

    method = MFAMethod(
        user_id=user.id,
        type=MFAType.totp,
        secret_encrypted=secret,  # TODO: encrypt at rest with KMS key
        is_primary=True,
        verified=False,
    )
    db.add(method)
    await db.flush()

    return TOTPEnrollResponse(method_id=method.id, secret=secret, otpauth_uri=uri, qr_data_url=qr)


@router.post("/enroll/verify", response_model=MFAEnrollVerifyResponse)
async def enroll_verify(body: MFAEnrollVerifyRequest, db: AsyncSession = Depends(get_db), token: TokenData = Depends(get_current_user)):
    result = await db.execute(select(MFAMethod).where(
        MFAMethod.id == body.method_id, MFAMethod.user_id == token.user_id
    ))
    method = result.scalars().first()
    if not method:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MFA method not found")

    if not mfa_svc.verify_totp(method.secret_encrypted, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")

    method.verified = True

    codes = mfa_svc.generate_recovery_codes()
    for code in codes:
        db.add(MFARecoveryCode(method_id=method.id, code_hash=mfa_svc.hash_recovery_code(code)))

    result2 = await db.execute(select(User).where(User.id == token.user_id))
    user = result2.scalars().first()
    if user:
        user.mfa_enabled = True

    return MFAEnrollVerifyResponse(activated=True, recovery_codes=codes)


@router.post("/verify", response_model=TokenResponse)
@limiter.limit("10/minute")
async def mfa_verify(body: MFAVerifyRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    from app.routers.auth import _issue_token_pair
    user = await _resolve_mfa_user(redis, body.mfa_token, db)

    result = await db.execute(select(MFAMethod).where(
        MFAMethod.user_id == user.id, MFAMethod.verified == True
    ))
    method = result.scalars().first()
    if not method:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No verified MFA method")

    if not mfa_svc.verify_totp(method.secret_encrypted, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")

    await redis.delete(f"mfa_pending:{body.mfa_token}")
    tokens = await _issue_token_pair(db, redis, request, user)
    await audit_svc.log_event(db, "mfa_verified", user.id, get_ip(request))
    return tokens


@router.post("/recovery", response_model=TokenResponse)
@limiter.limit("5/minute")
async def mfa_recovery(body: MFARecoveryRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    from app.routers.auth import _issue_token_pair
    user = await _resolve_mfa_user(redis, body.mfa_token, db)

    result = await db.execute(select(MFAMethod).where(
        MFAMethod.user_id == user.id, MFAMethod.verified == True
    ))
    method = result.scalars().first()
    if not method:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No verified MFA method")

    result2 = await db.execute(select(MFARecoveryCode).where(
        MFARecoveryCode.method_id == method.id, MFARecoveryCode.used == False
    ))
    codes = result2.scalars().all()

    matched = None
    for rc in codes:
        if mfa_svc.verify_recovery_code(body.recovery_code, rc.code_hash):
            matched = rc
            break

    if not matched:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid recovery code")

    matched.used = True
    await redis.delete(f"mfa_pending:{body.mfa_token}")

    tokens = await _issue_token_pair(db, redis, request, user)
    await audit_svc.log_event(db, "mfa_recovery_used", user.id, get_ip(request))
    return tokens


@router.delete("/{method_id}")
async def remove_mfa(method_id: uuid.UUID, db: AsyncSession = Depends(get_db), token: TokenData = Depends(require_stepup)):
    result = await db.execute(select(MFAMethod).where(
        MFAMethod.id == method_id, MFAMethod.user_id == token.user_id
    ))
    method = result.scalars().first()
    if not method:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    await db.delete(method)

    result2 = await db.execute(select(User).where(User.id == token.user_id))
    user = result2.scalars().first()
    if user:
        remaining = await db.execute(select(MFAMethod).where(MFAMethod.user_id == user.id, MFAMethod.verified == True))
        if not remaining.scalars().first():
            user.mfa_enabled = False

    return {"message": "MFA method removed"}
