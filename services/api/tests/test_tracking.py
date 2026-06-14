import pytest
from httpx import AsyncClient
from app.models.filing import Filing, FilingTemplate


@pytest.mark.asyncio
async def test_tracking_found(client: AsyncClient, db_session):
    template = FilingTemplate(key="test_tmpl", name="Test", category="complaint")
    db_session.add(template)
    await db_session.flush()

    record = Filing(
        template_id=template.id,
        anonymous_tracking_code="ANCH123456789A",
        state="under_review",
        final_outcome_note="Your complaint is being reviewed.",
        category="complaint",
        language="en",
    )
    db_session.add(record)
    await db_session.commit()

    resp = await client.get("/complaints/track/ANCH123456789A")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["status"] == "under_review"
    assert data["status_message"] == "Your complaint is being reviewed."


@pytest.mark.asyncio
async def test_tracking_not_found(client: AsyncClient):
    resp = await client.get("/complaints/track/INVALIDCODE999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
    assert data["status"] == "not_found"
