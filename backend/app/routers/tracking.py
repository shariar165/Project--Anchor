from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.anonymous import AnonymousIdentityMapping
from app.schemas.tracking import TrackingLookupResponse

router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.get("/track/{code}", response_model=TrackingLookupResponse)
async def track_complaint(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AnonymousIdentityMapping).where(AnonymousIdentityMapping.anonymous_code == code)
    )
    record = result.scalars().first()
    if not record:
        return TrackingLookupResponse(code=code, status="not_found", status_message=None, found=False)

    return TrackingLookupResponse(
        code=code,
        status=record.status,
        status_message=record.status_message,
        found=True,
    )
