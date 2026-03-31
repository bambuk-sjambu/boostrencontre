"""Tests for conversation history routes (GET /api/conversations/...)."""

import os
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from src.app import app
from src.database import init_db


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


# --- GET /api/conversations/{platform} ---

@pytest.mark.asyncio
async def test_list_conversations_empty(client):
    """List conversations on a fresh DB returns empty list."""
    r = await client.get("/api/conversations/wyylde")
    assert r.status_code == 200
    data = r.json()
    assert "conversations" in data
    assert "count" in data
    assert data["conversations"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_list_conversations_invalid_platform(client):
    """Invalid platform returns 400."""
    r = await client.get("/api/conversations/badplatform")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


@pytest.mark.asyncio
async def test_list_conversations_with_data(client):
    """List conversations returns mocked data."""
    mock_data = [
        {"contact_name": "Alice", "stage": "opening", "last_message": "Hello", "turns": 2},
        {"contact_name": "Bob", "stage": "deepening", "last_message": "Hey", "turns": 5},
    ]
    with patch(
        "src.routes.conversations.list_conversations",
        new_callable=AsyncMock,
        return_value=mock_data,
    ):
        r = await client.get("/api/conversations/wyylde")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    assert data["conversations"][0]["contact_name"] == "Alice"
    assert data["conversations"][1]["contact_name"] == "Bob"


@pytest.mark.asyncio
async def test_list_conversations_all_valid_platforms(client):
    """All valid platforms return 200."""
    for platform in ["tinder", "meetic", "wyylde"]:
        r = await client.get(f"/api/conversations/{platform}")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_conversations_error_returns_500(client):
    """Internal error returns 500."""
    with patch(
        "src.routes.conversations.list_conversations",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db crash"),
    ):
        r = await client.get("/api/conversations/wyylde")
    assert r.status_code == 500
    assert "error" in r.json()


# --- GET /api/conversations/{platform}/{contact_name} ---

@pytest.mark.asyncio
async def test_get_conversation_detail_with_mocked_data(client):
    """Conversation detail returns full structure."""
    mock_messages = [
        {"direction": "sent", "message_text": "Salut!", "stage": "opening"},
        {"direction": "received", "message_text": "Hey!", "stage": "opening"},
    ]
    mock_stage = {
        "stage": "deepening",
        "stage_info": {
            "description": "Approfondir la connexion",
            "prompt_addon": "Pose une question ouverte",
        },
        "sent_count": 3,
        "received_count": 2,
        "total_turns": 5,
    }
    with patch(
        "src.routes.conversations.get_full_conversation",
        new_callable=AsyncMock,
        return_value=mock_messages,
    ), patch(
        "src.routes.conversations.get_conversation_stage",
        new_callable=AsyncMock,
        return_value=mock_stage,
    ):
        r = await client.get("/api/conversations/wyylde/Alice")
    assert r.status_code == 200
    data = r.json()
    assert data["contact_name"] == "Alice"
    assert len(data["messages"]) == 2
    assert data["stage"] == "deepening"
    assert data["sent_count"] == 3
    assert data["received_count"] == 2
    assert data["total_turns"] == 5
    assert "description" in data["stage_info"]
    assert "prompt_addon" in data["stage_info"]


@pytest.mark.asyncio
async def test_get_conversation_invalid_platform(client):
    """Invalid platform returns 400."""
    r = await client.get("/api/conversations/badplatform/Alice")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


@pytest.mark.asyncio
async def test_get_conversation_error_returns_500(client):
    """Internal error returns 500."""
    with patch(
        "src.routes.conversations.get_full_conversation",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db error"),
    ):
        r = await client.get("/api/conversations/wyylde/Alice")
    assert r.status_code == 500
    assert "error" in r.json()


# --- GET /api/conversation-stats/{platform} ---

@pytest.mark.asyncio
async def test_conversation_stats_with_mocked_data(client):
    """Conversation stats returns expected structure."""
    mock_stats = {
        "total_conversations": 10,
        "by_stage": {"opening": 5, "deepening": 3, "closing": 2},
        "avg_turns": 4.2,
        "response_rate": 65.0,
    }
    with patch(
        "src.routes.conversations.get_conversation_stats",
        new_callable=AsyncMock,
        return_value=mock_stats,
    ):
        r = await client.get("/api/conversation-stats/wyylde")
    assert r.status_code == 200
    data = r.json()
    assert data["total_conversations"] == 10
    assert data["by_stage"]["opening"] == 5
    assert data["response_rate"] == 65.0


@pytest.mark.asyncio
async def test_conversation_stats_invalid_platform(client):
    """Invalid platform returns 400."""
    r = await client.get("/api/conversation-stats/badplatform")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


@pytest.mark.asyncio
async def test_conversation_stats_error_returns_500(client):
    """Internal error returns 500."""
    with patch(
        "src.routes.conversations.get_conversation_stats",
        new_callable=AsyncMock,
        side_effect=RuntimeError("stats error"),
    ):
        r = await client.get("/api/conversation-stats/wyylde")
    assert r.status_code == 500
    assert "error" in r.json()


@pytest.mark.asyncio
async def test_conversation_stats_all_valid_platforms(client):
    """All valid platforms return 200."""
    mock_stats = {"total_conversations": 0, "by_stage": {}}
    with patch(
        "src.routes.conversations.get_conversation_stats",
        new_callable=AsyncMock,
        return_value=mock_stats,
    ):
        for platform in ["tinder", "meetic", "wyylde"]:
            r = await client.get(f"/api/conversation-stats/{platform}")
            assert r.status_code == 200
