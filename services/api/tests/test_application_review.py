"""
Tests for the Apply-Formally approval chain and the admin application queue.

Covers the full stage routing (mentor/department_head -> dean -> accounts) with
the money-related gate, stage-ownership enforcement on /review, and the
/v1/admin/applications queue + stats.

SQLite in-memory + fakeredis — no Docker required. Migrations don't run on the
SQLite path, so application templates are inserted directly.
"""
import uuid
import pytest
from sqlalchemy import select, update

from app.models.user import User, Role
from app.models.application import ApplicationTemplate


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _register(client, role_hint: str = "user") -> dict:
    email = f"{role_hint}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": f"{role_hint.title()} User",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200
    return {"email": email, "password": password, "tokens": login.json()}


async def _make_staff(client, db_session, role: str = "admin",
                      staff_position: str | None = None) -> dict:
    """Register a user, promote to admin/moderator with a staff_position, relogin."""
    acct = await _register(client, role)
    await db_session.execute(
        update(User).where(User.email == acct["email"]).values(
            role=Role(role), staff_position=staff_position
        )
    )
    await db_session.commit()
    login = await client.post("/auth/login", json={
        "identifier": acct["email"], "password": acct["password"]
    })
    acct["tokens"] = login.json()
    row = (await db_session.execute(
        select(User).where(User.email == acct["email"])
    )).scalars().first()
    acct["id"] = row.id
    return acct


async def _make_template(db_session, key: str, requires_accounts: bool) -> ApplicationTemplate:
    tmpl = ApplicationTemplate(
        key=key,
        name=f"Template {key}",
        name_bn="",
        skill_reference="generic",
        requires_accounts_approval=requires_accounts,
    )
    db_session.add(tmpl)
    await db_session.commit()
    await db_session.refresh(tmpl)
    return tmpl


async def _create_and_submit(client, db_session, student, template,
                             first_approver_choice, mentor_id=None):
    # Create draft
    r = await client.post("/v1/applications", json={
        "template_id": str(template.id),
        "field_values": {"reason": "test"},
        "language": "en",
    }, headers=_auth(student["tokens"]))
    assert r.status_code == 201, r.json()
    app_id = r.json()["id"]

    if first_approver_choice == "mentor":
        assert mentor_id is not None
        pr = await client.patch("/v1/students/me/campus-settings",
                                json={"mentor_user_id": str(mentor_id)},
                                headers=_auth(student["tokens"]))
        assert pr.status_code == 200, pr.json()

    sr = await client.post(f"/v1/applications/{app_id}/submit",
                           json={"first_approver_choice": first_approver_choice},
                           headers=_auth(student["tokens"]))
    assert sr.status_code == 200, sr.json()
    return app_id


@pytest.fixture(autouse=True)
def _no_pdf(monkeypatch):
    """Avoid the real-DB PDF background task firing during final approval."""
    async def _noop(application_id):
        return None
    monkeypatch.setattr("app.services.application_svc._generate_pdf_background", _noop)


# ── Money path: mentor -> dean -> accounts -> approved ────────────────────────

@pytest.mark.asyncio
async def test_money_application_full_chain(client, db_session, mock_redis):
    student = await _register(client)
    mentor = await _make_staff(client, db_session, "admin", staff_position="mentor")
    dean = await _make_staff(client, db_session, "admin", staff_position="dean")
    accounts = await _make_staff(client, db_session, "admin", staff_position="accounts")
    tmpl = await _make_template(db_session, "fee-test", requires_accounts=True)

    app_id = await _create_and_submit(client, db_session, student, tmpl,
                                      "mentor", mentor_id=mentor["id"])

    # Mentor approves -> dean
    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(mentor["tokens"]))
    assert r.status_code == 200, r.json()
    assert r.json()["current_approver_level"] == "dean"
    assert r.json()["state"] == "in_review"

    # Dean approves -> accounts (because money-related)
    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(dean["tokens"]))
    assert r.status_code == 200, r.json()
    assert r.json()["current_approver_level"] == "accounts"

    # Accounts approves -> final approved
    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(accounts["tokens"]))
    assert r.status_code == 200, r.json()
    assert r.json()["state"] == "approved"
    assert r.json()["approved_at"] is not None


# ── Non-money path: dept_head -> dean -> approved (no accounts) ────────────────

@pytest.mark.asyncio
async def test_nonmoney_application_skips_accounts(client, db_session, mock_redis):
    student = await _register(client)
    dept_head = await _make_staff(client, db_session, "admin", staff_position="department_head")
    dean = await _make_staff(client, db_session, "admin", staff_position="dean")
    tmpl = await _make_template(db_session, "leave-test", requires_accounts=False)

    app_id = await _create_and_submit(client, db_session, student, tmpl, "department_head")

    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(dept_head["tokens"]))
    assert r.status_code == 200, r.json()
    assert r.json()["current_approver_level"] == "dean"

    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(dean["tokens"]))
    assert r.status_code == 200, r.json()
    assert r.json()["state"] == "approved"


# ── Reject + changes_requested/resubmit ───────────────────────────────────────

@pytest.mark.asyncio
async def test_dean_reject(client, db_session, mock_redis):
    student = await _register(client)
    dept_head = await _make_staff(client, db_session, "admin", staff_position="department_head")
    tmpl = await _make_template(db_session, "leave-rej", requires_accounts=False)
    app_id = await _create_and_submit(client, db_session, student, tmpl, "department_head")

    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "rejected", "notes": "Insufficient"},
                          headers=_auth(dept_head["tokens"]))
    assert r.status_code == 200
    assert r.json()["state"] == "rejected"
    assert r.json()["rejected_at"] is not None


@pytest.mark.asyncio
async def test_changes_requested_then_resubmit(client, db_session, mock_redis):
    student = await _register(client)
    dept_head = await _make_staff(client, db_session, "admin", staff_position="department_head")
    tmpl = await _make_template(db_session, "leave-chg", requires_accounts=False)
    app_id = await _create_and_submit(client, db_session, student, tmpl, "department_head")

    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "changes_requested", "notes": "Add proof"},
                          headers=_auth(dept_head["tokens"]))
    assert r.status_code == 200
    assert r.json()["state"] == "changes_requested"

    r = await client.post(f"/v1/applications/{app_id}/resubmit",
                          headers=_auth(student["tokens"]))
    assert r.status_code == 200
    assert r.json()["state"] == "in_review"
    assert r.json()["round_count"] == 2


# ── Enforcement ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wrong_position_forbidden(client, db_session, mock_redis):
    student = await _register(client)
    dept_head = await _make_staff(client, db_session, "admin", staff_position="department_head")
    accounts = await _make_staff(client, db_session, "admin", staff_position="accounts")
    tmpl = await _make_template(db_session, "leave-enf", requires_accounts=False)
    app_id = await _create_and_submit(client, db_session, student, tmpl, "department_head")

    # accounts officer cannot act at the department_head stage
    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(accounts["tokens"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_unassigned_mentor_forbidden(client, db_session, mock_redis):
    student = await _register(client)
    mentor = await _make_staff(client, db_session, "admin", staff_position="mentor")
    other = await _make_staff(client, db_session, "admin", staff_position="mentor")
    tmpl = await _make_template(db_session, "fee-enf", requires_accounts=True)
    app_id = await _create_and_submit(client, db_session, student, tmpl,
                                      "mentor", mentor_id=mentor["id"])

    # A different mentor (not the assigned one) cannot act
    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(other["tokens"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_review(client, db_session, mock_redis):
    student = await _register(client)
    dept_head = await _make_staff(client, db_session, "admin", staff_position="department_head")
    plain = await _register(client)
    tmpl = await _make_template(db_session, "leave-nonadmin", requires_accounts=False)
    app_id = await _create_and_submit(client, db_session, student, tmpl, "department_head")

    r = await client.post(f"/v1/applications/{app_id}/review",
                          json={"decision": "approved"}, headers=_auth(plain["tokens"]))
    assert r.status_code == 403


# ── Admin queue + stats ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_queue_scope_mine(client, db_session, mock_redis):
    student = await _register(client)
    dept_head = await _make_staff(client, db_session, "admin", staff_position="department_head")
    dean = await _make_staff(client, db_session, "admin", staff_position="dean")
    tmpl = await _make_template(db_session, "leave-queue", requires_accounts=False)
    app_id = await _create_and_submit(client, db_session, student, tmpl, "department_head")

    # dept_head sees it in their queue; dean does not (yet)
    r = await client.get("/v1/admin/applications?scope=mine", headers=_auth(dept_head["tokens"]))
    assert r.status_code == 200
    assert any(row["id"] == app_id for row in r.json())

    r = await client.get("/v1/admin/applications?scope=mine", headers=_auth(dean["tokens"]))
    assert r.status_code == 200
    assert all(row["id"] != app_id for row in r.json())

    # advance to dean stage; now dean's queue has it
    await client.post(f"/v1/applications/{app_id}/review",
                      json={"decision": "approved"}, headers=_auth(dept_head["tokens"]))
    r = await client.get("/v1/admin/applications?scope=mine", headers=_auth(dean["tokens"]))
    assert any(row["id"] == app_id for row in r.json())


@pytest.mark.asyncio
async def test_super_admin_sets_staff_position(client, db_session, mock_redis):
    sa = await _make_staff(client, db_session, "super_admin")
    admin = await _make_staff(client, db_session, "admin")

    # Assign a valid position
    r = await client.patch(f"/v1/admin/users/{admin['id']}/position",
                           json={"staff_position": "dean"}, headers=_auth(sa["tokens"]))
    assert r.status_code == 200, r.json()
    assert r.json()["staff_position"] == "dean"

    # Invalid position rejected
    r = await client.patch(f"/v1/admin/users/{admin['id']}/position",
                           json={"staff_position": "principal"}, headers=_auth(sa["tokens"]))
    assert r.status_code == 400

    # Clearing the position is allowed
    r = await client.patch(f"/v1/admin/users/{admin['id']}/position",
                           json={"staff_position": None}, headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    assert r.json()["staff_position"] is None


@pytest.mark.asyncio
async def test_admin_stats(client, db_session, mock_redis):
    student = await _register(client)
    dept_head = await _make_staff(client, db_session, "admin", staff_position="department_head")
    tmpl = await _make_template(db_session, "leave-stats", requires_accounts=False)
    await _create_and_submit(client, db_session, student, tmpl, "department_head")

    r = await client.get("/v1/admin/applications/stats", headers=_auth(dept_head["tokens"]))
    assert r.status_code == 200
    assert r.json()["department_head"] >= 1
