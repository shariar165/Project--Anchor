"""
Tests for the Verification Feed system.

Uses SQLite in-memory + fakeredis — no Docker required.
Step-up is monkeypatched to bypass the stepup-token requirement.
AI pre-screen is monkeypatched to always pass.
SSE publish is monkeypatched to a no-op.
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.feed import (
    VerificationFeedPost, VerificationFeedSignal, VerificationFeedFlag,
    UserFeedTrust, PostState, SignalType,
)
from app.deps import get_current_user


# ─── Module-level mocks ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_feed_bg(monkeypatch):
    """Bypass AI prescreening and SSE publishing in all feed tests."""
    async def _pass_prescreen(*a, **kw):
        return {"verdict": "pass", "reason": "", "flags": []}

    async def _noop(*a, **kw):
        pass

    monkeypatch.setattr("app.services.feed_prescreen.run_prescreen", _pass_prescreen)
    monkeypatch.setattr("app.services.feed_sse.publish_signal_update", _noop)
    monkeypatch.setattr("app.services.feed_svc.activate_post", _noop)


@pytest.fixture
def mock_stepup():
    """Allow tests to call step-up-gated endpoints with a regular access token."""
    from app.main import app as _app
    from app.deps import require_stepup
    _app.dependency_overrides[require_stepup] = get_current_user
    yield
    _app.dependency_overrides.pop(require_stepup, None)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


_POST_BODY = {
    "scope": "national",
    "category": "incident",
    "title": "Test accident on Mirpur Road",
    "body": "A major road accident occurred near Mirpur 10 roundabout involving two vehicles. Traffic is blocked in both directions.",
    "tags": ["mirpur", "traffic"],
}


# ─── Additional fixtures ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_user(client, mock_redis):
    """Register + verify an admin user."""
    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    password = "AdminPass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Admin User",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    tokens = verify.json()

    # Promote to admin directly in DB
    from app.models.user import User, Role
    from app.database import get_db
    from app.main import app
    db_override = app.dependency_overrides.get(get_db)
    if db_override:
        async for db in db_override():
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            if user:
                user.role = Role.admin
                await db.commit()
            break

    # Re-login to get token with admin role
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    login_tokens = login.json()
    return {"email": email, "password": password, "tokens": login_tokens}


@pytest_asyncio.fixture
async def second_user(client, mock_redis):
    """A second registered user for signal tests."""
    email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Second User",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    return {"email": email, "password": password, "tokens": verify.json()}


@pytest_asyncio.fixture
async def live_post(client, registered_user, db_session, mock_stepup):
    """Create a live feed post directly, bypassing background activation."""
    resp = await client.post("/v1/feed", json=_POST_BODY, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200, resp.text
    post_id = resp.json()["post_id"]

    # Force state to live (background task is mocked out)
    result = await db_session.execute(
        select(VerificationFeedPost).where(VerificationFeedPost.id == uuid.UUID(post_id))
    )
    post = result.scalars().first()
    post.state = PostState.live
    await db_session.commit()
    return {"id": post_id, "tokens": registered_user["tokens"], "post": post}


# ─── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_feed_requires_auth(client: AsyncClient):
    resp = await client.get("/v1/feed?scope=national")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 401 or 403 when no header


@pytest.mark.asyncio
async def test_publish_requires_stepup(client: AsyncClient, registered_user):
    """POST /v1/feed with a regular access token (no step-up) should fail."""
    resp = await client.post("/v1/feed", json=_POST_BODY, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_publish_success(client: AsyncClient, registered_user, db_session, mock_stepup):
    resp = await client.post("/v1/feed", json=_POST_BODY, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "post_id" in data
    assert "post_number" in data
    assert data["post_number"].startswith("VFP-")

    # Verify DB row created
    result = await db_session.execute(
        select(VerificationFeedPost).where(
            VerificationFeedPost.id == uuid.UUID(data["post_id"])
        )
    )
    post = result.scalars().first()
    assert post is not None
    assert post.title == _POST_BODY["title"]


@pytest.mark.asyncio
async def test_publish_ai_block(client: AsyncClient, registered_user, mock_stepup, monkeypatch):
    """AI prescreen block → 422."""
    async def _block_prescreen(*a, **kw):
        return {"verdict": "block", "reason": "hate_speech", "flags": ["safety"]}
    monkeypatch.setattr("app.services.feed_prescreen.run_prescreen", _block_prescreen)
    resp = await client.post("/v1/feed", json=_POST_BODY, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_national_feed(client: AsyncClient, registered_user, live_post):
    resp = await client.get("/v1/feed?scope=national", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    posts = resp.json()
    assert any(p["id"] == live_post["id"] for p in posts)


@pytest.mark.asyncio
async def test_get_post_detail(client: AsyncClient, registered_user, live_post):
    resp = await client.get(f"/v1/feed/{live_post['id']}", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == live_post["id"]
    assert data["body"] == _POST_BODY["body"]


@pytest.mark.asyncio
async def test_corroborate_toggle(client: AsyncClient, second_user, live_post, db_session):
    """Corroborate → corroborate again → signal removed (neutral)."""
    headers = _auth(second_user["tokens"])
    post_id = live_post["id"]

    r1 = await client.post(f"/v1/feed/{post_id}/corroborate", json={}, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["action"] == "added"
    assert r1.json()["counts"]["corroborate"] == 1

    r2 = await client.post(f"/v1/feed/{post_id}/corroborate", json={}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["action"] == "removed"
    assert r2.json()["counts"]["corroborate"] == 0


@pytest.mark.asyncio
async def test_challenge_after_corroborate(client: AsyncClient, second_user, live_post, db_session):
    """Corroborate then challenge → signal switches type."""
    headers = _auth(second_user["tokens"])
    post_id = live_post["id"]

    await client.post(f"/v1/feed/{post_id}/corroborate", json={}, headers=headers)

    r = await client.post(f"/v1/feed/{post_id}/challenge", json={}, headers=headers)
    assert r.status_code == 200
    assert r.json()["action"] == "changed"
    assert r.json()["signal_type"] == "challenge"
    assert r.json()["counts"]["corroborate"] == 0
    assert r.json()["counts"]["challenge"] == 1


@pytest.mark.asyncio
async def test_remove_signal(client: AsyncClient, second_user, live_post, db_session):
    headers = _auth(second_user["tokens"])
    post_id = live_post["id"]

    await client.post(f"/v1/feed/{post_id}/corroborate", json={}, headers=headers)

    r = await client.delete(f"/v1/feed/{post_id}/signal", headers=headers)
    assert r.status_code == 204

    # Verify signal gone
    result = await db_session.execute(
        select(VerificationFeedSignal).where(
            VerificationFeedSignal.post_id == uuid.UUID(post_id)
        )
    )
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_self_signal_blocked(client: AsyncClient, registered_user, live_post):
    """Author cannot corroborate their own post."""
    r = await client.post(
        f"/v1/feed/{live_post['id']}/corroborate",
        json={},
        headers=_auth(registered_user["tokens"]),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_flag_post(client: AsyncClient, second_user, live_post, db_session):
    headers = _auth(second_user["tokens"])
    post_id = live_post["id"]

    r1 = await client.post(f"/v1/feed/{post_id}/flag",
                           json={"flag_reason": "off_topic"}, headers=headers)
    assert r1.status_code == 200

    # Duplicate flag → 409
    r2 = await client.post(f"/v1/feed/{post_id}/flag",
                           json={"flag_reason": "spam"}, headers=headers)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_flag_threshold_triggers_review(
    client: AsyncClient, registered_user, second_user, live_post, db_session
):
    """3 flags → post state becomes under_review."""
    post_id = live_post["id"]

    # Create 2 more users to flag
    users = []
    for i in range(3):
        email = f"flagger{i}_{uuid.uuid4().hex[:6]}@example.com"
        reg = await client.post("/auth/register", json={
            "full_name": f"Flagger {i}", "email": email,
            "password": "Pass!9999", "role": "user", "terms": True, "data_consent": True,
        })
        otp = reg.json()["dev_otp"]
        tok = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
        users.append(tok.json())

    for tok in users:
        await client.post(f"/v1/feed/{post_id}/flag",
                          json={"flag_reason": "spam"},
                          headers={"Authorization": f"Bearer {tok['access_token']}"})

    # Refresh from DB
    await db_session.refresh(live_post["post"])
    assert live_post["post"].state == PostState.under_review


@pytest.mark.asyncio
async def test_edit_post_resets_signals(
    client: AsyncClient, registered_user, second_user, live_post, db_session, mock_stepup
):
    """Editing a post clears all signals and resets admin_confirmed."""
    post_id = live_post["id"]

    # Add a signal
    await client.post(f"/v1/feed/{post_id}/corroborate", json={},
                      headers=_auth(second_user["tokens"]))

    # Edit
    r = await client.patch(f"/v1/feed/{post_id}",
                           json={"title": "Updated accident report on Mirpur Road section"},
                           headers=_auth(registered_user["tokens"]))
    assert r.status_code == 200

    # Signals should be cleared
    result = await db_session.execute(
        select(VerificationFeedSignal).where(
            VerificationFeedSignal.post_id == uuid.UUID(post_id)
        )
    )
    assert result.scalars().first() is None

    # admin_confirmed reset
    await db_session.refresh(live_post["post"])
    assert live_post["post"].admin_confirmed is False


@pytest.mark.asyncio
async def test_soft_delete(
    client: AsyncClient, registered_user, live_post, db_session, mock_stepup
):
    r = await client.delete(f"/v1/feed/{live_post['id']}",
                            headers=_auth(registered_user["tokens"]))
    assert r.status_code == 204

    await db_session.refresh(live_post["post"])
    assert live_post["post"].state == PostState.deleted_by_author


@pytest.mark.asyncio
async def test_admin_confirm(
    client: AsyncClient, admin_user, registered_user, live_post, db_session, mock_stepup
):
    post_id = live_post["id"]
    r = await client.post(
        f"/v1/feed/admin/{post_id}/confirm",
        json={"internal_note": "Verified accurate"},
        headers=_auth(admin_user["tokens"]),
    )
    assert r.status_code == 200, r.text

    await db_session.refresh(live_post["post"])
    assert live_post["post"].admin_confirmed is True

    # Trust should be recalculated
    result = await db_session.execute(
        select(UserFeedTrust).where(
            UserFeedTrust.user_id == live_post["post"].publisher_user_id
        )
    )
    trust = result.scalars().first()
    assert trust is not None
    assert trust.confirmed_accurate_count >= 1


@pytest.mark.asyncio
async def test_admin_mark_fake(
    client: AsyncClient, admin_user, live_post, db_session, mock_stepup
):
    post_id = live_post["id"]
    r = await client.post(
        f"/v1/feed/admin/{post_id}/mark-fake",
        json={
            "internal_note": "Confirmed false",
            "public_note": "This post was removed after review for inaccuracy per our policy.",
        },
        headers=_auth(admin_user["tokens"]),
    )
    assert r.status_code == 200, r.text

    await db_session.refresh(live_post["post"])
    assert live_post["post"].state == PostState.marked_fake


@pytest.mark.asyncio
async def test_admin_mark_fake_requires_public_note(
    client: AsyncClient, admin_user, live_post, mock_stepup
):
    r = await client.post(
        f"/v1/feed/admin/{live_post['id']}/mark-fake",
        json={"internal_note": "fake", "public_note": "too short"},
        headers=_auth(admin_user["tokens"]),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_queue_tabs(
    client: AsyncClient, admin_user, live_post, db_session, mock_stepup
):
    """Each queue tab should return a list without errors."""
    for tab in ("flagged", "pre_publish", "confirmation"):
        r = await client.get(
            f"/v1/feed/admin/queue?tab={tab}",
            headers=_auth(admin_user["tokens"]),
        )
        assert r.status_code == 200, f"tab={tab}: {r.text}"
        assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_admin_self_confirm_blocked(
    client: AsyncClient, registered_user, live_post, db_session, mock_stepup
):
    """Moderator cannot confirm their own post. Promote registered_user to admin first."""
    from app.models.user import User, Role
    from app.database import get_db
    from app.main import app as _app

    db_override = _app.dependency_overrides.get(get_db)
    if db_override:
        async for db in db_override():
            result = await db.execute(
                select(User).where(User.email == registered_user["email"])
            )
            user = result.scalars().first()
            if user:
                user.role = Role.admin
                await db.commit()
            break

    # Re-login to get admin token
    login = await client.post("/auth/login", json={
        "identifier": registered_user["email"],
        "password": registered_user["password"],
    })
    tokens = login.json()

    r = await client.post(
        f"/v1/feed/admin/{live_post['id']}/confirm",
        json={},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_my_profile(client: AsyncClient, registered_user):
    r = await client.get("/v1/feed/me/profile", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 200
    data = r.json()
    assert "trust_tier" in data
    assert data["trust_tier"] == "none"


@pytest.mark.asyncio
async def test_post_not_found(client: AsyncClient, registered_user):
    r = await client.get(f"/v1/feed/{uuid.uuid4()}", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 404
