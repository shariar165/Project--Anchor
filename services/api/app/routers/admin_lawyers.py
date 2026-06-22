import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.models.lawyer import Lawyer
from app.schemas.lawyers import LawyerAdminResponse, LawyerRejectRequest
from app.services import lawyer_svc, audit as audit_svc
from app.services.device import get_ip

router = APIRouter(prefix="/v1/admin/lawyers", tags=["admin-lawyers"])

PAGE_SIZE = 20
_STATUSES = {"pending", "verified", "rejected"}


async def _get_lawyer(db: AsyncSession, lawyer_id: uuid.UUID) -> Lawyer:
    result = await db.execute(select(Lawyer).where(Lawyer.id == lawyer_id))
    lawyer = result.scalars().first()
    if not lawyer or lawyer.user_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lawyer application not found")
    return lawyer


@router.get("")
async def list_lawyer_applications(
    lawyer_status: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, alias="q", max_length=120),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    if lawyer_status and lawyer_status not in _STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(sorted(_STATUSES))}",
        )
    items, total = await lawyer_svc.list_for_admin(
        db, status=lawyer_status, search=search, page=page
    )
    return {
        "items": [LawyerAdminResponse.model_validate(l) for l in items],
        "total": total,
        "page": page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


@router.post("/{lawyer_id}/verify", response_model=LawyerAdminResponse)
async def verify_lawyer(
    lawyer_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    lawyer = await _get_lawyer(db, lawyer_id)
    lawyer = await lawyer_svc.verify_lawyer(db, lawyer, token.user_id)
    await audit_svc.log_event(
        db, "lawyer_verified", lawyer.user_id, get_ip(request),
        {"by": str(token.user_id), "lawyer_id": str(lawyer.id)},
    )
    return LawyerAdminResponse.model_validate(lawyer)


@router.post("/{lawyer_id}/reject", response_model=LawyerAdminResponse)
async def reject_lawyer(
    lawyer_id: uuid.UUID,
    body: LawyerRejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    lawyer = await _get_lawyer(db, lawyer_id)
    lawyer = await lawyer_svc.reject_lawyer(db, lawyer, body.reason)
    await audit_svc.log_event(
        db, "lawyer_rejected", lawyer.user_id, get_ip(request),
        {"by": str(token.user_id), "lawyer_id": str(lawyer.id), "reason": body.reason},
    )
    return LawyerAdminResponse.model_validate(lawyer)
