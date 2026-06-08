"""
Campus geofence router — save/load polygon boundary per tenant.

Admins and moderators can GET the current geofence and POST to update it.
The boundary is stored as a JSON array of {x, y} pixel coordinates matching
the frontend SVG viewport (400×200 coordinate space).
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.tenant_geofence import TenantGeofence

router = APIRouter(tags=["geofence"])


class GeofenceSaveRequest(BaseModel):
    vertices: list[list[float]]


@router.get("/v1/admin/geofence")
@limiter.limit("60/minute")
async def get_geofence(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Return the current tenant's saved geofence vertices, or 404 if none saved yet."""
    if not token.tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No tenant associated with this account")

    result = await db.execute(
        select(TenantGeofence).where(TenantGeofence.tenant_id == token.tenant_id)
    )
    geo = result.scalars().first()
    if not geo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No geofence saved yet")

    return {
        "tenant_id": str(geo.tenant_id),
        "vertices": json.loads(geo.vertices_json),
        "updated_at": geo.updated_at.isoformat() if geo.updated_at else None,
        "updated_by": str(geo.updated_by) if geo.updated_by else None,
    }


@router.post("/v1/admin/geofence", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def save_geofence(
    body: GeofenceSaveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Upsert the geofence boundary for the current tenant."""
    if not token.tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No tenant associated with this account")

    if len(body.vertices) < 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A geofence requires at least 3 vertices")

    vertices_json = json.dumps(body.vertices)

    result = await db.execute(
        select(TenantGeofence).where(TenantGeofence.tenant_id == token.tenant_id)
    )
    geo = result.scalars().first()

    now = datetime.now(tz=timezone.utc)
    if geo:
        geo.vertices_json = vertices_json
        geo.updated_at = now
        geo.updated_by = token.user_id
    else:
        geo = TenantGeofence(
            id=uuid.uuid4(),
            tenant_id=token.tenant_id,
            vertices_json=vertices_json,
            updated_at=now,
            updated_by=token.user_id,
        )
        db.add(geo)

    await db.commit()
    return {"message": "Geofence saved", "vertex_count": len(body.vertices)}
