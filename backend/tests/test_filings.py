"""
Tests for the Complaint / Report / Grievance filing system.

Uses SQLite in-memory + fakeredis — no Docker required.
Step-up dependency is monkeypatched to get_current_user so tests
don't need to mint separate stepup tokens.
"""
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.filing import Filing, FilingState, FilingTemplate, ClassroomReport
from app.deps import get_current_user, require_stepup
from app.main import app as _app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _bypass_stepup():
    """Allow tests to call step-up-gated endpoints with a regular access token."""
    _app.dependency_overrides[require_stepup] = get_current_user
    yield
    _app.dependency_overrides.pop(require_stepup, None)


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed(db_session):
    """Seed filing templates so tests don't depend on app startup."""
    from app.services.filing_svc import seed_templates
    await seed_templates(db_session)


# ── Template tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_templates(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.get("/v1/filings/templates", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 200
    templates = r.json()
    assert len(templates) == 10
    keys = {t["key"] for t in templates}
    assert "academic_rank1" in keys
    assert "academic_rank3" in keys
    assert "warden_misconduct" in keys


@pytest.mark.asyncio
async def test_get_template_by_key(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.get("/v1/filings/templates/academic_rank3", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 200
    t = r.json()
    assert t["key"] == "academic_rank3"
    assert t["anonymity_mode"] == "anonymous"
    assert t["requires_stepup"] is True


@pytest.mark.asyncio
async def test_get_template_not_found(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.get("/v1/filings/templates/nonexistent", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 404


# ── Filing CRUD ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_get_filing(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    assert r.status_code == 201
    filing = r.json()
    assert filing["state"] == "draft"
    assert filing["category"] == "complaint"
    assert filing["filing_number"] is None

    r2 = await client.get(f"/v1/filings/{filing['id']}", headers=_auth(registered_user["tokens"]))
    assert r2.status_code == 200
    assert r2.json()["id"] == filing["id"]


@pytest.mark.asyncio
async def test_update_filing_body(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "dept_c1", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]

    patch = await client.patch(f"/v1/filings/{fid}",
                               json={"body": "The projector in room 301 has been broken since May 2026."},
                               headers=_auth(registered_user["tokens"]))
    assert patch.status_code == 200
    assert "projector" in patch.json()["body"]


@pytest.mark.asyncio
async def test_list_filings(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    for key in ("academic_rank1", "dept_c1"):
        await client.post("/v1/filings", json={"template_key": key, "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    r = await client.get("/v1/filings", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_delete_draft_filing(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    d = await client.delete(f"/v1/filings/{fid}", headers=_auth(registered_user["tokens"]))
    assert d.status_code == 204
    r2 = await client.get(f"/v1/filings/{fid}", headers=_auth(registered_user["tokens"]))
    assert r2.status_code == 404


# ── Submission ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_attributed_filing(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank2", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    await client.patch(f"/v1/filings/{fid}",
                       json={"body": "On 15 May 2026, Professor X made inappropriate remarks during lecture."},
                       headers=_auth(registered_user["tokens"]))

    sub = await client.post(f"/v1/filings/{fid}/submit", headers=_auth(registered_user["tokens"]))
    assert sub.status_code == 200
    data = sub.json()
    assert data["state"] == "routed"
    assert data["filing_number"].startswith("DIU-CMP-")
    assert data["anonymous_tracking_code"] is None


@pytest.mark.asyncio
async def test_submit_anonymous_filing(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank3", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    await client.patch(f"/v1/filings/{fid}",
                       json={"body": "I am experiencing a pattern of threatening behavior from an instructor."},
                       headers=_auth(registered_user["tokens"]))

    sub = await client.post(f"/v1/filings/{fid}/submit", headers=_auth(registered_user["tokens"]))
    assert sub.status_code == 200
    data = sub.json()
    # Anonymous template routes to moderation queue first
    assert data["state"] == "moderation_queue"
    assert data["anonymous_tracking_code"] is not None
    assert len(data["anonymous_tracking_code"]) == 12

    # Verify the DB record has no complainant_user_id
    import uuid as _uuid
    result = await db_session.execute(select(Filing).where(Filing.id == _uuid.UUID(fid)))
    db_filing = result.scalars().first()
    assert db_filing.complainant_user_id is None
    assert db_filing.encrypted_actor_link is not None


@pytest.mark.asyncio
async def test_anonymous_lookup(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "dept_c3", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    await client.patch(f"/v1/filings/{fid}",
                       json={"body": "The department atmosphere has become hostile to junior students."},
                       headers=_auth(registered_user["tokens"]))
    sub = await client.post(f"/v1/filings/{fid}/submit", headers=_auth(registered_user["tokens"]))
    tracking_code = sub.json()["anonymous_tracking_code"]

    # Lookup without auth
    lookup = await client.post("/v1/filings/anonymous-lookup", json={"tracking_code": tracking_code})
    assert lookup.status_code == 200
    data = lookup.json()
    assert data["filing_number"].startswith("DIU-GRV-")
    assert "state" in data
    assert "complainant" not in str(data).lower()


@pytest.mark.asyncio
async def test_anonymous_lookup_wrong_code(client, db_session, mock_redis):
    lookup = await client.post("/v1/filings/anonymous-lookup", json={"tracking_code": "WRONGCODE123"})
    assert lookup.status_code == 404


# ── Withdrawal ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_withdraw_before_review(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    await client.patch(f"/v1/filings/{fid}", json={"body": "Some feedback on the course."}, headers=_auth(registered_user["tokens"]))
    await client.post(f"/v1/filings/{fid}/submit", headers=_auth(registered_user["tokens"]))

    wd = await client.post(f"/v1/filings/{fid}/withdraw", headers=_auth(registered_user["tokens"]))
    assert wd.status_code == 200
    assert wd.json()["state"] == "withdrawn"


@pytest.mark.asyncio
async def test_cannot_withdraw_after_review(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    await client.patch(f"/v1/filings/{fid}", json={"body": "Feedback text here."}, headers=_auth(registered_user["tokens"]))
    await client.post(f"/v1/filings/{fid}/submit", headers=_auth(registered_user["tokens"]))

    # Manually add a review record so withdrawal is blocked
    from app.models.filing import FilingReview
    import uuid as _uuid
    review = FilingReview(
        filing_id=_uuid.UUID(fid),
        reviewer_role="dept_head",
        action="route",
    )
    db_session.add(review)
    await db_session.commit()

    wd = await client.post(f"/v1/filings/{fid}/withdraw", headers=_auth(registered_user["tokens"]))
    assert wd.status_code == 409


# ── Filing number counter ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filing_number_counter_increments(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    for _ in range(3):
        r = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                              headers=_auth(registered_user["tokens"]))
        fid = r.json()["id"]
        await client.patch(f"/v1/filings/{fid}", json={"body": "Some complaint text."}, headers=_auth(registered_user["tokens"]))
        await client.post(f"/v1/filings/{fid}/submit", headers=_auth(registered_user["tokens"]))

    r_list = await client.get("/v1/filings?state=routed", headers=_auth(registered_user["tokens"]))
    numbers = [f["filing_number"] for f in r_list.json()]
    assert "DIU-CMP-2026-00001" in numbers
    assert "DIU-CMP-2026-00002" in numbers
    assert "DIU-CMP-2026-00003" in numbers


# ── Classroom reports ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_classroom_report_first_submission(client, db_session, mock_redis, registered_user):
    r = await client.post("/v1/classroom-reports",
                          json={"classroom_ref": "AB-301", "issue_type": "projector", "notes": "Projector dead since May."},
                          headers=_auth(registered_user["tokens"]))
    assert r.status_code == 201
    assert r.json()["classroom_ref"] == "AB-301"


@pytest.mark.asyncio
async def test_classroom_report_duplicate_rejected(client, db_session, mock_redis, registered_user):
    payload = {"classroom_ref": "AB-302", "issue_type": "ac"}
    r1 = await client.post("/v1/classroom-reports", json=payload, headers=_auth(registered_user["tokens"]))
    assert r1.status_code == 201
    r2 = await client.post("/v1/classroom-reports", json=payload, headers=_auth(registered_user["tokens"]))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_classroom_report_aggregation(client, db_session, mock_redis, registered_user):
    # Two different users report same classroom / issue
    for _ in range(2):
        import uuid as _uuid
        from app.models.user import User, Role, AccountStatus
        from app.models.filing import ClassroomReport
        u = User(full_name="Student", email=f"s{_uuid.uuid4().hex[:6]}@test.com",
                 password_hash="x", role=Role.user, status=AccountStatus.active)
        db_session.add(u)
        await db_session.commit()
        cr = ClassroomReport(classroom_ref="AB-303", issue_type="lighting", reporter_user_id=u.id)
        db_session.add(cr)
        await db_session.commit()

    r = await client.get("/v1/classroom-reports?classroom_ref=AB-303", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 200
    rows = r.json()
    assert any(row["count"] == 2 and row["issue_type"] == "lighting" for row in rows)


# ── Timeline ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_after_submit(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    await client.patch(f"/v1/filings/{fid}", json={"body": "Feedback text."}, headers=_auth(registered_user["tokens"]))
    await client.post(f"/v1/filings/{fid}/submit", headers=_auth(registered_user["tokens"]))

    tl = await client.get(f"/v1/filings/{fid}/timeline", headers=_auth(registered_user["tokens"]))
    assert tl.status_code == 200
    entries = tl.json()["entries"]
    assert any(e["event"] == "submitted" for e in entries)


# ── AI draft stub ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_draft_returns_501(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    r = await client.post("/v1/filings", json={"template_key": "academic_rank2", "language": "en"},
                          headers=_auth(registered_user["tokens"]))
    fid = r.json()["id"]
    dr = await client.post(f"/v1/filings/{fid}/draft-with-ai", headers=_auth(registered_user["tokens"]))
    assert dr.status_code == 501
