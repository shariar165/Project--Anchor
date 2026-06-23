"""
Tests for the national-mode FIR/GD drafting feature (/v1/police-reports).

SQLite in-memory + fakeredis — no Docker required. The RAG service is unreachable
in tests, so draft-with-ai exercises the deterministic template fallback.
"""
import uuid
import pytest

PDF_CT = "application/pdf"
DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CSV_CT = "text/csv"
CT = {"pdf": PDF_CT, "docx": DOCX_CT, "csv": CSV_CT}


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _register(client, prefix: str = "user") -> dict:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "GD Tester", "email": email, "password": password,
        "role": "user", "terms": True, "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"email": email, "password": password, "tokens": login.json()}


_FULL = {
    "complainant_name": "Sadia Akter",
    "guardian_name": "Aminul Akter",
    "address": "House 14/B, Sobhanbag, Dhaka",
    "phone": "+8801521000000",
    "subject": "General Diary — phone snatching at Mirpur-10",
    "incident_type": "snatching",
    "incident_datetime": "18 May 2026, 9:30 PM",
    "location": "Mirpur-10 circle, Dhaka",
    "thana": "Mirpur Model Thana",
    "district": "Dhaka",
    "narrative": "My phone was snatched by two men on a motorbike near the central island.",
    "property_details": "Samsung Galaxy A54, IMEI 359xxxx2189",
}


@pytest.mark.asyncio
async def test_create_update_finalize_flow(client, registered_user):
    h = _auth(registered_user["tokens"])

    # create draft
    r = await client.post("/v1/police-reports", json={"report_type": "gd", "language": "en"}, headers=h)
    assert r.status_code == 201, r.json()
    rid = r.json()["id"]
    assert r.json()["state"] == "draft"
    assert r.json()["reference_no"] is None

    # finalize with missing fields -> 400
    r = await client.post(f"/v1/police-reports/{rid}/finalize", headers=h)
    assert r.status_code == 400

    # fill required fields
    r = await client.patch(f"/v1/police-reports/{rid}", json=_FULL, headers=h)
    assert r.status_code == 200, r.json()
    assert r.json()["thana"] == "Mirpur Model Thana"

    # finalize -> reference_no + state
    r = await client.post(f"/v1/police-reports/{rid}/finalize", headers=h)
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["state"] == "finalized"
    assert body["reference_no"].startswith("GD-")

    # cannot edit a finalized report
    r = await client.patch(f"/v1/police-reports/{rid}", json={"subject": "x"}, headers=h)
    assert r.status_code == 409

    # mark filed
    r = await client.post(f"/v1/police-reports/{rid}/mark-filed", headers=h)
    assert r.status_code == 200
    assert r.json()["state"] == "filed_by_user"

    # appears in list
    r = await client.get("/v1/police-reports", headers=h)
    assert r.status_code == 200
    assert any(item["id"] == rid for item in r.json())


@pytest.mark.asyncio
async def test_draft_with_ai_template_fallback(client, registered_user):
    h = _auth(registered_user["tokens"])
    r = await client.post("/v1/police-reports/draft-with-ai", json={
        "report_type": "gd",
        "situation": "Someone snatched my phone at Mirpur-10 in the evening.",
        "language": "en",
        "complainant_name": "Sadia Akter",
        "incident_datetime": "18 May 2026",
        "location": "Mirpur-10",
    }, headers=h)
    assert r.status_code == 200, r.json()
    body = r.json()
    assert len(body["narrative"]) > 40
    assert "Sadia Akter" in body["narrative"]
    # RAG offline in tests -> deterministic template, ai_assisted False
    assert body["ai_assisted"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["pdf", "docx", "csv"])
async def test_export_each_format(client, registered_user, fmt):
    h = _auth(registered_user["tokens"])
    rid = (await client.post("/v1/police-reports", json={"report_type": "fir"}, headers=h)).json()["id"]
    await client.patch(f"/v1/police-reports/{rid}", json=_FULL, headers=h)
    await client.post(f"/v1/police-reports/{rid}/finalize", headers=h)

    r = await client.get(f"/v1/police-reports/{rid}/export?format={fmt}", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(CT[fmt])
    assert "attachment" in r.headers.get("content-disposition", "")
    if fmt == "pdf":
        assert r.content[:4] == b"%PDF"
    elif fmt == "docx":
        assert r.content[:2] == b"PK"
    assert len(r.content) > 0


@pytest.mark.asyncio
async def test_owner_isolation(client, registered_user):
    h1 = _auth(registered_user["tokens"])
    rid = (await client.post("/v1/police-reports", json={"report_type": "gd"}, headers=h1)).json()["id"]

    other = await _register(client, "other")
    h2 = _auth(other["tokens"])
    assert (await client.get(f"/v1/police-reports/{rid}", headers=h2)).status_code == 404
    assert (await client.patch(f"/v1/police-reports/{rid}", json={"subject": "x"}, headers=h2)).status_code == 404


@pytest.mark.asyncio
async def test_requires_auth(client):
    assert (await client.get("/v1/police-reports")).status_code in (401, 403)
    assert (await client.post("/v1/police-reports", json={"report_type": "gd"})).status_code in (401, 403)
