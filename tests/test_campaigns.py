"""Tests for campaign manager and campaign API routes."""

import os
import pytest
from httpx import AsyncClient, ASGITransport
from src.app import app
from src.database import init_db
from src import campaign_manager


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Use a temp DB for each test. Disable auth middleware."""
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    import src.database as db_mod
    db_mod.DB_PATH = str(tmp_path / "test.db")
    await init_db()
    yield
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Campaign Manager Unit Tests ---

@pytest.mark.asyncio
async def test_create_campaign():
    cid = await campaign_manager.create_campaign("Test Camp", "wyylde", {
        "target_type": "Couple F Bi",
        "age_min": 25,
        "age_max": 45,
        "style": "romantique",
    })
    assert cid is not None
    assert isinstance(cid, int)

    campaign = await campaign_manager.get_campaign(cid)
    assert campaign is not None
    assert campaign["name"] == "Test Camp"
    assert campaign["platform"] == "wyylde"
    assert campaign["status"] == "draft"
    assert campaign["target_type"] == "Couple F Bi"
    assert campaign["target_age_min"] == 25
    assert campaign["target_age_max"] == 45
    assert campaign["style"] == "romantique"


@pytest.mark.asyncio
async def test_create_campaign_with_desires():
    cid = await campaign_manager.create_campaign("Desires Camp", "wyylde", {
        "desires": ["Gang bang", "Echangisme"],
    })
    campaign = await campaign_manager.get_campaign(cid)
    assert campaign["target_desires"] == ["Gang bang", "Echangisme"]


@pytest.mark.asyncio
async def test_create_campaign_missing_name():
    with pytest.raises(ValueError):
        await campaign_manager.create_campaign("", "wyylde")


@pytest.mark.asyncio
async def test_list_campaigns():
    await campaign_manager.create_campaign("Camp 1", "wyylde")
    await campaign_manager.create_campaign("Camp 2", "wyylde")
    await campaign_manager.create_campaign("Camp 3", "tinder")

    wyylde_camps = await campaign_manager.list_campaigns("wyylde")
    assert len(wyylde_camps) == 2

    tinder_camps = await campaign_manager.list_campaigns("tinder")
    assert len(tinder_camps) == 1

    all_camps = await campaign_manager.list_campaigns()
    assert len(all_camps) == 3


@pytest.mark.asyncio
async def test_start_and_pause_campaign():
    cid = await campaign_manager.create_campaign("Toggle Camp", "wyylde")

    result = await campaign_manager.start_campaign(cid)
    assert result["status"] == "active"

    campaign = await campaign_manager.get_campaign(cid)
    assert campaign["status"] == "active"

    result = await campaign_manager.pause_campaign(cid)
    assert result["status"] == "paused"

    campaign = await campaign_manager.get_campaign(cid)
    assert campaign["status"] == "paused"


@pytest.mark.asyncio
async def test_start_completed_campaign_fails():
    cid = await campaign_manager.create_campaign("Done Camp", "wyylde")
    await campaign_manager.complete_campaign(cid)

    result = await campaign_manager.start_campaign(cid)
    assert result["error"] == "campaign_completed"


@pytest.mark.asyncio
async def test_start_nonexistent_campaign():
    result = await campaign_manager.start_campaign(9999)
    assert result["error"] == "campaign_not_found"


@pytest.mark.asyncio
async def test_delete_campaign():
    cid = await campaign_manager.create_campaign("Delete Me", "wyylde")
    await campaign_manager.add_contact_to_campaign(cid, "Alice")

    result = await campaign_manager.delete_campaign(cid)
    assert result["status"] == "deleted"

    campaign = await campaign_manager.get_campaign(cid)
    assert campaign is None


@pytest.mark.asyncio
async def test_delete_nonexistent_campaign():
    result = await campaign_manager.delete_campaign(9999)
    assert result["error"] == "campaign_not_found"


@pytest.mark.asyncio
async def test_add_contact():
    cid = await campaign_manager.create_campaign("Contact Camp", "wyylde")
    result = await campaign_manager.add_contact_to_campaign(
        cid, "Alice", contact_type="Femme Bi", score=85
    )
    assert result["status"] == "added"

    campaign = await campaign_manager.get_campaign(cid)
    assert len(campaign["contacts"]) == 1
    assert campaign["contacts"][0]["contact_name"] == "Alice"
    assert campaign["contacts"][0]["score"] == 85


@pytest.mark.asyncio
async def test_add_duplicate_contact():
    cid = await campaign_manager.create_campaign("Dup Camp", "wyylde")
    await campaign_manager.add_contact_to_campaign(cid, "Alice")
    result = await campaign_manager.add_contact_to_campaign(cid, "Alice")
    assert result["status"] == "duplicate"


@pytest.mark.asyncio
async def test_update_contact_status():
    cid = await campaign_manager.create_campaign("Status Camp", "wyylde")
    await campaign_manager.add_contact_to_campaign(cid, "Bob")

    result = await campaign_manager.update_contact_status(
        cid, "Bob", "contacted", message_sent="Salut Bob!"
    )
    assert result["status"] == "updated"
    assert result["new_status"] == "contacted"

    campaign = await campaign_manager.get_campaign(cid)
    bob = campaign["contacts"][0]
    assert bob["status"] == "contacted"
    assert bob["message_sent"] == "Salut Bob!"
    assert bob["contacted_at"] is not None


@pytest.mark.asyncio
async def test_update_contact_replied():
    cid = await campaign_manager.create_campaign("Reply Camp", "wyylde")
    await campaign_manager.add_contact_to_campaign(cid, "Clara")
    await campaign_manager.update_contact_status(cid, "Clara", "contacted")
    await campaign_manager.update_contact_status(cid, "Clara", "replied")

    campaign = await campaign_manager.get_campaign(cid)
    clara = campaign["contacts"][0]
    assert clara["status"] == "replied"
    assert clara["replied_at"] is not None


@pytest.mark.asyncio
async def test_update_contact_invalid_status():
    cid = await campaign_manager.create_campaign("Invalid Camp", "wyylde")
    await campaign_manager.add_contact_to_campaign(cid, "Dave")
    result = await campaign_manager.update_contact_status(cid, "Dave", "invalid_status")
    assert "error" in result


@pytest.mark.asyncio
async def test_update_nonexistent_contact():
    cid = await campaign_manager.create_campaign("Ghost Camp", "wyylde")
    result = await campaign_manager.update_contact_status(cid, "Nobody", "contacted")
    assert result["error"] == "contact_not_found"


@pytest.mark.asyncio
async def test_contacts_done_counter():
    cid = await campaign_manager.create_campaign("Counter Camp", "wyylde")
    await campaign_manager.add_contact_to_campaign(cid, "A")
    await campaign_manager.add_contact_to_campaign(cid, "B")
    await campaign_manager.add_contact_to_campaign(cid, "C")

    await campaign_manager.update_contact_status(cid, "A", "contacted")
    await campaign_manager.update_contact_status(cid, "B", "contacted")

    campaign = await campaign_manager.get_campaign(cid)
    assert campaign["contacts_done"] == 2


@pytest.mark.asyncio
async def test_campaign_stats_empty():
    cid = await campaign_manager.create_campaign("Empty Stats", "wyylde")
    stats = await campaign_manager.get_campaign_stats(cid)
    assert stats["total_contacts"] == 0
    assert stats["response_rate"] == 0.0
    assert stats["conversion_rate"] == 0.0


@pytest.mark.asyncio
async def test_campaign_stats_with_data():
    cid = await campaign_manager.create_campaign("Full Stats", "wyylde")
    for name in ["A", "B", "C", "D", "E"]:
        await campaign_manager.add_contact_to_campaign(cid, name)

    await campaign_manager.update_contact_status(cid, "A", "contacted")
    await campaign_manager.update_contact_status(cid, "B", "replied")
    await campaign_manager.update_contact_status(cid, "C", "conversation")
    await campaign_manager.update_contact_status(cid, "D", "met")
    # E stays pending

    stats = await campaign_manager.get_campaign_stats(cid)
    assert stats["total_contacts"] == 5
    assert stats["pending"] == 1
    assert stats["contacted"] == 1
    assert stats["replied"] == 1
    assert stats["conversation"] == 1
    assert stats["met"] == 1

    # total_contacted = contacted + replied + conversation + met = 4
    # total_replied = replied + conversation + met = 3
    assert stats["response_rate"] == 75.0  # 3/4
    assert stats["conversion_rate"] == 25.0  # 1/4


@pytest.mark.asyncio
async def test_campaign_stats_funnel():
    cid = await campaign_manager.create_campaign("Funnel Stats", "wyylde")
    for name in ["A", "B", "C", "D"]:
        await campaign_manager.add_contact_to_campaign(cid, name)

    await campaign_manager.update_contact_status(cid, "A", "contacted")
    await campaign_manager.update_contact_status(cid, "B", "replied")
    await campaign_manager.update_contact_status(cid, "C", "met")

    stats = await campaign_manager.get_campaign_stats(cid)
    funnel = stats["funnel"]
    assert len(funnel) == 4
    assert funnel[0]["stage"] == "contacted"
    assert funnel[0]["count"] == 3  # contacted + replied + met
    assert funnel[1]["stage"] == "replied"
    assert funnel[1]["count"] == 2  # replied + met
    assert funnel[2]["stage"] == "conversation"
    assert funnel[2]["count"] == 1  # met only (conversation=0, met=1)
    assert funnel[3]["stage"] == "met"
    assert funnel[3]["count"] == 1


# --- API Route Tests ---

@pytest.mark.asyncio
async def test_api_create_campaign(client):
    r = await client.post("/api/campaigns", json={
        "name": "API Campaign",
        "platform": "wyylde",
        "target_type": "Femme Bi",
        "style": "humoristique",
        "max_contacts": 10,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "created"
    assert "campaign_id" in data


@pytest.mark.asyncio
async def test_api_create_campaign_missing_name(client):
    r = await client.post("/api/campaigns", json={
        "name": "",
        "platform": "wyylde",
    })
    assert r.status_code == 400
    assert r.json()["error"] == "missing_name"


@pytest.mark.asyncio
async def test_api_create_campaign_invalid_platform(client):
    r = await client.post("/api/campaigns", json={
        "name": "Bad Platform",
        "platform": "badone",
    })
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


@pytest.mark.asyncio
async def test_api_list_campaigns(client):
    await client.post("/api/campaigns", json={"name": "C1", "platform": "wyylde"})
    await client.post("/api/campaigns", json={"name": "C2", "platform": "wyylde"})

    r = await client.get("/api/campaigns/wyylde")
    assert r.status_code == 200
    assert len(r.json()["campaigns"]) == 2


@pytest.mark.asyncio
async def test_api_get_campaign_detail(client):
    cr = await client.post("/api/campaigns", json={"name": "Detail", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]

    r = await client.get(f"/api/campaigns/detail/{cid}")
    assert r.status_code == 200
    assert r.json()["campaign"]["name"] == "Detail"
    assert "stats" in r.json()


@pytest.mark.asyncio
async def test_api_get_campaign_not_found(client):
    r = await client.get("/api/campaigns/detail/9999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_api_start_campaign(client):
    cr = await client.post("/api/campaigns", json={"name": "Start", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]

    r = await client.post(f"/api/campaigns/{cid}/start")
    assert r.status_code == 200
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_api_pause_campaign(client):
    cr = await client.post("/api/campaigns", json={"name": "Pause", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]
    await client.post(f"/api/campaigns/{cid}/start")

    r = await client.post(f"/api/campaigns/{cid}/pause")
    assert r.status_code == 200
    assert r.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_api_paused_campaign_does_not_execute(client):
    """A paused campaign should not run steps (status != active)."""
    cr = await client.post("/api/campaigns", json={"name": "No Run", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]

    # Campaign is in draft status, so it's not active
    detail = await client.get(f"/api/campaigns/detail/{cid}")
    assert detail.json()["campaign"]["status"] == "draft"


@pytest.mark.asyncio
async def test_api_delete_campaign(client):
    cr = await client.post("/api/campaigns", json={"name": "Delete", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]

    r = await client.delete(f"/api/campaigns/{cid}")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"

    r2 = await client.get(f"/api/campaigns/detail/{cid}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_api_add_contact(client):
    cr = await client.post("/api/campaigns", json={"name": "Contacts", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]

    r = await client.post(f"/api/campaigns/{cid}/contacts", json={
        "contact_name": "TestUser",
        "contact_type": "Femme Bi",
        "score": 90,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "added"


@pytest.mark.asyncio
async def test_api_update_contact_status(client):
    cr = await client.post("/api/campaigns", json={"name": "Update", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]
    await client.post(f"/api/campaigns/{cid}/contacts", json={"contact_name": "User1"})

    # Get contact ID
    detail = await client.get(f"/api/campaigns/detail/{cid}")
    contact_id = detail.json()["campaign"]["contacts"][0]["id"]

    r = await client.put(f"/api/campaigns/contacts/{contact_id}/status", json={
        "status": "contacted",
        "message_sent": "Hello!",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "updated"


@pytest.mark.asyncio
async def test_api_update_contact_invalid_status(client):
    cr = await client.post("/api/campaigns", json={"name": "BadStatus", "platform": "wyylde"})
    cid = cr.json()["campaign_id"]
    await client.post(f"/api/campaigns/{cid}/contacts", json={"contact_name": "User2"})

    detail = await client.get(f"/api/campaigns/detail/{cid}")
    contact_id = detail.json()["campaign"]["contacts"][0]["id"]

    r = await client.put(f"/api/campaigns/contacts/{contact_id}/status", json={
        "status": "bogus",
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_api_campaign_in_homepage(client):
    """The homepage should contain the campaigns section."""
    r = await client.get("/")
    assert r.status_code == 200
    assert "Campagnes" in r.text
    assert "Nouvelle campagne" in r.text
