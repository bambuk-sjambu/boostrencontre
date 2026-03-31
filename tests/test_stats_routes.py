"""Tests for stats-related routes: /api/stats, /api/daily-stats, /api/scoring-stats."""

import os
import pytest
from unittest.mock import patch, AsyncMock
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


async def insert_score(platform, name, target_type, score, grade, recommendation="", style="auto"):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO profile_scores "
            "(platform, target_name, target_type, score, grade, recommendation, suggested_style) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (platform, name, target_type, score, grade, recommendation, style),
        )
        await db.commit()


# --- GET /api/stats/{platform} ---

@pytest.mark.asyncio
async def test_stats_returns_expected_keys(client):
    """GET /api/stats/wyylde returns all top-level keys."""
    r = await client.get("/api/stats/wyylde")
    assert r.status_code == 200
    data = r.json()
    for key in ("today", "period", "by_style", "by_day", "recent_conversations"):
        assert key in data


@pytest.mark.asyncio
async def test_stats_today_has_correct_structure(client):
    """today section has messages_sent, replies_sent, likes, follows, crushes."""
    r = await client.get("/api/stats/wyylde")
    today = r.json()["today"]
    for key in ("messages_sent", "replies_sent", "likes", "follows", "crushes"):
        assert key in today
        assert isinstance(today[key], int)


@pytest.mark.asyncio
async def test_stats_period_has_correct_structure(client):
    """period section has messages_sent, replies_received, response_rate."""
    r = await client.get("/api/stats/wyylde")
    period = r.json()["period"]
    assert "messages_sent" in period
    assert "replies_received" in period
    assert "response_rate" in period


@pytest.mark.asyncio
async def test_stats_invalid_platform_returns_400(client):
    """Invalid platform returns 400."""
    r = await client.get("/api/stats/hackme")
    assert r.status_code == 400


# --- GET /api/daily-stats/{platform} ---

@pytest.mark.asyncio
async def test_daily_stats_returns_structure(client):
    """GET /api/daily-stats/wyylde returns stats and date."""
    r = await client.get("/api/daily-stats/wyylde")
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    assert "date" in data
    assert isinstance(data["stats"], dict)


@pytest.mark.asyncio
async def test_daily_stats_has_action_entries(client):
    """Daily stats entries have count, limit, remaining fields."""
    r = await client.get("/api/daily-stats/wyylde")
    data = r.json()
    stats = data["stats"]
    # Should have at least some known actions from DEFAULT_DAILY_LIMITS
    if stats:
        first_key = next(iter(stats))
        entry = stats[first_key]
        assert "count" in entry
        assert "limit" in entry
        assert "remaining" in entry


@pytest.mark.asyncio
async def test_daily_stats_all_platforms(client):
    """All valid platforms return 200."""
    for platform in ["tinder", "meetic", "wyylde"]:
        r = await client.get(f"/api/daily-stats/{platform}")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_daily_stats_counts_zero_on_fresh_db(client):
    """On a fresh DB, all daily counts are 0."""
    r = await client.get("/api/daily-stats/wyylde")
    data = r.json()
    for action, entry in data["stats"].items():
        assert entry["count"] == 0
        assert entry["remaining"] == entry["limit"]


# --- GET /api/scoring-stats/{platform} ---

@pytest.mark.asyncio
async def test_scoring_stats_returns_structure(client):
    """GET /api/scoring-stats/wyylde returns all expected keys."""
    r = await client.get("/api/scoring-stats/wyylde")
    assert r.status_code == 200
    data = r.json()
    for key in ("distribution", "by_type", "top_profiles", "overall"):
        assert key in data


@pytest.mark.asyncio
async def test_scoring_stats_empty_db(client):
    """Scoring stats on empty DB returns empty lists and zero totals."""
    r = await client.get("/api/scoring-stats/wyylde")
    data = r.json()
    assert data["distribution"] == []
    assert data["by_type"] == []
    assert data["top_profiles"] == []
    assert data["overall"]["total"] == 0


@pytest.mark.asyncio
async def test_scoring_stats_with_data(client):
    """Scoring stats returns correct data after inserting scores."""
    await insert_score("wyylde", "Alice", "Femme", 85, "A", "good match", "romantique")
    await insert_score("wyylde", "Bob", "Homme", 60, "B", "ok match", "humoristique")
    await insert_score("wyylde", "Charlie", "Couple", 45, "C", "low match", "auto")

    r = await client.get("/api/scoring-stats/wyylde")
    data = r.json()

    assert data["overall"]["total"] == 3
    assert data["overall"]["max_score"] == 85
    assert data["overall"]["min_score"] == 45

    # Top profiles should be sorted by score desc
    names = [p["target_name"] for p in data["top_profiles"]]
    assert names[0] == "Alice"

    # Distribution should have entries for grades A, B, C
    grades = [d["grade"] for d in data["distribution"]]
    assert "A" in grades
    assert "B" in grades
    assert "C" in grades

    # by_type should have entries
    types = [t["target_type"] for t in data["by_type"]]
    assert "Femme" in types


@pytest.mark.asyncio
async def test_scoring_stats_invalid_platform(client):
    """Invalid platform returns 400."""
    r = await client.get("/api/scoring-stats/hackme")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


@pytest.mark.asyncio
async def test_scoring_stats_isolates_platforms(client):
    """Scores from one platform are not included in another's stats."""
    await insert_score("wyylde", "Alice", "Femme", 90, "A")
    await insert_score("tinder", "Bob", "Homme", 70, "B")

    r = await client.get("/api/scoring-stats/wyylde")
    data = r.json()
    assert data["overall"]["total"] == 1
    assert data["top_profiles"][0]["target_name"] == "Alice"
