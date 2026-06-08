import pytest


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


_RATING_PAYLOAD = {
    "department": "Computer Science",
    "period": "Spring-2026",
    "overall": 4,
    "teaching_quality": 5,
    "resources": 3,
    "environment": 4,
    "feedback": "Great semester overall.",
}


@pytest.mark.anyio
async def test_create_rating(client, db_session, mock_redis, registered_user):
    resp = await client.post("/v1/departments/ratings", json=_RATING_PAYLOAD,
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 201
    data = resp.json()
    assert data["department"] == "Computer Science"
    assert data["overall"] == 4
    assert data["anonymous"] is False
    assert data["rater_user_id"] is not None


@pytest.mark.anyio
async def test_duplicate_rating_returns_409(client, db_session, mock_redis, registered_user):
    headers = _auth(registered_user["tokens"])
    await client.post("/v1/departments/ratings", json=_RATING_PAYLOAD, headers=headers)
    again = await client.post("/v1/departments/ratings", json=_RATING_PAYLOAD, headers=headers)
    assert again.status_code == 409


@pytest.mark.anyio
async def test_anonymous_rating_hides_rater(client, db_session, mock_redis, registered_user):
    payload = {**_RATING_PAYLOAD, "anonymous": True}
    resp = await client.post("/v1/departments/ratings", json=payload,
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 201
    assert resp.json()["rater_user_id"] is None


@pytest.mark.anyio
async def test_get_summary_empty(client, db_session, mock_redis):
    resp = await client.get("/v1/departments/Computer%20Science/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 0
    assert data["avg_overall"] is None


@pytest.mark.anyio
async def test_get_summary_with_ratings(client, db_session, mock_redis, registered_user):
    await client.post("/v1/departments/ratings", json=_RATING_PAYLOAD,
                      headers=_auth(registered_user["tokens"]))

    resp = await client.get("/v1/departments/Computer%20Science/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["avg_overall"] == 4.0
    assert data["avg_teaching"] == 5.0
    assert data["histogram"]["4"] == 1
    assert data["histogram"]["5"] == 0


@pytest.mark.anyio
async def test_my_ratings(client, db_session, mock_redis, registered_user):
    headers = _auth(registered_user["tokens"])
    await client.post("/v1/departments/ratings", json=_RATING_PAYLOAD, headers=headers)
    await client.post("/v1/departments/ratings", json={
        **_RATING_PAYLOAD,
        "department": "Electrical Engineering",
        "period": "Fall-2025",
    }, headers=headers)

    resp = await client.get("/v1/departments/ratings/mine", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.anyio
async def test_rating_requires_auth(client, db_session, mock_redis):
    resp = await client.post("/v1/departments/ratings", json=_RATING_PAYLOAD)
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_my_ratings_requires_auth(client, db_session, mock_redis):
    resp = await client.get("/v1/departments/ratings/mine")
    assert resp.status_code in (401, 403)
