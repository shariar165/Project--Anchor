from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.lawyers import LawyerResponse
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
