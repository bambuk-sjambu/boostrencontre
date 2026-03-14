import pytest
import os
from httpx import AsyncClient, ASGITransport
from src.app import app
from src.database import init_db, get_db


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Use a temp DB for each test. Disable auth middleware for tests."""
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


# --- Helpers ---

async def insert_activity(platform, action, target, message=None, style="auto"):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent, style) "
            "VALUES (?, ?, ?, ?, ?)",
            (platform, action, target, message, style),
        )
        await db.commit()


# --- Tests ---

@pytest.mark.asyncio
async def test_stats_returns_structure(client):
    """GET /api/stats/wyylde returns expected keys."""
    r = await client.get("/api/stats/wyylde")
    assert r.status_code == 200
    data = r.json()
    assert "today" in data
    assert "period" in data
    assert "by_style" in data
    assert "by_day" in data
    assert "recent_conversations" in data


@pytest.mark.asyncio
async def test_stats_empty_returns_zeros(client):
    """Stats with no data returns zero counts."""
    r = await client.get("/api/stats/wyylde")
    data = r.json()
    assert data["today"]["messages_sent"] == 0
    assert data["today"]["replies_sent"] == 0
    assert data["today"]["likes"] == 0
    assert data["today"]["follows"] == 0
    assert data["today"]["crushes"] == 0
    assert data["period"]["messages_sent"] == 0
    assert data["period"]["replies_received"] == 0
    assert data["period"]["response_rate"] == 0.0
    assert data["by_style"] == []
    assert len(data["by_day"]) == 7


@pytest.mark.asyncio
async def test_stats_today_counts(client):
    """Today's counts are computed correctly."""
    await insert_activity("wyylde", "message", "Alice", "Hello", "romantique")
    await insert_activity("wyylde", "message", "Bob", "Hi", "romantique")
    await insert_activity("wyylde", "sidebar_reply", "Alice", "Reply", "romantique")
    await insert_activity("wyylde", "like", "Charlie")
    await insert_activity("wyylde", "like", "Dave")
    await insert_activity("wyylde", "like", "Eve")

    r = await client.get("/api/stats/wyylde")
    data = r.json()
    assert data["today"]["messages_sent"] == 2
    assert data["today"]["replies_sent"] == 1
    assert data["today"]["likes"] == 3


@pytest.mark.asyncio
async def test_stats_by_style(client):
    """by_style returns correct counts per style."""
    await insert_activity("wyylde", "message", "Alice", "Hello", "romantique")
    await insert_activity("wyylde", "message", "Bob", "Hey", "romantique")
    await insert_activity("wyylde", "message", "Charlie", "Yo", "humoristique")
    # Alice replied (a reply action exists for Alice after her message)
    await insert_activity("wyylde", "sidebar_reply", "Alice", "She replied", "romantique")

    r = await client.get("/api/stats/wyylde")
    data = r.json()
    styles = {s["style"]: s for s in data["by_style"]}
    assert "romantique" in styles
    assert styles["romantique"]["sent"] == 2
    assert styles["romantique"]["responses"] == 1
    assert styles["romantique"]["rate"] == 50.0
    assert "humoristique" in styles
    assert styles["humoristique"]["sent"] == 1


@pytest.mark.asyncio
async def test_stats_by_day_returns_7_days(client):
    """by_day always returns 7 entries."""
    r = await client.get("/api/stats/wyylde")
    data = r.json()
    assert len(data["by_day"]) == 7


@pytest.mark.asyncio
async def test_stats_by_day_custom_period(client):
    """days parameter controls the number of days returned."""
    r = await client.get("/api/stats/wyylde?days=3")
    data = r.json()
    assert len(data["by_day"]) == 3


@pytest.mark.asyncio
async def test_stats_recent_conversations(client):
    """recent_conversations returns latest conversations."""
    await insert_activity("wyylde", "message", "Alice", "Hello Alice", "auto")
    await insert_activity("wyylde", "message", "Bob", "Hello Bob", "auto")

    r = await client.get("/api/stats/wyylde")
    data = r.json()
    names = [c["name"] for c in data["recent_conversations"]]
    assert "Alice" in names
    assert "Bob" in names


@pytest.mark.asyncio
async def test_stats_recent_conversations_replied_flag(client):
    """replied flag is true when a reply exists for a target."""
    await insert_activity("wyylde", "message", "Alice", "Hello", "auto")
    await insert_activity("wyylde", "sidebar_reply", "Alice", "Reply", "auto")

    r = await client.get("/api/stats/wyylde")
    data = r.json()
    alice = next(c for c in data["recent_conversations"] if c["name"] == "Alice")
    assert alice["replied"] is True


@pytest.mark.asyncio
async def test_stats_invalid_platform(client):
    """Invalid platform returns 400."""
    r = await client.get("/api/stats/badplatform")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


@pytest.mark.asyncio
async def test_stats_isolates_platforms(client):
    """Stats for one platform don't include another's data."""
    await insert_activity("wyylde", "message", "Alice", "Hello", "auto")
    await insert_activity("tinder", "message", "Bob", "Hey", "auto")

    r = await client.get("/api/stats/wyylde")
    data = r.json()
    assert data["today"]["messages_sent"] == 1

    r2 = await client.get("/api/stats/tinder")
    data2 = r2.json()
    assert data2["today"]["messages_sent"] == 1
