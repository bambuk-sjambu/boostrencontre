import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.session_manager import browser_sessions, check_login, close_browser, PLATFORMS


# ─── browser_sessions ───

def test_browser_sessions_is_dict():
    assert isinstance(browser_sessions, dict)


def test_platforms_registry_has_all():
    assert "tinder" in PLATFORMS
    assert "meetic" in PLATFORMS
    assert "wyylde" in PLATFORMS


def test_platforms_registry_has_three():
    assert len(PLATFORMS) == 3


# ─── check_login ───

@pytest.mark.asyncio
async def test_check_login_no_session():
    """check_login should return False when no session exists."""
    # Make sure no session for this platform
    browser_sessions.pop("test_platform", None)
    result = await check_login("test_platform")
    assert result is False


@pytest.mark.asyncio
async def test_check_login_with_session():
    """check_login should delegate to platform.is_logged_in() when session exists."""
    mock_platform = AsyncMock()
    mock_platform.is_logged_in = AsyncMock(return_value=True)
    browser_sessions["test_check"] = {
        "pw": MagicMock(),
        "context": MagicMock(),
        "platform": mock_platform,
    }
    try:
        result = await check_login("test_check")
        assert result is True
        mock_platform.is_logged_in.assert_called_once()
    finally:
        browser_sessions.pop("test_check", None)


@pytest.mark.asyncio
async def test_check_login_with_session_not_logged_in():
    """check_login should return False when platform says not logged in."""
    mock_platform = AsyncMock()
    mock_platform.is_logged_in = AsyncMock(return_value=False)
    browser_sessions["test_nologin"] = {
        "pw": MagicMock(),
        "context": MagicMock(),
        "platform": mock_platform,
    }
    try:
        result = await check_login("test_nologin")
        assert result is False
    finally:
        browser_sessions.pop("test_nologin", None)


# ─── close_browser ───

@pytest.mark.asyncio
async def test_close_browser_no_session(tmp_path, monkeypatch):
    """close_browser should not raise when no session exists."""
    import src.database as db_mod
    db_mod.DB_PATH = str(tmp_path / "test_close.db")
    from src.database import init_db
    await init_db()

    # Patch stop_auto_reply to avoid side effects
    with patch("src.actions.auto_reply.stop_auto_reply"):
        await close_browser("nonexistent_platform")
    # Should reach here without error


@pytest.mark.asyncio
async def test_close_browser_with_session(tmp_path, monkeypatch):
    """close_browser should close context, stop pw, and remove session."""
    import src.database as db_mod
    db_mod.DB_PATH = str(tmp_path / "test_close2.db")
    from src.database import init_db
    await init_db()

    mock_context = AsyncMock()
    mock_pw = AsyncMock()
    browser_sessions["test_close"] = {
        "pw": mock_pw,
        "context": mock_context,
        "platform": MagicMock(),
    }

    with patch("src.actions.auto_reply.stop_auto_reply"):
        await close_browser("test_close")

    assert "test_close" not in browser_sessions
    mock_context.close.assert_called_once()
    mock_pw.stop.assert_called_once()
