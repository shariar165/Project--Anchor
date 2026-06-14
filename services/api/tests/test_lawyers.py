import pytest

from app.models.lawyer import Lawyer


@pytest.mark.anyio
async def test_list_lawyers_empty(client, db_session, mock_redis):
    resp = await client.get("/v1/lawyers")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_lawyers_returns_all(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Rahim Uddin", district="Dhaka", specializations=["criminal"], verified=True),
        Lawyer(name="Karim Ali", district="Chittagong", specializations=["civil"], verified=False),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.anyio
async def test_list_lawyers_district_filter(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Dhaka Lawyer", district="Dhaka", specializations=[], verified=True),
        Lawyer(name="Sylhet Lawyer", district="Sylhet", specializations=[], verified=True),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers?district=Dhaka")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["district"] == "Dhaka"


@pytest.mark.anyio
async def test_list_lawyers_verified_only(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Verified One", district="Dhaka", specializations=[], verified=True),
        Lawyer(name="Unverified", district="Dhaka", specializations=[], verified=False),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers?verified_only=true")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["verified"] is True


@pytest.mark.anyio
async def test_list_lawyers_specialization_filter(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Criminal Lawyer", district="Dhaka", specializations=["criminal law", "defense"], verified=True),
        Lawyer(name="Civil Lawyer", district="Dhaka", specializations=["civil litigation"], verified=True),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers?specialization=criminal")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Criminal Lawyer"
