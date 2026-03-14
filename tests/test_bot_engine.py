"""Tests for bot_engine — browser sessions, check_login, save_session, close_browser.

All Playwright and DB calls are mocked to avoid real browser/network usage.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src import bot_engine


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp DB for each test."""
    import os
    import src.database as db_mod
    from src.database import init_db
    db_mod.DB_PATH = str(tmp_path / "test.db")
    await init_db()
    yield
    # Clean up browser_sessions to avoid leaking between tests
    bot_engine.browser_sessions.clear()
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


# --- PLATFORMS registry ---

def test_platforms_registry_has_all():
    assert "tinder" in bot_engine.PLATFORMS
    assert "meetic" in bot_engine.PLATFORMS
    assert "wyylde" in bot_engine.PLATFORMS


def test_platforms_registry_values_are_classes():
    for name, cls in bot_engine.PLATFORMS.items():
        assert callable(cls), f"PLATFORMS['{name}'] should be a class"


# --- check_login ---

@pytest.mark.asyncio
async def test_check_login_no_session():
    """check_login returns False when no browser session exists."""
    result = await bot_engine.check_login("tinder")
    assert result is False


@pytest.mark.asyncio
async def test_check_login_with_session_logged_in():
    """check_login delegates to platform.is_logged_in()."""
    mock_platform = AsyncMock()
    mock_platform.is_logged_in.return_value = True
    bot_engine.browser_sessions["wyylde"] = {
        "pw": MagicMock(),
        "context": MagicMock(),
        "platform": mock_platform,
    }
    result = await bot_engine.check_login("wyylde")
    assert result is True
    mock_platform.is_logged_in.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_login_with_session_not_logged_in():
    mock_platform = AsyncMock()
    mock_platform.is_logged_in.return_value = False
    bot_engine.browser_sessions["meetic"] = {
        "pw": MagicMock(),
        "context": MagicMock(),
        "platform": mock_platform,
    }
    result = await bot_engine.check_login("meetic")
    assert result is False


# --- save_session ---

@pytest.mark.asyncio
async def test_save_session_no_session():
    """save_session does nothing when no session exists."""
    await bot_engine.save_session("tinder")
    # Should not raise


@pytest.mark.asyncio
async def test_save_session_stores_cookies():
    """save_session writes cookies to the accounts table."""
    mock_context = AsyncMock()
    mock_context.cookies.return_value = [{"name": "session", "value": "abc123"}]
    bot_engine.browser_sessions["wyylde"] = {
        "pw": MagicMock(),
        "context": mock_context,
        "platform": AsyncMock(),
    }
    # Insert an account row first
    from src.database import get_db
    async with await get_db() as db:
        await db.execute("INSERT INTO accounts (platform) VALUES (?)", ("wyylde",))
        await db.commit()

    await bot_engine.save_session("wyylde")

    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT session_data, status FROM accounts WHERE platform = 'wyylde'"
        )
        row = await cursor.fetchone()
    assert row is not None
    cookies = json.loads(row[0])
    assert cookies[0]["name"] == "session"
    assert row[1] == "connected"


# --- close_browser ---

@pytest.mark.asyncio
async def test_close_browser_no_session():
    """close_browser on non-existent session should not raise."""
    await bot_engine.close_browser("tinder")


@pytest.mark.asyncio
async def test_close_browser_closes_context():
    mock_context = AsyncMock()
    mock_pw = AsyncMock()
    bot_engine.browser_sessions["tinder"] = {
        "pw": mock_pw,
        "context": mock_context,
        "platform": AsyncMock(),
    }
    # Insert account row
    from src.database import get_db
    async with await get_db() as db:
        await db.execute("INSERT INTO accounts (platform) VALUES (?)", ("tinder",))
        await db.commit()

    await bot_engine.close_browser("tinder")

    assert "tinder" not in bot_engine.browser_sessions
    mock_context.close.assert_awaited_once()
    mock_pw.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_browser_updates_db_status():
    mock_context = AsyncMock()
    mock_pw = AsyncMock()
    bot_engine.browser_sessions["meetic"] = {
        "pw": mock_pw,
        "context": mock_context,
        "platform": AsyncMock(),
    }
    from src.database import get_db
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO accounts (platform, status) VALUES (?, ?)",
            ("meetic", "connected")
        )
        await db.commit()

    await bot_engine.close_browser("meetic")

    async with await get_db() as db:
        cursor = await db.execute("SELECT status FROM accounts WHERE platform = 'meetic'")
        row = await cursor.fetchone()
    assert row[0] == "disconnected"


# --- launch_browser (mocked Playwright) ---

@pytest.mark.asyncio
async def test_launch_browser_already_open():
    """If session already exists, launch_browser returns already_open."""
    bot_engine.browser_sessions["wyylde"] = {"pw": MagicMock(), "context": MagicMock(), "platform": MagicMock()}
    result = await bot_engine.launch_browser("wyylde")
    assert result["status"] == "already_open"


@pytest.mark.asyncio
async def test_launch_browser_unknown_platform():
    """Unknown platform name should return error after closing context."""
    mock_context = AsyncMock()
    mock_pw = AsyncMock()
    mock_pw.chromium.launch_persistent_context.return_value = mock_context

    with patch("src.session_manager.async_playwright") as mock_apw:
        mock_apw_instance = AsyncMock()
        mock_apw_instance.start.return_value = mock_pw
        mock_apw.return_value = mock_apw_instance

        result = await bot_engine.launch_browser("unknown_platform")
    assert result["status"] == "error"
    assert "Unknown platform" in result["message"]


# --- run_likes (mocked) ---

@pytest.mark.asyncio
async def test_run_likes_no_session():
    """run_likes returns empty list when no session."""
    result = await bot_engine.run_likes("tinder")
    assert result == []


@pytest.mark.asyncio
async def test_run_likes_with_session():
    mock_platform = AsyncMock()
    mock_platform.like_profiles.return_value = [
        {"name": "Alice"},
        {"name": "Bob"},
    ]
    # Check if like_profiles accepts profile_filter
    mock_platform.like_profiles.__code__ = MagicMock()
    mock_platform.like_profiles.__code__.co_varnames = ("self", "count", "delay_range")

    bot_engine.browser_sessions["wyylde"] = {
        "pw": MagicMock(),
        "context": MagicMock(),
        "platform": mock_platform,
    }

    result = await bot_engine.run_likes("wyylde")
    assert len(result) == 2
    mock_platform.like_profiles.assert_awaited_once()

    # Check that activity was logged
    from src.database import get_db
    async with await get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM activity_log WHERE action = 'like'")
        count = (await cursor.fetchone())[0]
    assert count == 2


# --- run_messages (mocked) ---

@pytest.mark.asyncio
async def test_run_messages_no_session():
    result = await bot_engine.run_messages("tinder")
    assert result == []


# --- reply_to_inbox ---

@pytest.mark.asyncio
async def test_reply_to_inbox_no_session():
    result = await bot_engine.reply_to_inbox("wyylde")
    assert result == []


# --- PROFILE_DIR ---

def test_profile_dir_uses_home():
    """Browser profiles should be stored under ~/.boostrencontre/."""
    assert ".boostrencontre" in str(bot_engine.PROFILE_DIR)
    assert "browser_profiles" in str(bot_engine.PROFILE_DIR)
