import uuid
import pytest
import pytest_asyncio
from sqlalchemy import update

from app.models.user import User


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_admin_and_relogin(client, db_session, email: str, password: str) -> dict:
    """Promote user to admin in DB, then re-login so the JWT carries the admin role."""
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, f"Re-login failed: {resp.json()}"
    return resp.json()


async def _publish(client, headers: dict, notice_id: str) -> None:
    resp = await client.post(f"/v1/notices/{notice_id}/publish", headers=headers)
    assert resp.status_code == 200, f"Publish failed: {resp.json()}"


@pytest.mark.anyio
async def test_list_notices_empty(client, db_session, mock_redis):
    resp = await client.get("/v1/notices")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_create_notice_requires_admin(client, db_session, mock_redis, registered_user):
    payload = {
        "scope": "university",
        "title": "Test Notice",
        "body": "This is a test notice body.",
    }
    resp = await client.post("/v1/notices", json=payload, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_create_notice_as_admin(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    payload = {
        "scope": "university",
        "title": "Exam Schedule",
        "body": "Final exams are scheduled for next week.",
    }
    resp = await client.post("/v1/notices", json=payload, headers=_auth(admin_tokens))
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Exam Schedule"
    assert data["scope"] == "university"
    assert data["status"] == "draft"
    assert data["published_at"] is None


@pytest.mark.anyio
async def test_notice_draft_invisible_to_student(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    await client.post("/v1/notices", json={
        "scope": "university", "title": "Secret Draft", "body": "Not published yet.",
    }, headers=_auth(admin_tokens))

    # Unauthenticated — sees nothing
    resp = await client.get("/v1/notices")
    assert resp.json() == []

    # Regular user — also sees nothing
    resp = await client.get("/v1/notices", headers=_auth(registered_user["tokens"]))
    assert resp.json() == []


@pytest.mark.anyio
async def test_notice_publish_flow(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    headers = _auth(admin_tokens)

    create = await client.post("/v1/notices", json={
        "scope": "university", "title": "Published Notice", "body": "Now public.",
    }, headers=headers)
    nid = create.json()["id"]

    # Publish
    pub = await client.post(f"/v1/notices/{nid}/publish", headers=headers)
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
    assert pub.json()["published_at"] is not None

    # Publish again → 409
    again = await client.post(f"/v1/notices/{nid}/publish", headers=headers)
    assert again.status_code == 409

    # Now visible without auth
    resp = await client.get("/v1/notices")
    assert len(resp.json()) == 1


@pytest.mark.anyio
async def test_list_notices_scope_filter(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    headers = _auth(admin_tokens)

    uni = await client.post("/v1/notices", json={
        "scope": "university", "title": "Uni Notice", "body": "For everyone.",
    }, headers=headers)
    cse = await client.post("/v1/notices", json={
        "scope": "dept", "dept": "CSE", "title": "CSE Notice", "body": "For CSE only.",
    }, headers=headers)

    # Publish both so they're visible
    await _publish(client, headers, uni.json()["id"])
    await _publish(client, headers, cse.json()["id"])

    resp = await client.get("/v1/notices?scope=dept")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["title"] == "CSE Notice"
    assert items[0]["dept"] == "CSE"


@pytest.mark.anyio
async def test_list_notices_dept_filter(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    headers = _auth(admin_tokens)

    cse = await client.post("/v1/notices", json={
        "scope": "dept", "dept": "CSE", "title": "CSE Only", "body": "CSE dept notice.",
    }, headers=headers)
    eee = await client.post("/v1/notices", json={
        "scope": "dept", "dept": "EEE", "title": "EEE Only", "body": "EEE dept notice.",
    }, headers=headers)

    await _publish(client, headers, cse.json()["id"])
    await _publish(client, headers, eee.json()["id"])

    resp = await client.get("/v1/notices?scope=dept&dept=CSE")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["dept"] == "CSE"


@pytest.mark.anyio
async def test_update_notice(client, db_session, mock_redis, registered_user):
    admin_tokens = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    headers = _auth(admin_tokens)

    create = await client.post("/v1/notices", json={
        "scope": "university", "title": "Old Title", "body": "Old body.",
    }, headers=headers)
    nid = create.json()["id"]

    patch = await client.patch(f"/v1/notices/{nid}", json={"title": "New Title"}, headers=headers)
    assert patch.status_code == 200
    assert patch.json()["title"] == "New Title"
    assert patch.json()["status"] == "draft"
