import uuid
import pytest
from sqlalchemy import update, select

from app.models.user import User
from app.services import notification_svc


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _register(client, mock_redis, role: str = "user") -> dict:
    r, _ = mock_redis
    email = f"notif_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Notif User", "email": email, "password": password,
        "role": role, "terms": True, "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    assert verify.status_code == 200, verify.json()
    return {"email": email, "password": password, "tokens": verify.json()}


async def _make_admin_and_relogin(client, db_session, email: str, password: str) -> dict:
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()


async def _user_id(db_session, email: str) -> uuid.UUID:
    res = await db_session.execute(select(User.id).where(User.email == email))
    return res.scalar_one()


# ── Basic feed ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_empty(client, db_session, mock_redis, registered_user):
    resp = await client.get("/v1/notifications", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "unread_count": 0}


@pytest.mark.anyio
async def test_requires_auth(client, db_session, mock_redis):
    resp = await client.get("/v1/notifications")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_create_list_and_mark_read(client, db_session, mock_redis, registered_user):
    uid = await _user_id(db_session, registered_user["email"])
    await notification_svc.create(
        db_session, user_id=uid, type="case", title="Case routed",
        body="Your complaint was routed.", mode="campus", route="cases",
    )
    headers = _auth(registered_user["tokens"])

    resp = await client.get("/v1/notifications", headers=headers)
    data = resp.json()
    assert data["unread_count"] == 1
    assert len(data["items"]) == 1
    notif = data["items"][0]
    assert notif["type"] == "case"
    assert notif["read_at"] is None
    assert notif["route"] == "cases"

    # Mark the one notification read
    mark = await client.post(f"/v1/notifications/{notif['id']}/read", headers=headers)
    assert mark.status_code == 200
    resp2 = await client.get("/v1/notifications", headers=headers)
    assert resp2.json()["unread_count"] == 0


@pytest.mark.anyio
async def test_mark_read_not_owner_404(client, db_session, mock_redis, registered_user):
    headers = _auth(registered_user["tokens"])
    bogus = uuid.uuid4()
    resp = await client.post(f"/v1/notifications/{bogus}/read", headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_read_all(client, db_session, mock_redis, registered_user):
    uid = await _user_id(db_session, registered_user["email"])
    for i in range(3):
        await notification_svc.create(
            db_session, user_id=uid, type="notice", title=f"N{i}", mode="campus",
        )
    headers = _auth(registered_user["tokens"])
    assert (await client.get("/v1/notifications", headers=headers)).json()["unread_count"] == 3
    res = await client.post("/v1/notifications/read-all", headers=headers)
    assert res.json()["marked_read"] == 3
    assert (await client.get("/v1/notifications", headers=headers)).json()["unread_count"] == 0


@pytest.mark.anyio
async def test_mode_filter(client, db_session, mock_redis, registered_user):
    uid = await _user_id(db_session, registered_user["email"])
    await notification_svc.create(db_session, user_id=uid, type="notice", title="campus only", mode="campus")
    await notification_svc.create(db_session, user_id=uid, type="lawyer", title="country only", mode="country")
    await notification_svc.create(db_session, user_id=uid, type="alert", title="both modes", mode=None)
    headers = _auth(registered_user["tokens"])

    campus = (await client.get("/v1/notifications?mode=campus", headers=headers)).json()
    titles = {i["title"] for i in campus["items"]}
    assert titles == {"campus only", "both modes"}

    country = (await client.get("/v1/notifications?mode=country", headers=headers)).json()
    titles = {i["title"] for i in country["items"]}
    assert titles == {"country only", "both modes"}


# ── Preferences + enforcement ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_prefs_roundtrip(client, db_session, mock_redis, registered_user):
    headers = _auth(registered_user["tokens"])
    defaults = (await client.get("/v1/notifications/preferences", headers=headers)).json()
    assert defaults == {"alerts": True, "cases": True, "notices": True, "feed": True, "marketing": False}

    upd = await client.put("/v1/notifications/preferences", json={"notices": False, "marketing": True}, headers=headers)
    assert upd.status_code == 200
    assert upd.json()["notices"] is False
    assert upd.json()["marketing"] is True
    # Other fields unchanged
    assert upd.json()["alerts"] is True

    again = (await client.get("/v1/notifications/preferences", headers=headers)).json()
    assert again["notices"] is False


@pytest.mark.anyio
async def test_enforcement_disabled_category_not_created(client, db_session, mock_redis, registered_user):
    headers = _auth(registered_user["tokens"])
    await client.put("/v1/notifications/preferences", json={"notices": False}, headers=headers)

    uid = await _user_id(db_session, registered_user["email"])
    # notice type maps to the disabled "notices" category → suppressed
    suppressed = await notification_svc.create(db_session, user_id=uid, type="notice", title="blocked", mode="campus")
    assert suppressed is None
    # case type still allowed
    allowed = await notification_svc.create(db_session, user_id=uid, type="case", title="ok", mode="campus")
    assert allowed is not None

    data = (await client.get("/v1/notifications", headers=headers)).json()
    assert data["unread_count"] == 1
    assert data["items"][0]["title"] == "ok"


# ── Generation hook: notice publish ───────────────────────────────────────────

@pytest.mark.anyio
async def test_notice_publish_generates_notification(client, db_session, mock_redis, registered_user):
    recipient = await _register(client, mock_redis, role="user")
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    create = await client.post("/v1/notices", json={
        "scope": "university", "title": "Exam Week", "body": "Finals start Monday.",
    }, headers=_auth(admin_tokens))
    nid = create.json()["id"]
    pub = await client.post(f"/v1/notices/{nid}/publish", headers=_auth(admin_tokens))
    assert pub.status_code == 200

    feed = (await client.get("/v1/notifications", headers=_auth(recipient["tokens"]))).json()
    assert feed["unread_count"] == 1
    notif = feed["items"][0]
    assert notif["type"] == "notice"
    assert notif["title"] == "Exam Week"
    assert notif["route"] == "notices"
    assert notif["params"]["notice_id"] == nid


@pytest.mark.anyio
async def test_notice_publish_respects_disabled_pref(client, db_session, mock_redis, registered_user):
    recipient = await _register(client, mock_redis, role="user")
    # Recipient opts out of campus notices
    await client.put("/v1/notifications/preferences", json={"notices": False}, headers=_auth(recipient["tokens"]))

    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    create = await client.post("/v1/notices", json={
        "scope": "university", "title": "Skipped", "body": "Should not notify.",
    }, headers=_auth(admin_tokens))
    await client.post(f"/v1/notices/{create.json()['id']}/publish", headers=_auth(admin_tokens))

    feed = (await client.get("/v1/notifications", headers=_auth(recipient["tokens"]))).json()
    assert feed["unread_count"] == 0


# ── Admin aggregate ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_admin_aggregate_requires_admin(client, db_session, mock_redis, registered_user):
    resp = await client.get("/v1/admin/notifications", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_admin_aggregate_shape(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    resp = await client.get("/v1/admin/notifications", headers=_auth(admin_tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "unread_count" in body
    assert isinstance(body["items"], list)


@pytest.mark.anyio
async def test_admin_channel_prefs_roundtrip(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    headers = _auth(admin_tokens)
    assert (await client.get("/v1/admin/notifications/preferences", headers=headers)).json() == {"channels": {}}
    upd = await client.patch("/v1/admin/notifications/preferences",
                             json={"channels": {"pushNewCase": True, "emailDaily": False}}, headers=headers)
    assert upd.status_code == 200
    assert upd.json()["channels"]["pushNewCase"] is True
    again = (await client.get("/v1/admin/notifications/preferences", headers=headers)).json()
    assert again["channels"]["emailDaily"] is False
