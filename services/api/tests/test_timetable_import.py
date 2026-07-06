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
async def test_import_faculty_without_account_creates_standalone(client, admin_headers):
    # Faculty are standalone: an email with no user account still imports.
    r = await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv("email,name,rank,max_per_day\njc@diu.edu.bd,Dr. Jane,PROFESSOR,4\nmes@diu.edu.bd,,LECTURER,3\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 2 and r.json()["errors"] == [], r.json()
    fac = (await client.get("/v1/admin/timetable/faculty", headers=admin_headers)).json()
    by_email = {f["email"]: f for f in fac}
    assert by_email["jc@diu.edu.bd"]["user_id"] is None
    assert by_email["jc@diu.edu.bd"]["name"] == "Dr. Jane"
    assert by_email["mes@diu.edu.bd"]["name"] == "mes"          # falls back to email prefix
    assert by_email["mes@diu.edu.bd"]["rank"] == "LECTURER"


@pytest.mark.asyncio
async def test_import_faculty_links_account_when_present(client, admin_headers, registered_user):
    # When a user with that email exists, the faculty links to it.
    email = registered_user["email"]
    r = await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv(f"email,name,rank,max_per_day\n{email},,LECTURER,4\n"),
    )
    assert r.json()["created"] == 1, r.json()
    fac = (await client.get("/v1/admin/timetable/faculty", headers=admin_headers)).json()
    assert fac[0]["user_id"] is not None and fac[0]["email"] == email.lower()


@pytest.mark.asyncio
async def test_import_faculty_duplicate_email_updates_not_appends(client, admin_headers):
    # A repeated email upserts the existing profile instead of erroring or
    # (worse) appending a second row.
    r = await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv("email,rank,max_per_day\ndup@diu.edu.bd,LECTURER,4\ndup@diu.edu.bd,PROFESSOR,5\n"),
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["created"] == 1 and body["updated"] == 1 and body["error_count"] == 0, body
    fac = (await client.get("/v1/admin/timetable/faculty", headers=admin_headers)).json()
    assert len(fac) == 1, "duplicate email must not create a second faculty row"
    assert fac[0]["rank"] == "PROFESSOR" and fac[0]["max_per_day"] == 5  # last row wins


@pytest.mark.asyncio
async def test_reimporting_same_file_is_idempotent(client, admin_headers):
    """The H-1 regression test: importing the same file twice must not grow
    any table — courses/rooms/batches/faculty update, offerings/eligibility skip."""
    courses_csv = "code,name,credits,weekly_classes,is_lab\nSE900,Testing,3,2,false\nSE901,QA Lab,1,1,true\n"
    rooms_csv = "name,room_type,capacity\nRE-901,THEORY,40\nRE-902,LAB,30\n"
    batches_csv = "name,program\nBatch 90,SWE\n"
    faculty_csv = "email,rank,max_per_day\nrepeat@diu.edu.bd,LECTURER,4\n"

    for entity, csv_text in [
        ("courses", courses_csv), ("rooms", rooms_csv),
        ("batches", batches_csv), ("faculty", faculty_csv),
    ]:
        first = await client.post(
            f"/v1/admin/timetable/import?entity={entity}", headers=admin_headers,
            files=_csv(csv_text),
        )
        assert first.json()["error_count"] == 0, (entity, first.json())
        n_created = first.json()["created"]
        second = await client.post(
            f"/v1/admin/timetable/import?entity={entity}", headers=admin_headers,
            files=_csv(csv_text),
        )
        body = second.json()
        assert body["created"] == 0, (entity, body)
        assert body["updated"] == n_created, (entity, body)
        assert body["error_count"] == 0, (entity, body)

    # Row counts stayed stable
    assert len((await client.get("/v1/admin/timetable/courses", headers=admin_headers)).json()) == 2
    assert len((await client.get("/v1/admin/timetable/rooms", headers=admin_headers)).json()) == 2
    assert len((await client.get("/v1/admin/timetable/batches", headers=admin_headers)).json()) == 1
    assert len((await client.get("/v1/admin/timetable/faculty", headers=admin_headers)).json()) == 1

    # Relational entities: re-import skips instead of duplicating
    term = (await client.post("/v1/admin/timetable/terms", json={"name": "Idem"}, headers=admin_headers)).json()["id"]
    off_csv = "course_code,batch_name\nSE900,Batch 90\n"
    first = await client.post(
        f"/v1/admin/timetable/import?entity=offerings&term_id={term}", headers=admin_headers, files=_csv(off_csv),
    )
    assert first.json()["created"] == 1, first.json()
    second = await client.post(
        f"/v1/admin/timetable/import?entity=offerings&term_id={term}", headers=admin_headers, files=_csv(off_csv),
    )
    assert second.json()["created"] == 0 and second.json()["skipped"] == 1, second.json()

    elig_csv = "faculty_email,course_code\nrepeat@diu.edu.bd,SE900\n"
    first = await client.post(
        "/v1/admin/timetable/import?entity=eligibility", headers=admin_headers, files=_csv(elig_csv),
    )
    assert first.json()["created"] == 1, first.json()
    second = await client.post(
        "/v1/admin/timetable/import?entity=eligibility", headers=admin_headers, files=_csv(elig_csv),
    )
    assert second.json()["created"] == 0 and second.json()["skipped"] == 1, second.json()


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
async def test_import_eligibility_resolves_faculty_without_account(client, admin_headers):
    # Faculty imported without a login account; eligibility still resolves by email.
    await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv("email,rank,max_per_day\nnoacct@diu.edu.bd,LECTURER,4\n"),
    )
    await client.post(
        "/v1/admin/timetable/courses",
        json={"code": "SE303", "name": "OS", "credits": 3, "is_lab": False, "weekly_classes": 2},
        headers=admin_headers,
    )
    r = await client.post(
        "/v1/admin/timetable/import?entity=eligibility", headers=admin_headers,
        files=_csv("faculty_email,course_code\nnoacct@diu.edu.bd,SE303\n"),
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


@pytest.mark.asyncio
async def test_import_semicolon_delimited_csv(client, admin_headers):
    # Excel in some locales exports ';'-separated CSV — must still import.
    r = await client.post(
        "/v1/admin/timetable/import?entity=courses", headers=admin_headers,
        files=_csv("code;name;credits;weekly_classes;is_lab\nSE301;Networks;3;2;false\nSE302;OS;3;2;false\n"),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 2 and r.json()["errors"] == [], r.json()


@pytest.mark.asyncio
async def test_import_missing_columns_reported_once(client, admin_headers):
    # Wrong headers on a standalone entity → one clear message, not one per row.
    r = await client.post(
        "/v1/admin/timetable/import?entity=courses", headers=admin_headers,
        files=_csv("courseid,title\nSE1,Intro\nSE2,Data\nSE3,Algo\n"),
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["created"] == 0
    assert len(body["errors"]) == 1
    assert "Missing required column" in body["errors"][0]
    assert "code" in body["errors"][0] and "name" in body["errors"][0]


@pytest.mark.asyncio
async def test_import_missing_columns_dependency_entity(client, admin_headers):
    # Same single-message behaviour for a dependency entity (faculty needs 'email').
    r = await client.post(
        "/v1/admin/timetable/import?entity=faculty", headers=admin_headers,
        files=_csv("name,rank\nSomeone,LECTURER\n"),
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["created"] == 0 and len(body["errors"]) == 1
    assert "Missing required column" in body["errors"][0] and "email" in body["errors"][0]


@pytest.mark.asyncio
async def test_import_skips_blank_rows(client, admin_headers):
    # A trailing all-empty row must not be counted as an error.
    r = await client.post(
        "/v1/admin/timetable/import?entity=courses", headers=admin_headers,
        files=_csv("code,name,credits,weekly_classes,is_lab\nSE400,Intro,3,2,false\n,,,,\n"),
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["created"] == 1 and body["errors"] == [] and body["total"] == 1, body


@pytest.mark.asyncio
async def test_import_bad_row_does_not_cascade(client, admin_headers):
    # A bad row in the middle must not abort the valid rows around it.
    csv = (
        "code,name,credits,weekly_classes,is_lab\n"
        "SE501,Intro,3,2,false\n"
        "SE502,,3,2,false\n"        # missing name → row error
        "SE503,Advanced,3,2,false\n"
    )
    r = await client.post(
        "/v1/admin/timetable/import?entity=courses", headers=admin_headers, files=_csv(csv),
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["created"] == 2, body
    assert body["error_count"] == 1 and len(body["errors"]) == 1, body
    codes = [c["code"] for c in (await client.get("/v1/admin/timetable/courses", headers=admin_headers)).json()]
    assert "SE501" in codes and "SE503" in codes


@pytest.mark.asyncio
async def test_import_response_has_total_and_error_count(client, admin_headers):
    r = await client.post(
        "/v1/admin/timetable/import?entity=rooms", headers=admin_headers,
        files=_csv("name,room_type,capacity\nKT-601,THEORY,40\nKT-602,LAB,30\n"),
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["created"] == 2 and body["total"] == 2 and body["error_count"] == 0, body
