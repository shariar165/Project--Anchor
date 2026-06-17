import pytest

from app.models.legal_right import LegalRight
from app.services.legal_rights_svc import seed_legal_rights, LEGAL_RIGHTS_CORPUS


def _mk(**over):
    base = dict(
        category="personal_safety",
        title_en="A right",
        summary_en="summary",
        full_text_en="full text",
        citation="Penal Code 1860 · §509",
        steps=[],
        illustration="shield",
        accent="#C44536",
        sort_order=0,
        published=True,
    )
    base.update(over)
    return LegalRight(**base)


@pytest.mark.anyio
async def test_list_legal_rights_empty(client, db_session, mock_redis):
    resp = await client.get("/v1/legal-rights")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_legal_rights_ordered_by_sort_order(client, db_session, mock_redis):
    db_session.add_all([
        _mk(title_en="Second", sort_order=20),
        _mk(title_en="First", sort_order=10),
    ])
    await db_session.commit()

    resp = await client.get("/v1/legal-rights")
    assert resp.status_code == 200
    items = resp.json()
    assert [i["title_en"] for i in items] == ["First", "Second"]


@pytest.mark.anyio
async def test_list_legal_rights_category_filter(client, db_session, mock_redis):
    db_session.add_all([
        _mk(title_en="Cyber one", category="cyber"),
        _mk(title_en="Safety one", category="personal_safety"),
    ])
    await db_session.commit()

    resp = await client.get("/v1/legal-rights?category=cyber")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["category"] == "cyber"


@pytest.mark.anyio
async def test_list_legal_rights_hides_unpublished(client, db_session, mock_redis):
    db_session.add_all([
        _mk(title_en="Visible", published=True),
        _mk(title_en="Hidden", published=False),
    ])
    await db_session.commit()

    resp = await client.get("/v1/legal-rights")
    assert resp.status_code == 200
    titles = [i["title_en"] for i in resp.json()]
    assert "Visible" in titles
    assert "Hidden" not in titles


@pytest.mark.anyio
async def test_seed_is_idempotent(client, db_session, mock_redis):
    n1 = await seed_legal_rights(db_session)
    assert n1 == len(LEGAL_RIGHTS_CORPUS)

    n2 = await seed_legal_rights(db_session)
    assert n2 == 0

    resp = await client.get("/v1/legal-rights")
    assert resp.status_code == 200
    assert len(resp.json()) == len(LEGAL_RIGHTS_CORPUS)
    # bilingual payload present
    first = resp.json()[0]
    assert "title_bn" in first and "steps" in first and "illustration" in first
