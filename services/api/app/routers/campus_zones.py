"""Campus zone CRUD for university admins.

Routes: /v1/admin/campus-zones
Auth: admin or super_admin role required.
Constraint: zone_type is always 'campus', shape_type is always 'polygon'.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.alert import Zone, ZoneType, ZoneStatus
from app.schemas.zones import ZoneCreate, ZonePatch, zone_color
from app.services.audit import log_event as audit_log
from app.services.device import get_ip

router = APIRouter(prefix="/v1/admin/campus-zones", tags=["campus-zones"])


def _centroid(coords: list[list[float]]) -> tuple[float, float]:
    """Arithmetic centroid of [[lat,lng],...] — good enough for non-self-intersecting polygons."""
    n = len(coords)
    return sum(c[0] for c in coords) / n, sum(c[1] for c in coords) / n


def _zone_out(z: Zone) -> dict:
    zt = z.zone_type.value if hasattr(z.zone_type, "value") else str(z.zone_type)
    return {
        "id": str(z.id),
        "name": z.name or z.label or "Campus zone",
        "zone_type": zt,
        "shape_type": z.shape_type or "polygon",
        "polygon_coords": z.polygon_coords,
        "center_lat": z.center_lat,
        "center_lng": z.center_lng,
        "radius_m": z.radius_m,
        "description_public": z.description_public,
        "color": zone_color(zt),
        "status": z.status.value if hasattr(z.status, "value") else str(z.status),
        "university_id": str(z.university_id) if z.university_id else None,
        "created_by_role": z.created_by_role,
        "expires_at": z.expires_at.isoformat() if z.expires_at else None,
        "created_at": z.created_at.isoformat(),
        "updated_at": z.created_at.isoformat(),  # zones table has no updated_at; use created_at
    }


# ── List campus zones ─────────────────────────────────────────────────────────

@router.get("")
@limiter.limit("120/minute")
async def list_campus_zones(
    request: Request,
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),
):
    """List all campus zones (active by default). Admins see all; super_admin sees all."""
    q = select(Zone).where(Zone.zone_type == ZoneType.campus)
    if not include_archived:
        q = q.where(Zone.status == ZoneStatus.active)
    q = q.order_by(desc(Zone.created_at))
    result = await db.execute(q)
    return [_zone_out(z) for z in result.scalars().all()]


# ── Create campus zone ────────────────────────────────────────────────────────

@router.post("", status_code=201)
@limiter.limit("30/minute")
async def create_campus_zone(
    body: ZoneCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),
):
    """Create a new campus boundary polygon. zone_type is forced to 'campus'."""
    if body.shape_type != "polygon":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Campus zones must be polygons")
    if body.zone_type != "campus":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="This endpoint only creates campus zones")
    if not body.polygon_coords or len(body.polygon_coords) < 3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Polygon requires at least 3 points")

    # Server-side centroid (client also sends center_lat/lng but we recompute)
    c_lat, c_lng = _centroid(body.polygon_coords)

    zone = Zone(
        zone_type=ZoneType.campus,
        name=body.name,
        shape_type="polygon",
        polygon_coords=body.polygon_coords,
        center_lat=c_lat,
        center_lng=c_lng,
        radius_m=None,
        description_public=body.description,
        university_id=body.university_id,
        created_by_id=token.user_id,
        created_by_role=token.role if isinstance(token.role, str) else token.role.value,
        status=ZoneStatus.active,
    )
    db.add(zone)
    await audit_log(db, "campus_zone_created", token.user_id, get_ip(request), {
        "name": body.name,
        "vertex_count": len(body.polygon_coords),
        "center_lat": round(c_lat, 5),
        "center_lng": round(c_lng, 5),
    })
    await db.commit()
    await db.refresh(zone)
    return _zone_out(zone)


# ── Update campus zone ────────────────────────────────────────────────────────

@router.patch("/{zone_id}")
@limiter.limit("30/minute")
async def update_campus_zone(
    zone_id: uuid.UUID,
    body: ZonePatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),
):
    """Update a campus zone's name, description, or polygon coords."""
    result = await db.execute(
        select(Zone).where(Zone.id == zone_id, Zone.zone_type == ZoneType.campus)
    )
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Campus zone not found")

    if body.name is not None:
        zone.name = body.name
    if body.description is not None:
        zone.description_public = body.description
    if body.university_id is not None:
        zone.university_id = body.university_id

    if body.polygon_coords is not None:
        if len(body.polygon_coords) < 3:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Polygon requires at least 3 points")
        zone.polygon_coords = body.polygon_coords
        zone.center_lat, zone.center_lng = _centroid(body.polygon_coords)

    if body.status is not None:
        zone.status = ZoneStatus(body.status)

    await audit_log(db, "campus_zone_updated", token.user_id, get_ip(request), {
        "zone_id": str(zone_id),
        "changes": body.model_dump(exclude_none=True),
    })
    await db.commit()
    await db.refresh(zone)
    return _zone_out(zone)


# ── Delete (archive) campus zone ──────────────────────────────────────────────

@router.delete("/{zone_id}", status_code=200)
@limiter.limit("20/minute")
async def archive_campus_zone(
    zone_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),
):
    """Soft-delete (archive) a campus zone."""
    result = await db.execute(
        select(Zone).where(Zone.id == zone_id, Zone.zone_type == ZoneType.campus)
    )
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Campus zone not found")
    if zone.status == ZoneStatus.archived:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Zone already archived")

    zone.status = ZoneStatus.archived
    await audit_log(db, "campus_zone_archived", token.user_id, get_ip(request), {
        "zone_id": str(zone_id),
        "name": zone.name,
    })
    await db.commit()
    return {"message": "Campus zone archived", "zone_id": str(zone_id)}
