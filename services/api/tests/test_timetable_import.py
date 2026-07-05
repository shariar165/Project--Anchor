"""Integration tests for the timetable CSV/XLSX import endpoint.

Covers the relational entities added on top of courses/rooms:
batches, faculty, offerings, eligibility.

Run: .venv/Scripts/python.exe -m pytest tests/test_timetable_import.py -x -v
"""
import pytest
from sqlalchemy import update

from app.models.user import User


async def _make_admin(client, db_session, email, password):
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, f"Re-login failed: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client, registered_user, db_session):
    return await _make_admin(client, db_session, registered_user["email"], registered_user["password"])


def _csv(text: str):
    return {"file": ("data.csv", text.encode("utf-8"), "text/csv")}


@pytest.mark.asyncio
async def test_import_courses_and_rooms_still_work(client, admin_headers):
    r = await client.post(
        "/v1/admin/timetable/import?entity=courses", headers=admin_headers,
        files=_csv("code,name,credits,weekly_classes,is_lab\nSE101,Intro,3,2,false\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 1 and r.json()["errors"] == []

    r = await client.post(
        "/v1/admin/timetable/import?entity=rooms", headers=admin_headers,
        files=_csv("name,room_type,capacity\nKT-504,THEORY,40\n"),
    )
    assert r.json()["created"] == 1, r.json()


@pytest.mark.asyncio
async def test_import_batches(client, admin_headers):
    r = await client.post(
        "/v1/admin/timetable/import?entity=batches", headers=admin_headers,
        files=_csv("name,program\nBatch 50,SWE\nBatch 51,CSE\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 2, r.json()
    names = [b["name"] for b in (await client.get("/v1/admin/timetable/batches", headers=admin_headers)).json()]
    assert "Batch 50" in names and "Batch 51" in names


@pytest.mark.asyncio
async def test_import_faculty_resolves_email(client, admin_headers, registered_user):
    email = registered_user["email"]
    r = await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv(f"email,rank,max_per_day\n{email},PROFESSOR,5\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 1, r.json()
    fac = (await client.get("/v1/admin/timetable/faculty", headers=admin_headers)).json()
    assert len(fac) == 1 and fac[0]["rank"] == "PROFESSOR" and fac[0]["max_per_day"] == 5


@pytest.mark.asyncio
async def test_import_faculty_unknown_email_errors_row(client, admin_headers):
    r = await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv("email,rank,max_per_day\nnobody@example.com,LECTURER,4\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 0
    assert len(r.json()["errors"]) == 1 and "nobody@example.com" in r.json()["errors"][0]


@pytest.mark.asyncio
async def test_import_offerings_requires_term(client, admin_headers):
    term = (await client.post("/v1/admin/timetable/terms", json={"name": "T1"}, headers=admin_headers)).json()["id"]
    await client.post(
        "/v1/admin/timetable/courses",
        json={"code": "SE101", "name": "Intro", "credits": 3, "is_lab": False, "weekly_classes": 2},
        headers=admin_headers,
    )
    await client.post(
        "/v1/admin/timetable/batches", json={"name": "Batch 60", "program": "SWE"}, headers=admin_headers
    )
    csv = "course_code,batch_name\nSE101,Batch 60\n"

    ok = await client.post(
        f"/v1/admin/timetable/import?entity=offerings&term_id={term}", headers=admin_headers, files=_csv(csv)
    )
    assert ok.status_code == 200, ok.json()
    assert ok.json()["created"] == 1, ok.json()

    # Without a term, every offering row fails cleanly rather than 500-ing.
    no_term = await client.post(
        "/v1/admin/timetable/import?entity=offerings", headers=admin_headers, files=_csv(csv)
    )
    assert no_term.json()["created"] == 0 and len(no_term.json()["errors"]) == 1


@pytest.mark.asyncio
async def test_import_eligibility(client, admin_headers, registered_user):
    email = registered_user["email"]
    await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv(f"email,rank,max_per_day\n{email},LECTURER,4\n"),
    )
    await client.post(
        "/v1/admin/timetable/courses",
        json={"code": "SE202", "name": "Data Structures", "credits": 3, "is_lab": False, "weekly_classes": 2},
        headers=admin_headers,
    )
    r = await client.post(
        "/v1/admin/timetable/import?entity=eligibility", headers=admin_headers,
        files=_csv(f"faculty_email,course_code\n{email},SE202\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 1, r.json()


@pytest.mark.asyncio
async def test_import_headers_case_insensitive(client, admin_headers):
    # Upper/mixed-case headers should be normalised.
    r = await client.post(
        "/v1/admin/timetable/import?entity=batches", headers=admin_headers,
        files=_csv("Name,Program\nBatch 70,SWE\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 1, r.json()
