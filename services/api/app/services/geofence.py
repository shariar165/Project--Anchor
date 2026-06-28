import math
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two WGS84 coordinates (Haversine)."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def get_nearby_users(
    db: AsyncSession,
    lat: float,
    lng: float,
    radius_m: int,
    alerting_user_hash: str,
    fallback_radii: list[int] | None = None,
    min_users: int = 5,
) -> list[dict]:
    """
    Return nearby consenting users within radius_m of (lat, lng).

    Each result: {user_id, user_id_hash, fcm_tokens: list[str], distance_m: int}

    Uses a SQL bounding-box pre-filter then Python-side Haversine for precision.
    Expands to fallback_radii if fewer than min_users found at the primary radius.
    """
    from app.models.alert import UserLocationSnapshot, UserFCMToken

    if fallback_radii is None:
        fallback_radii = [get_settings().alert_zone_fallback_radius_m, 5000]

    settings = get_settings()
    staleness_cutoff = datetime.now(tz=timezone.utc) - timedelta(
        minutes=settings.alert_location_staleness_minutes
    )

    for search_radius in [radius_m, *fallback_radii]:
        deg_lat = search_radius / 111_000
        deg_lng = search_radius / (111_000 * math.cos(math.radians(lat)) + 1e-9)

        result = await db.execute(
            select(UserLocationSnapshot).where(
                and_(
                    UserLocationSnapshot.geofence_consent == True,
                    UserLocationSnapshot.last_seen_at >= staleness_cutoff,
                    UserLocationSnapshot.user_id_hash != alerting_user_hash,
                    UserLocationSnapshot.lat.between(lat - deg_lat, lat + deg_lat),
                    UserLocationSnapshot.lng.between(lng - deg_lng, lng + deg_lng),
                )
            )
        )
        snapshots = result.scalars().all()

        candidates = []
        for snap in snapshots:
            dist = haversine(lat, lng, snap.lat, snap.lng)
            if dist <= search_radius:
                candidates.append((snap.user_id, snap.user_id_hash, int(dist)))

        if not candidates:
            continue

        # Fetch FCM tokens for candidates
        user_ids = [uid for uid, _, _ in candidates]
        tok_result = await db.execute(
            select(UserFCMToken).where(
                and_(
                    UserFCMToken.user_id.in_(user_ids),
                    UserFCMToken.disabled_at.is_(None),
                )
            )
        )
        tokens_by_user: dict = {}
        for tok in tok_result.scalars().all():
            tokens_by_user.setdefault(str(tok.user_id), []).append(tok.fcm_token)

        nearby = [
            {
                "user_id": uid,
                "user_id_hash": user_hash,
                "fcm_tokens": tokens_by_user.get(str(uid), []),
                "distance_m": dist_m,
            }
            for uid, user_hash, dist_m in sorted(candidates, key=lambda x: x[2])
        ]

        if len(nearby) >= min_users or search_radius == fallback_radii[-1]:
            return nearby

    return []
