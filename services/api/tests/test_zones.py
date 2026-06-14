import uuid
import pytest
from datetime import datetime, timezone, timedelta

from app.models.alert import Zone, ZoneType, ZoneStatus


@pytest.mark.anyio
async def test_list_zones_empty(client, db_session, mock_redis):
    resp = await client.get("/v1/zones")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_zones_returns_active(client, db_session, mock_redis):
    active_zone = Zone(
        zone_type=ZoneType.alert,
        center_lat=23.8103,
        center_lng=90.4125,
        radius_m=500,
        label="Test Zone",
        status=ZoneStatus.active,
    )
    archived_zone = Zone(
        zone_type=ZoneType.alert,
        center_lat=24.0,
        center_lng=90.0,
        radius_m=500,
        status=ZoneStatus.archived,
    )
    db_session.add_all([active_zone, archived_zone])
    await db_session.commit()

    resp = await client.get("/v1/zones")
    assert resp.status_code == 200
    ids = [z["id"] for z in resp.json()]
    assert str(active_zone.id) in ids
    assert str(archived_zone.id) not in ids


@pytest.mark.anyio
async def test_list_zones_excludes_expired(client, db_session, mock_redis):
    valid = Zone(
        zone_type=ZoneType.alert,
        center_lat=23.8, center_lng=90.4,
        radius_m=300, status=ZoneStatus.active,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    expired = Zone(
        zone_type=ZoneType.alert,
        center_lat=23.9, center_lng=90.5,
        radius_m=300, status=ZoneStatus.active,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add_all([valid, expired])
    await db_session.commit()

    resp = await client.get("/v1/zones")
    ids = [z["id"] for z in resp.json()]
    assert str(valid.id) in ids
    assert str(expired.id) not in ids


@pytest.mark.anyio
async def test_list_zones_bbox_filter(client, db_session, mock_redis):
    inside = Zone(
        zone_type=ZoneType.alert,
        center_lat=23.8103, center_lng=90.4125,
        radius_m=500, status=ZoneStatus.active,
        label="Inside",
    )
    outside = Zone(
        zone_type=ZoneType.alert,
        center_lat=10.0, center_lng=50.0,
        radius_m=500, status=ZoneStatus.active,
        label="Outside",
    )
    db_session.add_all([inside, outside])
    await db_session.commit()

    resp = await client.get("/v1/zones?lat_min=23.0&lat_max=24.0&lng_min=90.0&lng_max=91.0")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["label"] == "Inside"
