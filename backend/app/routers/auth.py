import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update
from app.limiter import limiter

from app.database import get_db
from app.redis import get_redis
from app.deps import get_current_user, TokenData
from app.config import get_settings
from app.models.user import User, Role, AccountStatus
from app.models.session import Session
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, MFAPendingResponse,
    RefreshRequest, LogoutRequest, ForgotPasswordRequest, ResetPasswordRequest,
    VerifyEmailRequest, VerifyPhoneRequest, ResendVerificationRequest,
    StepUpRequest, StepUpResponse, UserInfo,
)
from app.services import password as pwd_svc, token as tok_svc, otp as otp_svc
from app.services import email as email_svc, sms as sms_svc, audit as audit_svc
from app.services.device import fingerprint, get_ip
from app.services.tenant import resolve_by_email_domain

router = APIRouter(prefix="/auth", tags=["auth"])

# Pre-computed sentinel hash — used to keep login response time constant when
# the identifier doesn't match any account (prevents user-enumeration via timing).
_SENTINEL_HASH: str = ""


def _get_sentinel_hash() -> str:
    global _SENTINEL_HASH
    if not _SENTINEL_HASH:
        _SENTINEL_HASH = pwd_svc.hash_password("__anchor_sentinel_constant_time__")
    return _SENTINEL_HASH


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ensure_tz(dt: datetime) -> datetime:
    """Make a naive datetime timezone-aware (UTC).
    SQLite returns naive datetimes even for DateTime(timezone=True) columns;
    PostgreSQL returns timezone-aware. This makes comparisons work on both.
    """
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _issue_token_pair(db: AsyncSession, redis, request: Request, user: User) -> TokenResponse:
    settings = get_settings()
    tenant_id_str = str(user.tenant_id) if user.tenant_id else None

    access_token, access_jti, access_exp = tok_svc.create_access_token(str(user.id), user.role.value, tenant_id_str)
    refresh_token, refresh_jti, refresh_exp = tok_svc.create_refresh_token(str(user.id), user.role.value, tenant_id_str)

    refresh_hash = pwd_svc.hash_password(refresh_token)

    session = Session(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        jti=refresh_jti,
        device_fingerprint=fingerprint(request),
        user_agent=request.headers.get("user-agent"),
        ip_address=get_ip(request),
        expires_at=refresh_exp,
    )
    db.add(session)

    user.last_login_at = _now()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_ttl,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    settings = get_settings()

    # Check for duplicate — only include non-None identifiers to avoid matching NULL rows
    dup_conditions = []
    if body.email:
        dup_conditions.append(User.email == body.email)
    if body.phone:
        dup_conditions.append(User.phone == body.phone)
    if dup_conditions:
        existing = await db.execute(select(User).where(or_(*dup_conditions)))
        existing_user = existing.scalars().first()
        if existing_user:
            if existing_user.status == AccountStatus.pending_verification:
                # Resend OTP so they can complete verification without re-registering
                code = ""
                if existing_user.email:
                    code = await otp_svc.generate_and_store(redis, existing_user.email, "registration")
                    await email_svc.send_verification_email(existing_user.email, code)
                elif existing_user.phone:
                    code = await otp_svc.generate_and_store(redis, existing_user.phone, "registration")
                    await sms_svc.send_otp_sms(existing_user.phone, code)
                resp = {"message": "Account pending verification. A new code has been sent."}
                if settings.environment in ("development", "testing") and code:
                    resp["dev_otp"] = code
                return resp
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Account already exists")

    # HIBP check
    if await pwd_svc.check_pwned(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password found in breach database")

    # Resolve tenant for students
    tenant_id: uuid.UUID | None = None
    role = Role(body.role)
    if role == Role.student:
        if not body.email or not body.email.lower().endswith('.edu.bd'):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="University accounts require an institutional email address ending in .edu.bd"
            )
        tenant = await resolve_by_email_domain(db, body.email)
        if tenant:
            tenant_id = tenant.id
        if body.tenant_id:
            tenant_id = body.tenant_id

    user = User(
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        password_hash=pwd_svc.hash_password(body.password),
        role=role,
        tenant_id=tenant_id,
        status=AccountStatus.pending_verification,
    )
    db.add(user)
    await db.flush()

    # Send verification OTP
    code: str = ""
    if body.email:
        code = await otp_svc.generate_and_store(redis, body.email, "registration")
        await email_svc.send_verification_email(body.email, code)
    elif body.phone:
        code = await otp_svc.generate_and_store(redis, body.phone, "registration")
        await sms_svc.send_otp_sms(body.phone, code)

    await audit_svc.log_event(db, "user_registered", user.id, get_ip(request))
    resp: dict = {"message": "Account created. Check your email/phone for a verification code."}
    if settings.environment in ("development", "testing") and code:
        resp["dev_otp"] = code
    return resp


@router.post("/login")
@limiter.limit("10/minute")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    settings = get_settings()

    result = await db.execute(
        select(User).where(or_(User.email == body.identifier, User.phone == body.identifier))
    )
    user = result.scalars().first()

    if not user:
        pwd_svc.verify_password(body.password, _get_sentinel_hash())  # constant-time: prevent user-enumeration via timing
        await audit_svc.log_event(db, "login_failed", None, get_ip(request), {"identifier": body.identifier})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not pwd_svc.verify_password(body.password, user.password_hash):
        await audit_svc.log_event(db, "login_failed", user.id, get_ip(request), {"identifier": body.identifier})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.status == AccountStatus.suspended:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account suspended")

    if user.status == AccountStatus.pending_verification:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Email/phone not verified")

    # Rehash if needed
    if pwd_svc.needs_rehash(user.password_hash):
        user.password_hash = pwd_svc.hash_password(body.password)

    # MFA check
    if user.mfa_enabled:
        mfa_token = str(uuid.uuid4())
        await redis.set(f"mfa_pending:{mfa_token}", str(user.id), ex=settings.mfa_pending_ttl)
        return MFAPendingResponse(mfa_token=mfa_token, methods=["totp"])

    tokens = await _issue_token_pair(db, redis, request, user)
    await audit_svc.log_event(db, "login_success", user.id, get_ip(request))
    return tokens


@router.post("/refresh")
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    settings = get_settings()

    try:
        payload = tok_svc.decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    jti = payload["jti"]

    if await tok_svc.is_blacklisted(redis, jti):
        # Theft detected: revoke all sessions for this user.
        # Commit BEFORE raising so the revocations persist despite the
        # subsequent rollback that get_db triggers on HTTPException.
        user_id = uuid.UUID(payload["sub"])
        await db.execute(
            Session.__table__.update()
            .where(Session.user_id == user_id, Session.revoked == False)
            .values(revoked=True, revoked_at=_now())
        )
        await db.commit()
        await audit_svc.log_event(db, "token_reuse_detected", user_id, get_ip(request))
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token reuse detected — all sessions revoked")

    result = await db.execute(select(Session).where(Session.jti == jti, Session.revoked == False))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session not found or revoked")

    if not pwd_svc.verify_password(body.refresh_token, session.refresh_token_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if _ensure_tz(session.expires_at) < _now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalars().first()
    if not user or user.status != AccountStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not active")

    # Blacklist old jti
    remaining = int((_ensure_tz(session.expires_at) - _now()).total_seconds())
    await tok_svc.blacklist_jti(redis, jti, remaining)

    # Revoke old session
    session.revoked = True
    session.revoked_at = _now()

    tokens = await _issue_token_pair(db, redis, request, user)
    await audit_svc.log_event(db, "token_refreshed", user.id, get_ip(request))
    return tokens


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis), token: TokenData = Depends(get_current_user)):
    if body.refresh_token:
        try:
            payload = tok_svc.decode_token(body.refresh_token)
            jti = payload.get("jti")
            result = await db.execute(select(Session).where(Session.jti == jti))
            session = result.scalars().first()
            if session and not session.revoked and session.user_id == token.user_id:
                session.revoked = True
                session.revoked_at = _now()
                remaining = max(int((_ensure_tz(session.expires_at) - _now()).total_seconds()), 1)
                await tok_svc.blacklist_jti(redis, jti, remaining)
        except Exception:
            pass

    # Always blacklist the access token
    if token.expires_at:
        remaining = max(int((_ensure_tz(token.expires_at) - _now()).total_seconds()), 1)
        await tok_svc.blacklist_jti(redis, token.jti, remaining)

    return {"message": "Logged out"}


@router.post("/logout-all")
async def logout_all(db: AsyncSession = Depends(get_db), redis=Depends(get_redis), token: TokenData = Depends(get_current_user)):
    result = await db.execute(
        select(Session).where(Session.user_id == token.user_id, Session.revoked == False)
    )
    sessions = result.scalars().all()
    now = _now()
    for s in sessions:
        s.revoked = True
        s.revoked_at = now
        remaining = max(int((_ensure_tz(s.expires_at) - now).total_seconds()), 1)
        await tok_svc.blacklist_jti(redis, s.jti, remaining)

    if token.expires_at:
        remaining = max(int((_ensure_tz(token.expires_at) - now).total_seconds()), 1)
        await tok_svc.blacklist_jti(redis, token.jti, remaining)

    return {"message": f"Revoked {len(sessions)} sessions"}


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    result = await db.execute(
        select(User).where(or_(User.email == body.identifier, User.phone == body.identifier))
    )
    user = result.scalars().first()

    # Always return 200 to prevent enumeration
    if user:
        if user.email and body.identifier == user.email:
            code = await otp_svc.generate_and_store(redis, user.email, "password_reset")
            await email_svc.send_password_reset_email(user.email, code)
        elif user.phone:
            code = await otp_svc.generate_and_store(redis, user.phone, "password_reset")
            await sms_svc.send_otp_sms(user.phone, code)

    return {"message": "If an account exists, a reset code has been sent"}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(body: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)) -> dict:
    # token = "identifier:otp_code" encoded in body.token
    try:
        identifier, code = body.token.split(":", 1)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid reset token format")

    ok = await otp_svc.verify(redis, identifier, "password_reset", code)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset code")

    result = await db.execute(
        select(User).where(or_(User.email == identifier, User.phone == identifier))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="User not found")

    if await pwd_svc.check_pwned(body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password found in breach database")

    user.password_hash = pwd_svc.hash_password(body.new_password)
    user.password_changed_at = _now()

    # Revoke all active sessions so compromised tokens can't keep working
    sessions_result = await db.execute(
        select(Session).where(Session.user_id == user.id, Session.revoked == False)
    )
    now = _now()
    for s in sessions_result.scalars().all():
        s.revoked = True
        s.revoked_at = now
        remaining = max(int((_ensure_tz(s.expires_at) - now).total_seconds()), 1)
        await tok_svc.blacklist_jti(redis, s.jti, remaining)

    return {"message": "Password updated"}


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    try:
        email, code = body.token.split(":", 1)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid token format")

    ok = await otp_svc.verify(redis, email, "registration", code)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.status not in (AccountStatus.pending_verification, AccountStatus.active):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is not eligible for activation")
    user.email_verified = True
    user.status = AccountStatus.active
    tokens = await _issue_token_pair(db, redis, request, user)
    await audit_svc.log_event(db, "email_verified", user.id, get_ip(request))
    return tokens


@router.post("/verify-phone")
async def verify_phone(body: VerifyPhoneRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    ok = await otp_svc.verify(redis, body.phone, "registration", body.code)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.status not in (AccountStatus.pending_verification, AccountStatus.active):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is not eligible for activation")
    user.phone_verified = True
    user.status = AccountStatus.active
    tokens = await _issue_token_pair(db, redis, request, user)
    await audit_svc.log_event(db, "phone_verified", user.id, get_ip(request))
    return tokens


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    result = await db.execute(
        select(User).where(or_(User.email == body.identifier, User.phone == body.identifier))
    )
    user = result.scalars().first()
    if user and user.status == AccountStatus.pending_verification:
        if user.email and body.identifier == user.email:
            code = await otp_svc.generate_and_store(redis, user.email, "registration")
            await email_svc.send_verification_email(user.email, code)
        elif user.phone:
            code = await otp_svc.generate_and_store(redis, user.phone, "registration")
            await sms_svc.send_otp_sms(user.phone, code)

    return {"message": "If pending verification, a new code has been sent"}


@router.post("/stepup")
async def stepup(body: StepUpRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis), token: TokenData = Depends(get_current_user)):
    settings = get_settings()
    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalars().first()

    if not user or not pwd_svc.verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    tenant_id_str = str(user.tenant_id) if user.tenant_id else None
    stepup_token, _, _ = tok_svc.create_token_with_type(
        str(user.id), user.role.value, "stepup", settings.stepup_token_ttl, tenant_id_str
    )
    return StepUpResponse(stepup_token=stepup_token, expires_in=settings.stepup_token_ttl)


@router.get("/me", response_model=UserInfo)
async def me(db: AsyncSession = Depends(get_db), token: TokenData = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return user
