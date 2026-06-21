"""
De-anonymization workflow business logic.

A university/super admin requests release of the real identity behind an
anonymous filing or alert. Releasing the identity requires strict two-person
control: two *distinct* super admins must each approve. The decrypted identity
is never persisted — it is decrypted on demand from the target's
``encrypted_actor_link`` only while the request is ``approved`` and inside the
time-limited reveal window (``access_expires_at``).

Domain errors raise ``ValueError`` (routers convert to HTTPException), matching
the repo-wide service convention.
"""
import base64
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertEvent
from app.models.deanonymization import DeanonymizationRequest
from app.models.filing import Filing
from app.models.user import User
from app.services import alert_svc
from app.services.audit import log_event, mask_email

# Reveal window after final (second) approval.
ACCESS_WINDOW = timedelta(hours=4)

OPEN_STATUSES = ("pending_review", "awaiting_second_approval")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns tz-naive datetimes; normalize to UTC for comparison."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ── Identity decryption ───────────────────────────────────────────────────────

def decrypt_filing_actor(encrypted: bytes) -> str:
    """Inverse of filing_svc._encrypt_actor — recover the complainant user_id."""
    from cryptography.fernet import Fernet
    from app.config import get_settings
    settings = get_settings()
    raw = bytes.fromhex(settings.secret_key)[:32]
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key).decrypt(encrypted).decode()


def _decrypt_actor(target_type: str, encrypted: bytes) -> str:
    if target_type == "filing":
        return decrypt_filing_actor(encrypted)
    # alert: AES-256-GCM, same scheme as alert_svc.encrypt_payload
    return alert_svc.decrypt_payload(encrypted).decode()


# ── Request number ────────────────────────────────────────────────────────────

async def _next_request_number(db: AsyncSession) -> str:
    year = _now().year
    pattern = f"DAR-{year}-%"
    result = await db.execute(
        select(func.count(DeanonymizationRequest.id)).where(
            DeanonymizationRequest.request_number.like(pattern)
        )
    )
    count = result.scalar() or 0
    return f"DAR-{year}-{count + 1:04d}"


# ── Target resolution ─────────────────────────────────────────────────────────

async def resolve_target(
    db: AsyncSession, target_type: str, target_ref: str
) -> tuple[uuid.UUID, bytes, uuid.UUID | None]:
    """Resolve a target ref to (target_id, encrypted_actor_link, tenant_id).

    Raises ValueError if the target does not exist or has no recoverable
    anonymous identity link.
    """
    if target_type == "filing":
        result = await db.execute(
            select(Filing).where(Filing.filing_number == target_ref)
        )
        filing = result.scalars().first()
        if filing is None:
            # Fall back to the anonymous tracking code.
            result = await db.execute(
                select(Filing).where(Filing.anonymous_tracking_code == target_ref)
            )
            filing = result.scalars().first()
        if filing is None:
            raise ValueError("filing not found")
        if not filing.encrypted_actor_link:
            raise ValueError("filing has no anonymous identity to release")
        return filing.id, filing.encrypted_actor_link, filing.tenant_id

    if target_type == "alert":
        event = None
        try:
            ev_uuid = uuid.UUID(target_ref)
            result = await db.execute(
                select(AlertEvent).where(AlertEvent.event_id == ev_uuid)
            )
            event = result.scalars().first()
        except ValueError:
            event = None
        if event is None:
            raise ValueError("alert event not found")
        if not event.encrypted_actor_link:
            raise ValueError("alert has no anonymous identity to release")
        return event.id, event.encrypted_actor_link, event.tenant_id

    raise ValueError(f"unsupported target_type: {target_type}")


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create_request(
    db: AsyncSession,
    *,
    target_type: str,
    target_ref: str,
    legal_basis: str,
    reason: str,
    formal_letter_ref: str | None,
    requester: User,
    ip_address: str | None = None,
) -> DeanonymizationRequest:
    target_id, _encrypted, tenant_id = await resolve_target(db, target_type, target_ref)

    role_label = requester.role.value if hasattr(requester.role, "value") else str(requester.role)
    label = f"{requester.full_name} ({role_label})"

    req = DeanonymizationRequest(
        request_number=await _next_request_number(db),
        target_type=target_type,
        target_id=target_id,
        target_ref=target_ref,
        tenant_id=tenant_id or requester.tenant_id,
        requester_user_id=requester.id,
        requester_label=label,
        legal_basis=legal_basis,
        reason=reason,
        formal_letter_ref=formal_letter_ref,
        status="pending_review",
    )
    db.add(req)
    await db.flush()

    await log_event(
        db, "DEANON_REQUEST_CREATED", user_id=requester.id, ip_address=ip_address,
        metadata={
            "request_number": req.request_number,
            "target_type": target_type,
            "target_ref": target_ref,
            "legal_basis": legal_basis,
        },
    )
    await db.commit()
    await db.refresh(req)
    return req


async def get_request(db: AsyncSession, request_id: uuid.UUID) -> DeanonymizationRequest | None:
    result = await db.execute(
        select(DeanonymizationRequest).where(DeanonymizationRequest.id == request_id)
    )
    return result.scalars().first()


async def list_requests(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DeanonymizationRequest], int]:
    base = select(DeanonymizationRequest)
    if status:
        base = base.where(DeanonymizationRequest.status == status)

    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    page_q = (
        base.order_by(DeanonymizationRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await db.execute(page_q)).scalars().all())
    return rows, total


async def stats(db: AsyncSession) -> dict:
    result = await db.execute(
        select(DeanonymizationRequest.status, func.count(DeanonymizationRequest.id))
        .group_by(DeanonymizationRequest.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    out = {
        "pending_review": counts.get("pending_review", 0),
        "awaiting_second_approval": counts.get("awaiting_second_approval", 0),
        "approved": counts.get("approved", 0),
        "denied": counts.get("denied", 0),
        "expired": counts.get("expired", 0),
    }
    out["open_total"] = out["pending_review"] + out["awaiting_second_approval"]
    return out


# ── Decisions ─────────────────────────────────────────────────────────────────

async def approve(
    db: AsyncSession,
    req: DeanonymizationRequest,
    approver_id: uuid.UUID,
    ip_address: str | None = None,
) -> DeanonymizationRequest:
    if req.status not in OPEN_STATUSES:
        raise ValueError(f"request is not open for approval (status: {req.status})")

    now = _now()
    if req.first_approver_user_id is None:
        # First approval.
        req.first_approver_user_id = approver_id
        req.first_approved_at = now
        req.status = "awaiting_second_approval"
        await log_event(
            db, "DEANON_FIRST_APPROVAL", user_id=approver_id, ip_address=ip_address,
            metadata={"request_number": req.request_number},
        )
    else:
        # Second approval — must be a different super admin.
        if req.first_approver_user_id == approver_id:
            raise ValueError("second approver must be a different super admin")
        req.second_approver_user_id = approver_id
        req.second_approved_at = now
        req.status = "approved"
        req.decided_at = now
        req.access_expires_at = now + ACCESS_WINDOW
        await log_event(
            db, "DEANON_APPROVED_RELEASED", user_id=approver_id, ip_address=ip_address,
            metadata={
                "request_number": req.request_number,
                "first_approver": str(req.first_approver_user_id),
            },
        )
    await db.commit()
    await db.refresh(req)
    return req


async def deny(
    db: AsyncSession,
    req: DeanonymizationRequest,
    approver_id: uuid.UUID,
    reason: str,
    ip_address: str | None = None,
) -> DeanonymizationRequest:
    if req.status not in OPEN_STATUSES:
        raise ValueError(f"request is not open for a decision (status: {req.status})")
    now = _now()
    req.status = "denied"
    req.denied_by_user_id = approver_id
    req.denied_reason = reason
    req.decided_at = now
    await log_event(
        db, "DEANON_DENIED", user_id=approver_id, ip_address=ip_address,
        metadata={"request_number": req.request_number, "reason": reason},
    )
    await db.commit()
    await db.refresh(req)
    return req


async def reveal(
    db: AsyncSession,
    req: DeanonymizationRequest,
    viewer_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    """Decrypt and return the real identity. Only valid while approved and
    inside the access window. Lapsed windows flip the request to ``expired``."""
    if req.status != "approved":
        raise ValueError(f"identity is not released (status: {req.status})")

    expires = _aware(req.access_expires_at)
    if expires is None or _now() >= expires:
        req.status = "expired"
        await db.commit()
        raise ValueError("reveal window has expired")

    _tid, encrypted, _tenant = await resolve_target(db, req.target_type, req.target_ref)
    user_id_str = _decrypt_actor(req.target_type, encrypted)

    user = None
    try:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
        user = result.scalars().first()
    except ValueError:
        user = None

    await log_event(
        db, "DEANON_IDENTITY_REVEALED", user_id=viewer_id, ip_address=ip_address,
        metadata={
            "request_number": req.request_number,
            "revealed_user_id": user_id_str,
        },
    )
    await db.commit()

    return {
        "request_id": str(req.id),
        "request_number": req.request_number,
        "user_id": user_id_str,
        "full_name": user.full_name if user else None,
        "email": user.email if user else None,
        "masked_email": mask_email(user.email if user else None),
        "role": (user.role.value if user else None),
        "tenant_id": (str(user.tenant_id) if user and user.tenant_id else None),
        "access_expires_at": req.access_expires_at,
    }


# ── Serialization ─────────────────────────────────────────────────────────────

async def serialize(db: AsyncSession, req: DeanonymizationRequest) -> dict:
    """Build the API representation, masking approver emails (never the actor)."""
    approver_ids = [
        uid for uid in (req.first_approver_user_id, req.second_approver_user_id) if uid
    ]
    emails: dict[uuid.UUID, str | None] = {}
    if approver_ids:
        rows = (await db.execute(select(User).where(User.id.in_(approver_ids)))).scalars().all()
        emails = {u.id: u.email for u in rows}

    def _approver(uid, at):
        if not uid:
            return None
        return {
            "user_id": str(uid),
            "masked_email": mask_email(emails.get(uid)),
            "at": at,
        }

    return {
        "id": str(req.id),
        "request_number": req.request_number,
        "target_type": req.target_type,
        "target_ref": req.target_ref,
        "tenant_id": str(req.tenant_id) if req.tenant_id else None,
        "requester_label": req.requester_label,
        "requester_user_id": str(req.requester_user_id) if req.requester_user_id else None,
        "legal_basis": req.legal_basis,
        "reason": req.reason,
        "formal_letter_ref": req.formal_letter_ref,
        "status": req.status,
        "first_approval": _approver(req.first_approver_user_id, req.first_approved_at),
        "second_approval": _approver(req.second_approver_user_id, req.second_approved_at),
        "denied_reason": req.denied_reason,
        "decided_at": req.decided_at,
        "access_expires_at": req.access_expires_at,
        "created_at": req.created_at,
    }
