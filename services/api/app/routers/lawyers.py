from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.models.user import User
from app.schemas.lawyers import LawyerResponse, LawyerApplicationCreate
from app.services import lawyer_svc

router = APIRouter(prefix="/v1/lawyers", tags=["lawyers"])


@router.get("", response_model=list[LawyerResponse])
async def list_lawyers(
    district: str | None = Query(default=None),
    specialization: str | None = Query(default=None),
    verified_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    return await lawyer_svc.list_lawyers(
        db,
        district=district,
        specialization=specialization,
        verified_only=verified_only,
        page=page,
    )


@router.post("/apply", response_model=LawyerResponse, status_code=status.HTTP_201_CREATED)
async def apply_as_lawyer(
    body: LawyerApplicationCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        return await lawyer_svc.apply_as_lawyer(db, user, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/me", response_model=LawyerResponse)
async def get_my_lawyer_profile(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    lawyer = await lawyer_svc.get_lawyer_by_user(db, token.user_id)
    if not lawyer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No lawyer profile")
    return lawyer
