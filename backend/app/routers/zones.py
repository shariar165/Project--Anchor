"""Public zone read endpoints — no auth required.

Students call:
  GET /v1/zones/nearby?lat=&lng=&radius_km=10   — GPS-based
  GET /v1/zones?zone_type=                      — all active zones
  GET /v1/zones/{zone_id}                       — single zone detail
"""
import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models.alert import Zone, ZoneStatus
from app.schemas.zones import ZoneResponse, zone_color

router = APIRouter(prefix="/v1/zones", tags=["zones"])

# Types visible on the student map (excludes legacy alert-generated types)
_VISIBLE_TYPES = {"campus", "purple", "black", "red", "university", "rape", "murder", "alert"}

_MANUAL_TYPES = {"campus", "purple", "black", "red"}


def _zone_out(zone: Zone) -> dict:
    zt = zone.zone_type.value if hasattr(zone.zone_type, "value") else str(zone.zone_type)
    name = zone.name or zone.label or zt.capitalize()
    return {
        "id": str(zone.id),
        "name": name,
        "zone_type": zt,
        "shape_type": zone.shape_type or "circle",
        "polygon_coords": zone.polygon_coords,
        "center_lat": zone.center_lat,
        "center_lng": zone.center_lng,
        "radius_m": zone.radius_m,
        "description_public": zone.description_public,
        "color": zone_color(zt),
        "status": zone.status.value if hasattr(zone.status, "value") else str(zone.status),
        "expires_at": zone.expires_at.isoformat() if zone.expires_at else None,
        "label": zone.label,
        "created_at": zone.created_at.isoformat(),
    }


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _active_q(db_q, now: datetime):
    return db_q.where(
        Zone.status == ZoneStatus.active,
        or_(Zone.expires_at.is_(None), Zone.expires_at > now),
    )


# ── GET /v1/zones/nearby  (MUST be before /{zone_id} to avoid route shadowing)

@router.get("/nearby")
async def zones_nearby(
    lat: float = Query(..., ge=-90, le=90, description="Device latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Device longitude"),
    radius_km: float = Query(default=10, ge=0.5, le=100, description="Search radius in km"),
    zone_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return active zones whose center is within radius_km of the given GPS point.
    Uses a lat/lng bounding-box pre-filter then exact Haversine in Python.
    """
    now = datetime.now(timezone.utc)

    # Bounding box pre-filter (faster)
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / max(0.001, 111.0 * math.cos(math.radians(lat)))

    q = _active_q(select(Zone), now).where(
        Zone.center_lat.between(lat - lat_delta, lat + lat_delta),
        Zone.center_lng.between(lng - lng_delta, lng + lng_delta),
    )

    if zone_type:
        try:
            from app.models.alert import ZoneType
            q = q.where(Zone.zone_type == ZoneType(zone_type))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid zone_type: {zone_type}")

    result = await db.execute(q)
    all_zones = result.scalars().all()

    # Exact Haversine filter
    nearby = [
        z for z in all_zones
        if _haversine_km(lat, lng, z.center_lat, z.center_lng) <= radius_km
    ]
    return [_zone_out(z) for z in nearby]


# ── GET /v1/zones

@router.get("")
async def list_zones(
    zone_type: str | None = Query(default=None),
    lat_min: float | None = Query(default=None),
    lat_max: float | None = Query(default=None),
    lng_min: float | None = Query(default=None),
    lng_max: float | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return all active zones. Optional zone_type and bbox filters."""
    now = datetime.now(timezone.utc)
    q = _active_q(select(Zone), now)

    if zone_type:
        try:
            from app.models.alert import ZoneType
            q = q.where(Zone.zone_type == ZoneType(zone_type))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid zone_type: {zone_type}")

    # Legacy bbox filter (backward compat)
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
    return [_zone_out(z) for z in result.scalars().all()]


# ── GET /v1/zones/{zone_id}

@router.get("/{zone_id}")
async def get_zone(
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Single zone detail."""
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone not found")
    return _zone_out(zone)
