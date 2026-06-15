"""Super-admin zone CRUD for purple, black, and red zones.

Routes: /v1/super-admin/zones
Auth: super_admin role only.
Supports both polygon and circle shapes.
Does NOT handle campus zones (those are admin-only via campus_zones.py).
"""
import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.alert import Zone, ZoneType, ZoneStatus
from app.models.user import Role
from app.schemas.zones import ZoneCreate, ZonePatch, zone_color
from app.services.audit import log_event as audit_log
from app.services.device import get_ip

router = APIRouter(prefix="/v1/super-admin/zones", tags=["super-admin-zones"])

_ALLOWED_TYPES = {ZoneType.purple, ZoneType.black, ZoneType.red}


def _centroid(coords: list[list[float]]) -> tuple[float, float]:
    n = len(coords)
    return sum(c[0] for c in coords) / n, sum(c[1] for c in coords) / n


def _zone_out(z: Zone) -> dict:
    zt = z.zone_type.value if hasattr(z.zone_type, "value") else str(z.zone_type)
    return {
        "id": str(z.id),
        "name": z.name or z.label or zt.capitalize(),
        "zone_type": zt,
        "shape_type": z.shape_type or "circle",
        "polygon_coords": z.polygon_coords,
        "center_lat": z.center_lat,
        "center_lng": z.center_lng,
        "radius_m": z.radius_m,
        "description_public": z.description_public,
        "color": zone_color(zt),
        "status": z.status.value if hasattr(z.status, "value") else str(z.status),
        "expires_at": z.expires_at.isoformat() if z.expires_at else None,
        "created_by_role": z.created_by_role,
        "created_at": z.created_at.isoformat(),
    }


def _require_super_admin(token: TokenData) -> None:
    """super_admin bypasses require_role() but we still want explicit enforcement here."""
    role_str = token.role.value if hasattr(token.role, "value") else str(token.role)
    if role_str != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="super_admin role required")


# ── List zones ────────────────────────────────────────────────────────────────

@router.get("")
@limiter.limit("120/minute")
async def list_super_zones(
    request: Request,
    zone_type: str | None = Query(default=None, description="Filter: red|purple|black"),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """List manually-created danger zones (red, purple, black)."""
    _require_super_admin(token)

    q = select(Zone).where(Zone.zone_type.in_([ZoneType.purple, ZoneType.black, ZoneType.red]))
    if not include_archived:
        q = q.where(Zone.status == ZoneStatus.active)
    if zone_type:
        try:
            zt = ZoneType(zone_type)
            if zt not in _ALLOWED_TYPES:
                raise ValueError()
            q = q.where(Zone.zone_type == zt)
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid zone_type '{zone_type}'. Must be red, purple, or black.",
            )
    q = q.order_by(desc(Zone.created_at)).limit(limit)
    result = await db.execute(q)
    return [_zone_out(z) for z in result.scalars().all()]


# ── Create zone ───────────────────────────────────────────────────────────────

@router.post("", status_code=201)
@limiter.limit("30/minute")
async def create_super_zone(
    body: ZoneCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Create a new purple, black, or red zone (polygon or circle)."""
    _require_super_admin(token)

    try:
        zt = ZoneType(body.zone_type)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid zone_type: {body.zone_type}")

    if zt not in _ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only creates red, purple, or black zones. Campus zones use /v1/admin/campus-zones.",
        )

    if body.shape_type == "polygon":
        if not body.polygon_coords or len(body.polygon_coords) < 3:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Polygon requires at least 3 points")
        c_lat, c_lng = _centroid(body.polygon_coords)
        r_m = None
    else:  # circle
        if not body.radius_m:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="radius_m is required for circle zones")
        c_lat, c_lng = body.center_lat, body.center_lng
        r_m = body.radius_m

    zone = Zone(
        zone_type=zt,
        name=body.name,
        shape_type=body.shape_type,
        polygon_coords=body.polygon_coords if body.shape_type == "polygon" else None,
        center_lat=c_lat,
        center_lng=c_lng,
        radius_m=r_m,
        description_public=body.description,
        expires_at=body.expires_at,
        created_by_id=token.user_id,
        created_by_role="super_admin",
        status=ZoneStatus.active,
    )
    db.add(zone)
    await audit_log(db, "super_zone_created", token.user_id, get_ip(request), {
        "name": body.name,
        "zone_type": body.zone_type,
        "shape_type": body.shape_type,
        "center_lat": round(c_lat, 5),
        "center_lng": round(c_lng, 5),
    })
    await db.commit()
    await db.refresh(zone)
    return _zone_out(zone)


# ── Update zone ───────────────────────────────────────────────────────────────

@router.patch("/{zone_id}")
@limiter.limit("30/minute")
async def update_super_zone(
    zone_id: uuid.UUID,
    body: ZonePatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Update a super-admin zone."""
    _require_super_admin(token)

    result = await db.execute(
        select(Zone).where(
            Zone.id == zone_id,
            Zone.zone_type.in_([ZoneType.purple, ZoneType.black, ZoneType.red]),
        )
    )
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone not found")

    if body.name is not None:
        zone.name = body.name
    if body.description is not None:
        zone.description_public = body.description
    if body.radius_m is not None:
        zone.radius_m = body.radius_m
    if body.status is not None:
        zone.status = ZoneStatus(body.status)
    if body.expires_at is not None:
        zone.expires_at = body.expires_at

    if body.polygon_coords is not None:
        if len(body.polygon_coords) < 3:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Polygon requires at least 3 points")
        zone.polygon_coords = body.polygon_coords
        zone.center_lat, zone.center_lng = _centroid(body.polygon_coords)
    elif body.center_lat is not None:
        zone.center_lat = body.center_lat
    if body.center_lng is not None:
        zone.center_lng = body.center_lng

    await audit_log(db, "super_zone_updated", token.user_id, get_ip(request), {
        "zone_id": str(zone_id),
        "changes": body.model_dump(exclude_none=True),
    })
    await db.commit()
    await db.refresh(zone)
    return _zone_out(zone)


# ── Archive zone ──────────────────────────────────────────────────────────────

@router.delete("/{zone_id}", status_code=200)
@limiter.limit("20/minute")
async def archive_super_zone(
    zone_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Soft-delete (archive) a super-admin zone."""
    _require_super_admin(token)

    result = await db.execute(
        select(Zone).where(
            Zone.id == zone_id,
            Zone.zone_type.in_([ZoneType.purple, ZoneType.black, ZoneType.red]),
        )
    )
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone not found")
    if zone.status == ZoneStatus.archived:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Zone already archived")

    zone.status = ZoneStatus.archived
    await audit_log(db, "super_zone_archived", token.user_id, get_ip(request), {
        "zone_id": str(zone_id),
        "name": zone.name,
        "zone_type": zone.zone_type.value,
    })
    await db.commit()
    return {"message": "Zone archived", "zone_id": str(zone_id)}
