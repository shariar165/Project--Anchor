"""
Integration tests for zone CRUD endpoints.

Covers:
  /v1/super-admin/zones   — GET, POST, PATCH, DELETE (super_admin only)
  /v1/admin/campus-zones  — GET, POST, PATCH, DELETE (admin only)
  /v1/zones               — GET public (verifies zones surface on student map)

No Docker: SQLite in-memory + fakeredis.
"""
import uuid
import pytest
from sqlalchemy import update

from app.models.user import User, Role


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_user_with_role(client, db_session, role: Role, prefix: str) -> dict:
    """Register via email, verify, elevate to role in DB, re-login."""
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass!1234"

    reg = await client.post("/auth/register", json={
        "full_name": "Test User",
        "email": email,
        "password": password,
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]

    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    assert verify.status_code == 200, verify.json()

    await db_session.execute(update(User).where(User.email == email).values(role=role))
    await db_session.commit()

    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200, login.json()
    return {"email": email, "tokens": login.json()}


# ─── Super-admin zone helpers ────────────────────────────────────────────────

_CIRCLE_PAYLOAD = {
    "name": "Red Alert Zone",
    "zone_type": "red",
    "shape_type": "circle",
    "center_lat": 23.8103,
    "center_lng": 90.4125,
    "radius_m": 500,
    "description": "Danger area near test location",
}

_POLYGON_COORDS = [
    [23.81, 90.41],
    [23.82, 90.41],
    [23.82, 90.42],
    [23.81, 90.42],
]

_CAMPUS_COORDS = [
    [23.7450, 90.3718],
    [23.7460, 90.3718],
    [23.7460, 90.3730],
    [23.7450, 90.3730],
]


# ════════════════════════════════════════════════════════════════════════════════
# 1. Super-admin zone AUTH enforcement
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_super_zones_get_requires_auth(client, db_session, mock_redis):
    resp = await client.get("/v1/super-admin/zones")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_super_zones_get_requires_super_admin_not_admin(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.get("/v1/super-admin/zones", headers=_auth(admin["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_super_zones_get_requires_super_admin_not_user(client, db_session, mock_redis, registered_user):
    resp = await client.get("/v1/super-admin/zones", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_super_zones_post_requires_super_admin(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.post("/v1/super-admin/zones", headers=_auth(admin["tokens"]), json=_CIRCLE_PAYLOAD)
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════════════
# 2. Super-admin zone LIST
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_super_zones_list_empty(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    resp = await client.get("/v1/super-admin/zones", headers=_auth(sa["tokens"]))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_super_zones_list_returns_created_zone(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    headers = _auth(sa["tokens"])

    create = await client.post("/v1/super-admin/zones", headers=headers, json=_CIRCLE_PAYLOAD)
    assert create.status_code == 201
    zone_id = create.json()["id"]

    listing = await client.get("/v1/super-admin/zones", headers=headers)
    assert listing.status_code == 200
    ids = [z["id"] for z in listing.json()]
    assert zone_id in ids


@pytest.mark.asyncio
async def test_super_zones_list_excludes_archived_by_default(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    headers = _auth(sa["tokens"])

    create = await client.post("/v1/super-admin/zones", headers=headers, json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]
    await client.delete(f"/v1/super-admin/zones/{zone_id}", headers=headers)

    listing = await client.get("/v1/super-admin/zones", headers=headers)
    ids = [z["id"] for z in listing.json()]
    assert zone_id not in ids

    with_archived = await client.get("/v1/super-admin/zones?include_archived=true", headers=headers)
    ids_all = [z["id"] for z in with_archived.json()]
    assert zone_id in ids_all


# ════════════════════════════════════════════════════════════════════════════════
# 3. Super-admin zone CREATE
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_super_zones_create_circle(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=_CIRCLE_PAYLOAD)
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["name"] == "Red Alert Zone"
    assert data["zone_type"] == "red"
    assert data["shape_type"] == "circle"
    assert data["status"] == "active"
    assert data["radius_m"] == 500
    assert data["description_public"] == "Danger area near test location"
    assert data["created_by_role"] == "super_admin"
    assert "id" in data


@pytest.mark.asyncio
async def test_super_zones_create_purple_circle(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    payload = {**_CIRCLE_PAYLOAD, "name": "Murder Area", "zone_type": "purple"}
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=payload)
    assert resp.status_code == 201
    assert resp.json()["zone_type"] == "purple"


@pytest.mark.asyncio
async def test_super_zones_create_black_circle(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    payload = {**_CIRCLE_PAYLOAD, "name": "Assault Area", "zone_type": "black"}
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=payload)
    assert resp.status_code == 201
    assert resp.json()["zone_type"] == "black"


@pytest.mark.asyncio
async def test_super_zones_create_polygon(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json={
        "name": "Polygon Danger Zone",
        "zone_type": "purple",
        "shape_type": "polygon",
        "center_lat": 23.815,
        "center_lng": 90.415,
        "polygon_coords": _POLYGON_COORDS,
    })
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["zone_type"] == "purple"
    assert data["shape_type"] == "polygon"
    assert data["polygon_coords"] == _POLYGON_COORDS
    # Server overrides centroid from polygon_coords
    assert abs(data["center_lat"] - 23.815) < 0.01


@pytest.mark.asyncio
async def test_super_zones_create_rejects_campus_type(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json={
        "name": "Campus Zone",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.8, "center_lng": 90.4,
        "polygon_coords": _POLYGON_COORDS,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_super_zones_create_rejects_missing_name(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    payload = {k: v for k, v in _CIRCLE_PAYLOAD.items() if k != "name"}
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_super_zones_create_rejects_short_name(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json={
        **_CIRCLE_PAYLOAD, "name": "X"
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_super_zones_create_circle_requires_radius(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    payload = {k: v for k, v in _CIRCLE_PAYLOAD.items() if k != "radius_m"}
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=payload)
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_super_zones_create_polygon_requires_3_coords(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    resp = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json={
        "name": "Too Few Points",
        "zone_type": "red",
        "shape_type": "polygon",
        "center_lat": 23.8, "center_lng": 90.4,
        "polygon_coords": [[23.81, 90.41], [23.82, 90.41]],  # only 2 points
    })
    assert resp.status_code in (400, 422)


# ════════════════════════════════════════════════════════════════════════════════
# 4. Super-admin zone PATCH
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_super_zones_patch_name_and_description(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    headers = _auth(sa["tokens"])

    create = await client.post("/v1/super-admin/zones", headers=headers, json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    patch = await client.patch(f"/v1/super-admin/zones/{zone_id}", headers=headers, json={
        "name": "Updated Zone Name",
        "description": "Updated description",
    })
    assert patch.status_code == 200
    data = patch.json()
    assert data["name"] == "Updated Zone Name"
    assert data["description_public"] == "Updated description"


@pytest.mark.asyncio
async def test_super_zones_patch_radius(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    headers = _auth(sa["tokens"])

    create = await client.post("/v1/super-admin/zones", headers=headers, json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    patch = await client.patch(f"/v1/super-admin/zones/{zone_id}", headers=headers, json={"radius_m": 1200})
    assert patch.status_code == 200
    assert patch.json()["radius_m"] == 1200


@pytest.mark.asyncio
async def test_super_zones_patch_404_unknown_zone(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    fake_id = uuid.uuid4()
    resp = await client.patch(f"/v1/super-admin/zones/{fake_id}", headers=_auth(sa["tokens"]),
                              json={"name": "No Zone Here"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_super_zones_patch_requires_super_admin(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")

    create = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    resp = await client.patch(f"/v1/super-admin/zones/{zone_id}", headers=_auth(admin["tokens"]),
                              json={"name": "Hack Attempt"})
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════════════
# 5. Super-admin zone DELETE (archive)
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_super_zones_archive(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    headers = _auth(sa["tokens"])

    create = await client.post("/v1/super-admin/zones", headers=headers, json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    delete = await client.delete(f"/v1/super-admin/zones/{zone_id}", headers=headers)
    assert delete.status_code == 200
    assert delete.json()["zone_id"] == zone_id

    listing = await client.get("/v1/super-admin/zones", headers=headers)
    assert zone_id not in [z["id"] for z in listing.json()]


@pytest.mark.asyncio
async def test_super_zones_double_archive_rejected(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    headers = _auth(sa["tokens"])

    create = await client.post("/v1/super-admin/zones", headers=headers, json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    await client.delete(f"/v1/super-admin/zones/{zone_id}", headers=headers)
    resp = await client.delete(f"/v1/super-admin/zones/{zone_id}", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_super_zones_delete_404_unknown(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    fake_id = uuid.uuid4()
    resp = await client.delete(f"/v1/super-admin/zones/{fake_id}", headers=_auth(sa["tokens"]))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_super_zones_delete_requires_super_admin(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")

    create = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    resp = await client.delete(f"/v1/super-admin/zones/{zone_id}", headers=_auth(admin["tokens"]))
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════════════
# 6. Campus zone AUTH enforcement
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_campus_zones_get_requires_auth(client, db_session, mock_redis):
    resp = await client.get("/v1/admin/campus-zones")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_campus_zones_get_requires_admin_not_user(client, db_session, mock_redis, registered_user):
    resp = await client.get("/v1/admin/campus-zones", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════════════
# 7. Campus zone LIST
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_campus_zones_list_empty(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.get("/v1/admin/campus-zones", headers=_auth(admin["tokens"]))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_campus_zones_super_admin_can_list(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    resp = await client.get("/v1/admin/campus-zones", headers=_auth(sa["tokens"]))
    assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════════════
# 8. Campus zone CREATE
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_campus_zones_create_polygon(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.post("/v1/admin/campus-zones", headers=_auth(admin["tokens"]), json={
        "name": "Main Campus",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455,
        "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
        "description": "DIU main campus boundary",
    })
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["name"] == "Main Campus"
    assert data["zone_type"] == "campus"
    assert data["shape_type"] == "polygon"
    assert data["status"] == "active"
    assert data["polygon_coords"] == _CAMPUS_COORDS
    assert data["description_public"] == "DIU main campus boundary"


@pytest.mark.asyncio
async def test_campus_zones_create_rejects_circle(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.post("/v1/admin/campus-zones", headers=_auth(admin["tokens"]), json={
        "name": "Circle Campus",
        "zone_type": "campus",
        "shape_type": "circle",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "radius_m": 500,
    })
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_campus_zones_create_rejects_non_campus_type(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.post("/v1/admin/campus-zones", headers=_auth(admin["tokens"]), json={
        "name": "Red Zone via Admin",
        "zone_type": "red",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_campus_zones_create_rejects_missing_name(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.post("/v1/admin/campus-zones", headers=_auth(admin["tokens"]), json={
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_campus_zones_create_rejects_too_few_vertices(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    resp = await client.post("/v1/admin/campus-zones", headers=_auth(admin["tokens"]), json={
        "name": "Bad Polygon",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": [[23.74, 90.37], [23.75, 90.37]],  # only 2 points
    })
    assert resp.status_code in (400, 422)


# ════════════════════════════════════════════════════════════════════════════════
# 9. Campus zone PATCH
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_campus_zones_patch(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    headers = _auth(admin["tokens"])

    create = await client.post("/v1/admin/campus-zones", headers=headers, json={
        "name": "Old Campus Name",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
    })
    assert create.status_code == 201
    zone_id = create.json()["id"]

    patch = await client.patch(f"/v1/admin/campus-zones/{zone_id}", headers=headers, json={
        "name": "Updated Campus Name",
        "description": "Boundary updated",
    })
    assert patch.status_code == 200
    data = patch.json()
    assert data["name"] == "Updated Campus Name"
    assert data["description_public"] == "Boundary updated"


@pytest.mark.asyncio
async def test_campus_zones_patch_404(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    fake_id = uuid.uuid4()
    resp = await client.patch(f"/v1/admin/campus-zones/{fake_id}", headers=_auth(admin["tokens"]),
                              json={"name": "No Such Zone"})
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════════════════
# 10. Campus zone DELETE (archive)
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_campus_zones_archive(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    headers = _auth(admin["tokens"])

    create = await client.post("/v1/admin/campus-zones", headers=headers, json={
        "name": "To Archive",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
    })
    assert create.status_code == 201
    zone_id = create.json()["id"]

    delete = await client.delete(f"/v1/admin/campus-zones/{zone_id}", headers=headers)
    assert delete.status_code == 200

    listing = await client.get("/v1/admin/campus-zones", headers=headers)
    assert zone_id not in [z["id"] for z in listing.json()]


@pytest.mark.asyncio
async def test_campus_zones_double_archive_rejected(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    headers = _auth(admin["tokens"])

    create = await client.post("/v1/admin/campus-zones", headers=headers, json={
        "name": "Double Archive",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
    })
    zone_id = create.json()["id"]

    await client.delete(f"/v1/admin/campus-zones/{zone_id}", headers=headers)
    resp = await client.delete(f"/v1/admin/campus-zones/{zone_id}", headers=headers)
    assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════════════════
# 11. Public map visibility (GET /v1/zones)
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_public_map_shows_super_admin_zones(client, db_session, mock_redis):
    """Zones created via /v1/super-admin/zones appear at the public /v1/zones endpoint."""
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")

    create = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=_CIRCLE_PAYLOAD)
    assert create.status_code == 201
    zone_id = create.json()["id"]

    public = await client.get("/v1/zones")
    assert public.status_code == 200
    ids = [z["id"] for z in public.json()]
    assert zone_id in ids


@pytest.mark.asyncio
async def test_public_map_shows_campus_zones(client, db_session, mock_redis):
    """Campus zones created via /v1/admin/campus-zones appear at /v1/zones."""
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")

    create = await client.post("/v1/admin/campus-zones", headers=_auth(admin["tokens"]), json={
        "name": "Visible Campus",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
    })
    assert create.status_code == 201
    zone_id = create.json()["id"]

    public = await client.get("/v1/zones")
    assert public.status_code == 200
    ids = [z["id"] for z in public.json()]
    assert zone_id in ids


@pytest.mark.asyncio
async def test_public_map_hides_archived_super_admin_zone(client, db_session, mock_redis):
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    headers = _auth(sa["tokens"])

    create = await client.post("/v1/super-admin/zones", headers=headers, json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]
    await client.delete(f"/v1/super-admin/zones/{zone_id}", headers=headers)

    public = await client.get("/v1/zones")
    ids = [z["id"] for z in public.json()]
    assert zone_id not in ids


@pytest.mark.asyncio
async def test_public_map_hides_archived_campus_zone(client, db_session, mock_redis):
    admin = await _make_user_with_role(client, db_session, Role.admin, "admin")
    headers = _auth(admin["tokens"])

    create = await client.post("/v1/admin/campus-zones", headers=headers, json={
        "name": "Archived Campus",
        "zone_type": "campus",
        "shape_type": "polygon",
        "center_lat": 23.7455, "center_lng": 90.3724,
        "polygon_coords": _CAMPUS_COORDS,
    })
    zone_id = create.json()["id"]
    await client.delete(f"/v1/admin/campus-zones/{zone_id}", headers=headers)

    public = await client.get("/v1/zones")
    ids = [z["id"] for z in public.json()]
    assert zone_id not in ids


@pytest.mark.asyncio
async def test_public_map_zone_has_correct_color(client, db_session, mock_redis):
    """Zone color in public response matches the type."""
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    create = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    public = await client.get("/v1/zones")
    zone = next(z for z in public.json() if z["id"] == zone_id)
    assert zone["zone_type"] == "red"


@pytest.mark.asyncio
async def test_public_map_zone_has_name(client, db_session, mock_redis):
    """Zone name created via super-admin endpoint is returned at /v1/zones."""
    sa = await _make_user_with_role(client, db_session, Role.super_admin, "sa")
    create = await client.post("/v1/super-admin/zones", headers=_auth(sa["tokens"]), json=_CIRCLE_PAYLOAD)
    zone_id = create.json()["id"]

    public = await client.get("/v1/zones")
    zone = next(z for z in public.json() if z["id"] == zone_id)
    assert zone["name"] == "Red Alert Zone"
