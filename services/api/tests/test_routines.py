import pytest
from sqlalchemy import update

from app.models.user import User


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_admin_tokens(client, db_session, email: str, password: str) -> dict:
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, f"Re-login failed: {resp.json()}"
    return resp.json()


@pytest.mark.anyio
async def test_list_routines_empty(client, db_session, mock_redis):
    resp = await client.get("/v1/routines")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_draft_not_visible_without_auth(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    resp = await client.post("/v1/routines", json={
        "title": "CSE Routine Spring 2026",
        "department": "CSE",
        "batch": "2022",
        "semester": "Spring 2026",
        "slots": [],
    }, headers=_auth(admin_tokens))
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"

    # Unauthenticated request sees nothing
    public = await client.get("/v1/routines")
    assert public.json() == []


@pytest.mark.anyio
async def test_admin_sees_draft(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    await client.post("/v1/routines", json={
        "title": "Draft Routine",
        "department": "EEE",
        "slots": [],
    }, headers=_auth(admin_tokens))

    resp = await client.get("/v1/routines", headers=_auth(admin_tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "draft"


@pytest.mark.anyio
async def test_publish_routine(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    create = await client.post("/v1/routines", json={
        "title": "Published Routine",
        "department": "CSE",
        "slots": [{"day": "Monday", "start_time": "09:00", "end_time": "10:30", "course_name": "Math"}],
    }, headers=_auth(admin_tokens))
    rid = create.json()["id"]

    pub = await client.post(f"/v1/routines/{rid}/publish", headers=_auth(admin_tokens))
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
    assert pub.json()["published_at"] is not None

    # Now visible without auth
    public = await client.get("/v1/routines")
    assert len(public.json()) == 1


@pytest.mark.anyio
async def test_publish_already_published_returns_409(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    create = await client.post("/v1/routines", json={"title": "Test", "slots": []}, headers=_auth(admin_tokens))
    rid = create.json()["id"]

    await client.post(f"/v1/routines/{rid}/publish", headers=_auth(admin_tokens))
    again = await client.post(f"/v1/routines/{rid}/publish", headers=_auth(admin_tokens))
    assert again.status_code == 409


@pytest.mark.anyio
async def test_filter_by_dept(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    headers = _auth(admin_tokens)

    for dept in ["CSE", "EEE"]:
        r = await client.post("/v1/routines", json={"title": f"{dept} Routine", "department": dept, "slots": []}, headers=headers)
        await client.post(f"/v1/routines/{r.json()['id']}/publish", headers=headers)

    resp = await client.get("/v1/routines?department=CSE")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["department"] == "CSE"


@pytest.mark.anyio
async def test_update_routine(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    headers = _auth(admin_tokens)

    r = await client.post("/v1/routines", json={"title": "Old Title", "slots": []}, headers=headers)
    rid = r.json()["id"]

    patch = await client.patch(f"/v1/routines/{rid}", json={"title": "New Title"}, headers=headers)
    assert patch.status_code == 200
    assert patch.json()["title"] == "New Title"


@pytest.mark.anyio
async def test_create_routine_requires_admin(client, db_session, mock_redis, registered_user):
    resp = await client.post("/v1/routines", json={"title": "X", "slots": []},
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403
