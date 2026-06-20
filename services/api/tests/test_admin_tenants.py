"""
Tests for the super-admin tenant management endpoints (/v1/super-admin/tenants).

Access: super_admin only. Covers list, onboard (tenant + domains + initial admin),
conflict cases, suspend via PATCH, guarded delete, and domain management.
"""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import update

from app.models.user import User, Role


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_super_admin(client, db_session) -> dict:
    email = f"super_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Super Admin", "email": email,
        "password": password, "role": "user", "terms": True, "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    await db_session.execute(
        update(User).where(User.email == email).values(role=Role.super_admin)
    )
    await db_session.commit()
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"email": email, "password": password, "tokens": login.json()}


@pytest_asyncio.fixture
async def super_admin(client, db_session, mock_redis):
    return await _make_super_admin(client, db_session)


def _onboard_body(**over):
    slug = over.pop("slug", f"uni{uuid.uuid4().hex[:6]}")
    body = {
        "name": "Test University",
        "slug": slug,
        "email_domains": [f"{slug}.edu.bd"],
        "tier": "pilot",
        "country": "Bangladesh",
        "contact_name": "Dr. Test",
        "initial_admin": {
            "full_name": "Uni Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@{slug}.edu.bd",
            "password": "AdminPass!99",
        },
    }
    body.update(over)
    return body


# ─── Auth ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_requires_super_admin(client, registered_user):
    r = await client.get("/v1/super-admin/tenants", headers=_auth(registered_user["tokens"]))
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_unauthenticated(client, db_session, mock_redis):
    r = await client.get("/v1/super-admin/tenants")
    assert r.status_code in (401, 403)


# ─── List ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_empty(client, super_admin):
    r = await client.get("/v1/super-admin/tenants", headers=_auth(super_admin["tokens"]))
    assert r.status_code == 200
    assert r.json()["items"] == []


# ─── Onboard ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_onboard_happy_path(client, super_admin):
    h = _auth(super_admin["tokens"])
    body = _onboard_body()
    r = await client.post("/v1/super-admin/tenants", json=body, headers=h)
    assert r.status_code == 201, r.json()
    data = r.json()
    assert data["slug"] == body["slug"]
    assert data["status"] == "Pilot"
    assert data["vector_namespace"] == body["slug"]
    assert data["user_count"] == 1
    assert [d["domain"] for d in data["domains"]] == [body["email_domains"][0]]

    # the initial admin can log in
    login = await client.post("/auth/login", json={
        "identifier": body["initial_admin"]["email"],
        "password": body["initial_admin"]["password"],
    })
    assert login.status_code == 200

    # appears in the list with a real user count
    lst = await client.get("/v1/super-admin/tenants", headers=h)
    assert lst.json()["items"][0]["user_count"] == 1


@pytest.mark.asyncio
async def test_onboard_duplicate_slug(client, super_admin):
    h = _auth(super_admin["tokens"])
    body = _onboard_body(slug="dupe")
    assert (await client.post("/v1/super-admin/tenants", json=body, headers=h)).status_code == 201
    body2 = _onboard_body(slug="dupe")
    r = await client.post("/v1/super-admin/tenants", json=body2, headers=h)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_onboard_duplicate_domain(client, super_admin):
    h = _auth(super_admin["tokens"])
    body = _onboard_body(email_domains=["shared.edu.bd"])
    assert (await client.post("/v1/super-admin/tenants", json=body, headers=h)).status_code == 201
    body2 = _onboard_body(email_domains=["shared.edu.bd"])
    r = await client.post("/v1/super-admin/tenants", json=body2, headers=h)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_onboard_pwned_password(client, super_admin, monkeypatch):
    async def _pwned(pw): return True
    monkeypatch.setattr("app.routers.admin_tenants.pwd_svc.check_pwned", _pwned)
    h = _auth(super_admin["tokens"])
    r = await client.post("/v1/super-admin/tenants", json=_onboard_body(), headers=h)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_onboard_invalid_tier(client, super_admin):
    h = _auth(super_admin["tokens"])
    r = await client.post("/v1/super-admin/tenants", json=_onboard_body(tier="gold"), headers=h)
    assert r.status_code == 422  # pydantic validation


# ─── Patch / suspend ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_suspend_and_activate(client, super_admin):
    h = _auth(super_admin["tokens"])
    tid = (await client.post("/v1/super-admin/tenants", json=_onboard_body(), headers=h)).json()["id"]

    r = await client.patch(f"/v1/super-admin/tenants/{tid}", json={"active": False}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "Suspended"

    r = await client.patch(f"/v1/super-admin/tenants/{tid}", json={"active": True, "tier": "active"}, headers=h)
    assert r.json()["status"] == "Active"


@pytest.mark.asyncio
async def test_patch_no_fields(client, super_admin):
    h = _auth(super_admin["tokens"])
    tid = (await client.post("/v1/super-admin/tenants", json=_onboard_body(), headers=h)).json()["id"]
    r = await client.patch(f"/v1/super-admin/tenants/{tid}", json={}, headers=h)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_404(client, super_admin):
    h = _auth(super_admin["tokens"])
    r = await client.get(f"/v1/super-admin/tenants/{uuid.uuid4()}", headers=h)
    assert r.status_code == 404


# ─── Domains ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_remove_domain(client, super_admin):
    h = _auth(super_admin["tokens"])
    tid = (await client.post("/v1/super-admin/tenants", json=_onboard_body(), headers=h)).json()["id"]

    r = await client.post(f"/v1/super-admin/tenants/{tid}/domains", json={"domain": "@extra.edu.bd"}, headers=h)
    assert r.status_code == 201
    domains = r.json()["domains"]
    assert "extra.edu.bd" in [d["domain"] for d in domains]

    extra_id = next(d["id"] for d in domains if d["domain"] == "extra.edu.bd")
    r = await client.delete(f"/v1/super-admin/tenants/{tid}/domains/{extra_id}", headers=h)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cannot_remove_last_domain(client, super_admin):
    h = _auth(super_admin["tokens"])
    created = (await client.post("/v1/super-admin/tenants", json=_onboard_body(), headers=h)).json()
    tid = created["id"]
    only_domain_id = created["domains"][0]["id"]
    r = await client.delete(f"/v1/super-admin/tenants/{tid}/domains/{only_domain_id}", headers=h)
    assert r.status_code == 409


# ─── Delete ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_with_users_blocked(client, super_admin):
    h = _auth(super_admin["tokens"])
    # onboard creates an initial admin -> tenant has a user
    tid = (await client.post("/v1/super-admin/tenants", json=_onboard_body(), headers=h)).json()["id"]
    r = await client.delete(f"/v1/super-admin/tenants/{tid}", headers=h)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_delete_empty_tenant(client, super_admin, db_session):
    h = _auth(super_admin["tokens"])
    created = (await client.post("/v1/super-admin/tenants", json=_onboard_body(), headers=h)).json()
    tid = created["id"]
    # detach the only user so the tenant is empty
    await db_session.execute(
        update(User).where(User.tenant_id == uuid.UUID(tid)).values(tenant_id=None)
    )
    await db_session.commit()

    r = await client.delete(f"/v1/super-admin/tenants/{tid}", headers=h)
    assert r.status_code == 200
    assert (await client.get(f"/v1/super-admin/tenants/{tid}", headers=h)).status_code == 404
