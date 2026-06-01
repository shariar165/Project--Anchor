import pytest
from httpx import AsyncClient
from app.models.anonymous import AnonymousIdentityMapping


@pytest.mark.asyncio
async def test_tracking_found(client: AsyncClient, db_session):
    record = AnonymousIdentityMapping(
        anonymous_code="ANCH123456789A",
        complaint_id="CPL-001",
        status="under_review",
        status_message="Your complaint is being reviewed.",
    )
    db_session.add(record)
    await db_session.commit()

    resp = await client.get("/complaints/track/ANCH123456789A")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["status"] == "under_review"


@pytest.mark.asyncio
async def test_tracking_not_found(client: AsyncClient):
    resp = await client.get("/complaints/track/INVALIDCODE999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
    assert data["status"] == "not_found"
