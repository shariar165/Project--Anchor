from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models.alert import Zone, ZoneStatus
from app.schemas.zones import ZoneResponse

router = APIRouter(prefix="/v1/zones", tags=["zones"])


@router.get("", response_model=list[ZoneResponse])
async def list_zones(
    lat_min: float | None = Query(default=None),
    lat_max: float | None = Query(default=None),
    lng_min: float | None = Query(default=None),
    lng_max: float | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    q = select(Zone).where(
        Zone.status == ZoneStatus.active,
        or_(Zone.expires_at.is_(None), Zone.expires_at > now),
    )
    if lat_min is not None:
        q = q.where(Zone.center_lat >= lat_min)
    if lat_max is not None:
        q = q.where(Zone.center_lat <= lat_max)
    if lng_min is not None:
        q = q.where(Zone.center_lng >= lng_min)
    if lng_max is not None:
        q = q.where(Zone.center_lng <= lng_max)
    q = q.order_by(Zone.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())
