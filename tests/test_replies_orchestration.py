"""Tests for reply orchestration logic.

Tests _replied_recently, _is_rejected, _log_reply, _log_rejection
from replies_helpers.py, and reply_to_inbox / reply_to_sidebar from
replies_inbox.py — using a real temp SQLite DB.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import src.database as db_mod
from src.database import init_db, get_db
from src.actions.replies_helpers import (
    _replied_recently, _is_rejected, _log_reply, _log_rejection,
    _get_last_sent_message,
)
from src.actions.replies_inbox import reply_to_inbox, reply_to_sidebar


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp DB for each test."""
    db_mod.DB_PATH = str(tmp_path / "test.db")
    await init_db()
    yield
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


# ──────────────────────────────────────────────────────
# _log_reply
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_reply_inserts_row():
    await _log_reply("wyylde", "Marie", "Salut Marie!", action="reply", style="romantique")
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT platform, action, target_name, message_sent, style FROM activity_log"
        )
        row = await cursor.fetchone()
    assert row == ("wyylde", "reply", "Marie", "Salut Marie!", "romantique")


@pytest.mark.asyncio
async def test_log_reply_default_action():
    await _log_reply("wyylde", "Bob", "Hey!")
    async with await get_db() as db:
        cursor = await db.execute("SELECT action FROM activity_log")
        row = await cursor.fetchone()
    assert row[0] == "sidebar_reply"


@pytest.mark.asyncio
async def test_log_reply_default_style():
    await _log_reply("wyylde", "Alice", "Bonjour")
    async with await get_db() as db:
        cursor = await db.execute("SELECT style FROM activity_log")
        row = await cursor.fetchone()
    assert row[0] == "auto"


# ──────────────────────────────────────────────────────
# _log_rejection + _is_rejected
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_is_rejected_false_by_default():
    result = await _is_rejected("wyylde", "UnknownUser")
    assert result is False


@pytest.mark.asyncio
async def test_log_rejection_then_is_rejected():
    await _log_rejection("wyylde", "Angry99")
    result = await _is_rejected("wyylde", "Angry99")
    assert result is True


@pytest.mark.asyncio
async def test_is_rejected_cross_platform_independent():
    """Rejection on wyylde should not affect tinder."""
    await _log_rejection("wyylde", "Marie")
    assert await _is_rejected("wyylde", "Marie") is True
    assert await _is_rejected("tinder", "Marie") is False


# ──────────────────────────────────────────────────────
# _replied_recently
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replied_recently_false_when_no_replies():
    result = await _replied_recently("wyylde", "Someone")
    assert result is False


@pytest.mark.asyncio
async def test_replied_recently_true_after_log_reply():
    await _log_reply("wyylde", "Marie", "Test reply", action="auto_reply")
    result = await _replied_recently("wyylde", "Marie")
    assert result is True


@pytest.mark.asyncio
async def test_replied_recently_false_for_old_entries():
    """Entries older than the window should not count.
    We insert a row with a manually backdated timestamp."""
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now', '-10 minutes'))",
            ("wyylde", "auto_reply", "OldFriend", "Hi")
        )
        await db.commit()
    result = await _replied_recently("wyylde", "OldFriend", minutes=3)
    assert result is False


@pytest.mark.asyncio
async def test_replied_recently_different_actions():
    """Only auto_reply, sidebar_reply, reply count as recent replies."""
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) "
            "VALUES (?, ?, ?, ?)",
            ("wyylde", "message", "Alice", "First msg")
        )
        await db.commit()
    # 'message' action should NOT count as recent reply
    result = await _replied_recently("wyylde", "Alice")
    assert result is False


# ──────────────────────────────────────────────────────
# _get_last_sent_message
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_last_sent_message_empty():
    result = await _get_last_sent_message("wyylde", "Nobody")
    assert result == ""


@pytest.mark.asyncio
async def test_get_last_sent_message_returns_latest():
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "message", "Marie", "First message")
        )
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "reply", "Marie", "Second message")
        )
        await db.commit()
    result = await _get_last_sent_message("wyylde", "Marie")
    assert result == "Second message"


# ──────────────────────────────────────────────────────
# reply_to_inbox — orchestration
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reply_to_inbox_no_session():
    """Returns empty list when no browser session exists."""
    with patch("src.actions.replies_inbox.browser_sessions", {}):
        result = await reply_to_inbox("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_reply_to_inbox_rate_limited():
    """Returns empty list when daily limit is reached."""
    mock_session = {"platform": MagicMock()}
    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(False, 30, 30)):
        result = await reply_to_inbox("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_reply_to_inbox_skips_already_replied():
    """Conversations already replied to are skipped."""
    # Pre-insert a reply in DB
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "reply", "AlreadyReplied", "Old reply")
        )
        await db.commit()

    mock_platform = AsyncMock()
    mock_platform.get_inbox_conversations = AsyncMock(return_value=[
        {"text": "AlreadyReplied\nSome message content here"},
    ])
    mock_session = {"platform": mock_platform}

    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 30)), \
         patch("src.actions.replies_inbox.MY_PROFILE", {"pseudo": "testbot"}):
        result = await reply_to_inbox("wyylde")

    assert result == []
    # open_chat_and_read should NOT have been called
    mock_platform.open_chat_and_read.assert_not_called()


@pytest.mark.asyncio
async def test_reply_to_inbox_skips_own_pseudo():
    """Conversations where sender is our own pseudo are skipped."""
    mock_platform = AsyncMock()
    mock_platform.get_inbox_conversations = AsyncMock(return_value=[
        {"text": "testbot\nSome text"},
    ])
    mock_session = {"platform": mock_platform}

    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 30)), \
         patch("src.actions.replies_inbox.MY_PROFILE", {"pseudo": "testbot"}):
        result = await reply_to_inbox("wyylde")

    assert result == []


@pytest.mark.asyncio
async def test_reply_to_inbox_successful_reply():
    """Full flow: conversation found, AI generates reply, platform sends it."""
    mock_platform = AsyncMock()
    mock_platform.get_inbox_conversations = AsyncMock(return_value=[
        {"text": "Marie\nSalut ca va ?"},
    ])
    mock_platform.open_chat_and_read = AsyncMock(return_value={
        "fullText": "Salut, ton profil est sympa!",
        "hasMessages": True,
    })
    mock_platform.reply_in_chat = AsyncMock(return_value=True)
    mock_session = {"platform": mock_platform}

    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 30)), \
         patch("src.actions.replies_inbox.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.replies_inbox.generate_reply_message", new_callable=AsyncMock,
               return_value="Merci Marie, enchanté!"), \
         patch("src.actions.replies_inbox.filter_ui_text", return_value=["Salut, ton profil est sympa!"]), \
         patch("src.actions.replies_inbox.record_conv_message", new_callable=AsyncMock), \
         patch("src.actions.replies_inbox.increment_daily_count", new_callable=AsyncMock), \
         patch("src.actions.replies_inbox._human_delay_with_pauses", new_callable=AsyncMock):
        result = await reply_to_inbox("wyylde")

    assert len(result) == 1
    assert result[0]["name"] == "Marie"
    assert result[0]["reply"] == "Merci Marie, enchanté!"


# ──────────────────────────────────────────────────────
# reply_to_sidebar — orchestration
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reply_to_sidebar_no_session():
    with patch("src.actions.replies_inbox.browser_sessions", {}):
        result = await reply_to_sidebar("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_reply_to_sidebar_rate_limited():
    mock_session = {"platform": MagicMock()}
    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(False, 30, 30)):
        result = await reply_to_sidebar("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_reply_to_sidebar_skips_already_replied():
    """Sidebar conversations already replied to (reply or sidebar_reply) are skipped."""
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "sidebar_reply", "SidebarUser", "Already replied")
        )
        await db.commit()

    mock_platform = AsyncMock()
    mock_platform.get_sidebar_conversations = AsyncMock(return_value=[
        {"name": "SidebarUser"},
    ])
    mock_session = {"platform": mock_platform}

    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 30)), \
         patch("src.actions.replies_inbox.MY_PROFILE", {"pseudo": "testbot"}):
        result = await reply_to_sidebar("wyylde")

    assert result == []
    mock_platform.open_sidebar_chat.assert_not_called()


@pytest.mark.asyncio
async def test_reply_to_sidebar_skips_blocked():
    """Sidebar conversations blocked by message filters are skipped."""
    mock_platform = AsyncMock()
    mock_platform.get_sidebar_conversations = AsyncMock(return_value=[
        {"name": "BlockedUser"},
    ])
    mock_platform.open_sidebar_chat = AsyncMock(return_value={
        "blocked": True,
        "hasMessages": True,
        "fullText": "Some text",
    })
    mock_session = {"platform": mock_platform}

    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 30)), \
         patch("src.actions.replies_inbox.MY_PROFILE", {"pseudo": "testbot"}):
        result = await reply_to_sidebar("wyylde")

    assert result == []


@pytest.mark.asyncio
async def test_reply_to_sidebar_successful():
    """Full sidebar reply flow."""
    mock_platform = AsyncMock()
    mock_platform.get_sidebar_conversations = AsyncMock(return_value=[
        {"name": "CoolCouple"},
    ])
    mock_platform.open_sidebar_chat = AsyncMock(return_value={
        "blocked": False,
        "hasMessages": True,
        "fullText": "Coucou, votre profil est top!",
    })
    mock_platform.reply_in_sidebar_chat = AsyncMock(return_value=True)
    mock_session = {"platform": mock_platform}

    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 30)), \
         patch("src.actions.replies_inbox.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.replies_inbox.generate_reply_message", new_callable=AsyncMock,
               return_value="Merci, vous aussi!"), \
         patch("src.actions.replies_inbox.filter_ui_text", return_value=["Coucou, votre profil est top!"]), \
         patch("src.actions.replies_inbox.record_conv_message", new_callable=AsyncMock), \
         patch("src.actions.replies_inbox.increment_daily_count", new_callable=AsyncMock), \
         patch("src.actions.replies_inbox._human_delay_with_pauses", new_callable=AsyncMock):
        result = await reply_to_sidebar("wyylde")

    assert len(result) == 1
    assert result[0]["name"] == "CoolCouple"
    assert result[0]["reply"] == "Merci, vous aussi!"


@pytest.mark.asyncio
async def test_reply_to_sidebar_skips_only_our_messages():
    """When chat only contains our messages (our pseudo in text, not theirs), skip."""
    mock_platform = AsyncMock()
    mock_platform.get_sidebar_conversations = AsyncMock(return_value=[
        {"name": "SilentUser"},
    ])
    mock_platform.open_sidebar_chat = AsyncMock(return_value={
        "blocked": False,
        "hasMessages": True,
        "fullText": "testbot said something\ntestbot said another thing",
    })
    mock_session = {"platform": mock_platform}

    with patch("src.actions.replies_inbox.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.replies_inbox.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 30)), \
         patch("src.actions.replies_inbox.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.replies_inbox.filter_ui_text", return_value=["testbot said something"]):
        result = await reply_to_sidebar("wyylde")

    assert result == []
