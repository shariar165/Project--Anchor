import pytest
from sqlalchemy import update

from app.config import get_settings
from app.models.user import User


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def force_ai_offline(monkeypatch):
    """Point Ollama at an unreachable address so generation deterministically falls back,
    regardless of whether a real Ollama is running on the test machine."""
    monkeypatch.setattr(get_settings(), "ollama_base_url", "http://127.0.0.1:9", raising=False)


async def _make_admin_and_relogin(client, db_session, email: str, password: str) -> dict:
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, f"Re-login failed: {resp.json()}"
    return resp.json()


@pytest.mark.anyio
async def test_generate_requires_admin(client, db_session, mock_redis, registered_user):
    resp = await client.post(
        "/v1/notices/generate",
        json={"prompt": "Library hours extended during finals."},
        headers=_auth(registered_user["tokens"]),
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_generate_unauthenticated(client, db_session, mock_redis):
    resp = await client.post(
        "/v1/notices/generate",
        json={"prompt": "Library hours extended during finals."},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_generate_english_fallback(client, db_session, mock_redis, registered_user, force_ai_offline):
    """With no Ollama in the test env, the service falls back to a template draft."""
    admin = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    resp = await client.post(
        "/v1/notices/generate",
        json={
            "prompt": "The library will extend hours to 1 AM during finals week (June 8-15).",
            "language": "en",
            "tone": "Formal · institutional",
            "audience": "University-wide",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["language"] == "en"
    assert data["ai_generated"] is False  # Ollama unavailable in CI -> fallback
    assert data["body"].strip()
    assert "Daffodil International University" in data["body"]
    assert data["subject"].strip()


@pytest.mark.anyio
async def test_generate_bangla_fallback(client, db_session, mock_redis, registered_user, force_ai_offline):
    admin = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    resp = await client.post(
        "/v1/notices/generate",
        json={"prompt": "পরীক্ষাকালীন গ্রন্থাগারের সময়সূচি পরিবর্তন।", "language": "bn"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["language"] == "bn"
    assert "ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি" in data["body"]


@pytest.mark.anyio
async def test_generate_rejects_empty_prompt(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"]
    )
    resp = await client.post(
        "/v1/notices/generate", json={"prompt": ""}, headers=_auth(admin)
    )
    assert resp.status_code == 422  # min_length validation
