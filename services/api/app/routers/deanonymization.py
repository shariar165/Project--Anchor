"""
De-anonymization workflow — request, dual-control approval, and time-limited
identity reveal.

Releasing the real identity behind an anonymous filing/alert is the most
sensitive action on the platform. It requires strict two-person control: two
*distinct* super admins must each approve. Every step is written to the
SHA-256 audit hash chain (see services/audit.py). The decrypted identity is
never persisted — it is decrypted on demand only while the request is approved
and inside the 4-hour reveal window.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import TokenData, get_current_user, require_role
from app.limiter import limiter
from app.models.user import User
from app.schemas.deanonymization import (
    DeanonDenyRequest,
    DeanonListResponse,
    DeanonRequestCreate,
    DeanonRequestOut,
    DeanonRevealResponse,
    DeanonStats,
)
from app.services import deanon_svc
from app.services.device import get_ip

router = APIRouter(prefix="/v1/admin/deanonymization", tags=["deanonymization"])

MAX_LIMIT = 200
VALID_STATUSES = {
    "pending_review", "awaiting_second_approval", "approved", "denied", "expired",
}


async def _load_request(db: AsyncSession, request_id: str) -> "deanon_svc.DeanonymizationRequest":
    try:
        rid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid request id")
    req = await deanon_svc.get_request(db, rid)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Request not found")
    return req


@router.post("", response_model=DeanonRequestOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_request(
    request: Request,
    body: DeanonRequestCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "super_admin")),
):
    """Open a de-anonymization request against an anonymous filing or alert."""
    requester = (await db.execute(select(User).where(User.id == token.user_id))).scalars().first()
    if requester is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not active")
    try:
        req = await deanon_svc.create_request(
            db,
            target_type=body.target_type,
            target_ref=body.target_ref,
            legal_basis=body.legal_basis,
            reason=body.reason,
            formal_letter_ref=body.formal_letter_ref,
            requester=requester,
            ip_address=get_ip(request),
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return await deanon_svc.serialize(db, req)


@router.get("", response_model=DeanonListResponse)
@limiter.limit("60/minute")
async def list_requests(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Queue of de-anonymization requests. Super-Admin only."""
    if status_filter and status_filter not in VALID_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {status_filter}")
    rows, total = await deanon_svc.list_requests(
        db, status=status_filter, limit=limit, offset=offset
    )
    items = [await deanon_svc.serialize(db, r) for r in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/stats", response_model=DeanonStats)
@limiter.limit("60/minute")
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Counts by status for dashboard badges. Super-Admin only."""
    return await deanon_svc.stats(db)


@router.get("/{request_id}", response_model=DeanonRequestOut)
@limiter.limit("60/minute")
async def get_one(
    request: Request,
    request_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Request detail. Super-Admin, or the original requester."""
    req = await _load_request(db, request_id)
    if token.role != "super_admin" and req.requester_user_id != token.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return await deanon_svc.serialize(db, req)


@router.post("/{request_id}/approve", response_model=DeanonRequestOut)
@limiter.limit("30/minute")
async def approve_request(
    request: Request,
    request_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Record an approval. Two distinct super admins are required to release."""
    req = await _load_request(db, request_id)
    try:
        req = await deanon_svc.approve(db, req, token.user_id, get_ip(request))
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return await deanon_svc.serialize(db, req)


@router.post("/{request_id}/deny", response_model=DeanonRequestOut)
@limiter.limit("30/minute")
async def deny_request(
    request: Request,
    request_id: str,
    body: DeanonDenyRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Deny the request with a recorded reason."""
    req = await _load_request(db, request_id)
    try:
        req = await deanon_svc.deny(db, req, token.user_id, body.reason, get_ip(request))
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return await deanon_svc.serialize(db, req)


@router.post("/{request_id}/reveal", response_model=DeanonRevealResponse)
@limiter.limit("30/minute")
async def reveal_identity(
    request: Request,
    request_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Decrypt and return the real identity, inside the reveal window.
    Super-Admin, or the original requester."""
    req = await _load_request(db, request_id)
    if token.role != "super_admin" and req.requester_user_id != token.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    try:
        return await deanon_svc.reveal(db, req, token.user_id, get_ip(request))
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
