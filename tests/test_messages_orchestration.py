"""Tests for message orchestration logic.

Tests _was_already_messaged, run_messages, message_discussions,
message_from_search from src/actions/messages.py — using a real temp
SQLite DB for DB-dependent checks and mocks for browser/platform.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import src.database as db_mod
from src.database import init_db, get_db
from src.actions.messages import (
    _was_already_messaged, run_messages, message_discussions,
    message_from_search, ALL_MESSAGE_ACTIONS, MIN_SCORE_MESSAGE,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp DB for each test."""
    db_mod.DB_PATH = str(tmp_path / "test.db")
    await init_db()
    yield
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


# ──────────────────────────────────────────────────────
# _was_already_messaged
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_was_already_messaged_false_when_empty():
    result = await _was_already_messaged("wyylde", "NeverContacted")
    assert result is False


@pytest.mark.asyncio
async def test_was_already_messaged_true_for_message_action():
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "message", "Marie", "Salut!")
        )
        await db.commit()
    assert await _was_already_messaged("wyylde", "Marie") is True


@pytest.mark.asyncio
async def test_was_already_messaged_true_for_sidebar_msg():
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "sidebar_msg", "Bob", "Hey!")
        )
        await db.commit()
    assert await _was_already_messaged("wyylde", "Bob") is True


@pytest.mark.asyncio
async def test_was_already_messaged_true_for_search_msg():
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "search_msg", "Alice", "Bonjour!")
        )
        await db.commit()
    assert await _was_already_messaged("wyylde", "Alice") is True


@pytest.mark.asyncio
async def test_was_already_messaged_checks_all_3_action_types():
    """All three action types (message, sidebar_msg, search_msg) are checked."""
    for action in ALL_MESSAGE_ACTIONS:
        # Reset DB between iterations
        async with await get_db() as db:
            await db.execute("DELETE FROM activity_log")
            await db.commit()

        # Should be False before insert
        assert await _was_already_messaged("wyylde", "TestUser") is False

        # Insert one action type
        async with await get_db() as db:
            await db.execute(
                "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
                ("wyylde", action, "TestUser", "msg")
            )
            await db.commit()

        # Should be True after insert
        assert await _was_already_messaged("wyylde", "TestUser") is True, \
            f"Should detect action '{action}' as already messaged"


@pytest.mark.asyncio
async def test_was_already_messaged_false_for_other_actions():
    """Actions like 'like', 'follow', 'reply' should NOT count as already messaged."""
    for action in ("like", "follow", "reply", "auto_reply", "rejected"):
        async with await get_db() as db:
            await db.execute("DELETE FROM activity_log")
            await db.execute(
                "INSERT INTO activity_log (platform, action, target_name) VALUES (?, ?, ?)",
                ("wyylde", action, "TestUser")
            )
            await db.commit()
        assert await _was_already_messaged("wyylde", "TestUser") is False, \
            f"Action '{action}' should NOT count as already messaged"


@pytest.mark.asyncio
async def test_was_already_messaged_cross_platform():
    """Message on wyylde should not block tinder."""
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "message", "CrossUser", "Hi")
        )
        await db.commit()
    assert await _was_already_messaged("wyylde", "CrossUser") is True
    assert await _was_already_messaged("tinder", "CrossUser") is False


# ──────────────────────────────────────────────────────
# run_messages — orchestration
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_messages_no_session():
    with patch("src.actions.messages.browser_sessions", {}):
        result = await run_messages("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_run_messages_rate_limited():
    mock_session = {"platform": MagicMock()}
    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(False, 20, 20)):
        result = await run_messages("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_run_messages_skips_already_messaged():
    """Matches that were already messaged should be skipped."""
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "message", "OldContact", "Previous msg")
        )
        await db.commit()

    mock_platform = AsyncMock()
    mock_platform.get_matches = AsyncMock(return_value=[
        {"name": "OldContact", "id": "123"},
    ])
    mock_session = {"platform": mock_platform}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}):
        result = await run_messages("wyylde")

    assert result == []
    mock_platform.navigate_to_profile.assert_not_called()


@pytest.mark.asyncio
async def test_run_messages_skips_own_pseudo():
    mock_platform = AsyncMock()
    mock_platform.get_matches = AsyncMock(return_value=[
        {"name": "testbot", "id": "1"},
        {"name": "te", "id": "2"},  # first 2 chars of pseudo
    ])
    mock_session = {"platform": mock_platform}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}):
        result = await run_messages("wyylde")

    assert result == []


@pytest.mark.asyncio
async def test_run_messages_skips_low_score():
    """Profiles with score below MIN_SCORE_MESSAGE are skipped."""
    mock_platform = AsyncMock()
    mock_platform.get_matches = AsyncMock(return_value=[
        {"name": "LowScore", "id": "42"},
    ])
    mock_platform.navigate_to_profile = AsyncMock(return_value={
        "name": "LowScore", "type": "Femme", "bio": "test",
    })
    mock_session = {"platform": mock_platform}

    low_score = {"total": 20, "grade": "F", "recommendation": "skip",
                 "suggested_style": "auto", "details": {}}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.messages.score_profile", new_callable=AsyncMock,
               return_value=low_score), \
         patch("src.actions.messages.save_score", new_callable=AsyncMock):
        result = await run_messages("wyylde")

    assert result == []
    mock_platform.send_message_from_profile.assert_not_called()


@pytest.mark.asyncio
async def test_run_messages_successful_send():
    """Full flow: match found, scored, messaged."""
    mock_platform = AsyncMock()
    mock_platform.get_matches = AsyncMock(return_value=[
        {"name": "GoodMatch", "id": "99"},
    ])
    mock_platform.navigate_to_profile = AsyncMock(return_value={
        "name": "GoodMatch", "type": "Couple F Bi", "bio": "On adore voyager",
    })
    mock_platform.send_message_from_profile = AsyncMock(return_value=True)
    mock_session = {"platform": mock_platform}

    good_score = {"total": 75, "grade": "B", "recommendation": "message",
                  "suggested_style": "romantique", "details": {}}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.messages.score_profile", new_callable=AsyncMock,
               return_value=good_score), \
         patch("src.actions.messages.save_score", new_callable=AsyncMock), \
         patch("src.actions.messages.generate_first_message", new_callable=AsyncMock,
               return_value="Salut, votre profil me plait!"), \
         patch("src.actions.messages.increment_daily_count", new_callable=AsyncMock), \
         patch("src.actions.messages._human_delay_with_pauses", new_callable=AsyncMock):
        result = await run_messages("wyylde")

    assert len(result) == 1
    assert result[0]["name"] == "GoodMatch"
    assert result[0]["score"] == 75


# ──────────────────────────────────────────────────────
# message_discussions — orchestration
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_message_discussions_no_session():
    with patch("src.actions.messages.browser_sessions", {}):
        result = await message_discussions("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_message_discussions_rate_limited():
    mock_session = {"platform": MagicMock()}
    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(False, 20, 20)):
        result = await message_discussions("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_message_discussions_skips_already_messaged():
    """Discussions with already-messaged contacts are skipped."""
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "sidebar_msg", "AlreadyDone", "Old msg")
        )
        await db.commit()

    mock_platform = AsyncMock()
    mock_platform._ensure_chat_sidebar_visible = AsyncMock()
    mock_platform._open_discussions_list = AsyncMock()
    # Simulate clicking a discussion that returns AlreadyDone, then no more discussions
    call_count = 0

    async def mock_evaluate(js_code, *args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"clicked": True, "name": "AlreadyDone", "x": 1050, "y": 300}
        return {"clicked": False}

    mock_platform.page = AsyncMock()
    mock_platform.page.evaluate = mock_evaluate
    mock_platform.page.url = "https://app.wyylde.com/fr-fr/dashboard"
    mock_session = {"platform": mock_platform}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.messages.asyncio.sleep", new_callable=AsyncMock):
        result = await message_discussions("wyylde", count=1)

    assert result == []


# ──────────────────────────────────────────────────────
# message_from_search — orchestration
# ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_message_from_search_no_session():
    with patch("src.actions.messages.browser_sessions", {}):
        result = await message_from_search("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_message_from_search_rate_limited():
    mock_session = {"platform": MagicMock()}
    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(False, 20, 20)):
        result = await message_from_search("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_message_from_search_no_results():
    mock_platform = AsyncMock()
    mock_platform.get_search_results = AsyncMock(return_value=[])
    mock_session = {"platform": mock_platform}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}):
        result = await message_from_search("wyylde")

    assert result == []


@pytest.mark.asyncio
async def test_message_from_search_skips_already_messaged():
    """Search results with already-messaged contacts are skipped."""
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "search_msg", "OldSearch", "Previous msg")
        )
        await db.commit()

    mock_platform = AsyncMock()
    mock_platform.get_search_results = AsyncMock(return_value=[
        {"href": "https://app.wyylde.com/fr-fr/member/123"},
    ])
    mock_platform.read_full_profile = AsyncMock(return_value={
        "name": "OldSearch", "type": "Femme", "bio": "test",
    })
    mock_platform.page = AsyncMock()
    mock_platform.page.goto = AsyncMock()
    mock_platform.page.url = "https://app.wyylde.com/fr-fr/member/123"
    mock_platform.page.evaluate = AsyncMock(return_value=False)  # loading check
    mock_session = {"platform": mock_platform}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.messages.asyncio.sleep", new_callable=AsyncMock):
        result = await message_from_search("wyylde")

    assert result == []
    mock_platform.send_message_from_profile.assert_not_called()


@pytest.mark.asyncio
async def test_message_from_search_skips_low_score():
    """Profiles below MIN_SCORE_MESSAGE are skipped in search."""
    mock_platform = AsyncMock()
    mock_platform.get_search_results = AsyncMock(return_value=[
        {"href": "https://app.wyylde.com/fr-fr/member/456"},
    ])
    mock_platform.read_full_profile = AsyncMock(return_value={
        "name": "LowScoreSearch", "type": "Homme", "bio": "test",
    })
    mock_platform.page = AsyncMock()
    mock_platform.page.goto = AsyncMock()
    mock_platform.page.url = "https://app.wyylde.com/fr-fr/member/456"
    mock_platform.page.evaluate = AsyncMock(return_value=False)
    mock_session = {"platform": mock_platform}

    low_score = {"total": 25, "grade": "F", "recommendation": "skip",
                 "suggested_style": "auto", "details": {}}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.messages.score_profile", new_callable=AsyncMock,
               return_value=low_score), \
         patch("src.actions.messages.save_score", new_callable=AsyncMock), \
         patch("src.actions.messages.asyncio.sleep", new_callable=AsyncMock):
        result = await message_from_search("wyylde")

    assert result == []
    mock_platform.send_message_from_profile.assert_not_called()


@pytest.mark.asyncio
async def test_message_from_search_successful():
    """Full search message flow: find, score, send."""
    mock_platform = AsyncMock()
    mock_platform.get_search_results = AsyncMock(return_value=[
        {"href": "https://app.wyylde.com/fr-fr/member/789"},
    ])
    mock_platform.read_full_profile = AsyncMock(return_value={
        "name": "SearchMatch", "type": "Couple F Bi", "bio": "Couple ouvert",
    })
    mock_platform.send_message_from_profile = AsyncMock(return_value=True)
    mock_platform.page = AsyncMock()
    mock_platform.page.goto = AsyncMock()
    mock_platform.page.url = "https://app.wyylde.com/fr-fr/member/789"
    mock_platform.page.evaluate = AsyncMock(return_value=False)
    mock_session = {"platform": mock_platform}

    good_score = {"total": 80, "grade": "B", "recommendation": "message",
                  "suggested_style": "complice", "details": {}}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.messages.score_profile", new_callable=AsyncMock,
               return_value=good_score), \
         patch("src.actions.messages.save_score", new_callable=AsyncMock), \
         patch("src.actions.messages.generate_first_message", new_callable=AsyncMock,
               return_value="Votre profil est inspirant!"), \
         patch("src.actions.messages.increment_daily_count", new_callable=AsyncMock), \
         patch("src.actions.messages._human_delay_with_pauses", new_callable=AsyncMock), \
         patch("src.actions.messages.asyncio.sleep", new_callable=AsyncMock):
        result = await message_from_search("wyylde")

    assert len(result) == 1
    assert result[0]["name"] == "SearchMatch"
    assert result[0]["score"] == 80


@pytest.mark.asyncio
async def test_message_from_search_type_filter():
    """Profiles not matching type filter are skipped."""
    mock_platform = AsyncMock()
    mock_platform.get_search_results = AsyncMock(return_value=[
        {"href": "https://app.wyylde.com/fr-fr/member/111"},
    ])
    mock_platform.read_full_profile = AsyncMock(return_value={
        "name": "WrongType", "type": "Homme", "bio": "test",
    })
    mock_platform.page = AsyncMock()
    mock_platform.page.goto = AsyncMock()
    mock_platform.page.url = "https://app.wyylde.com/fr-fr/member/111"
    mock_platform.page.evaluate = AsyncMock(return_value=False)
    mock_session = {"platform": mock_platform}

    with patch("src.actions.messages.browser_sessions", {"wyylde": mock_session}), \
         patch("src.actions.messages.check_daily_limit", new_callable=AsyncMock,
               return_value=(True, 0, 20)), \
         patch("src.actions.messages.MY_PROFILE", {"pseudo": "testbot"}), \
         patch("src.actions.messages.asyncio.sleep", new_callable=AsyncMock):
        result = await message_from_search("wyylde", profile_type="Couple F Bi")

    assert result == []
    mock_platform.send_message_from_profile.assert_not_called()


# ──────────────────────────────────────────────────────
# Constants verification
# ──────────────────────────────────────────────────────

def test_all_message_actions_tuple():
    assert ALL_MESSAGE_ACTIONS == ('message', 'sidebar_msg', 'search_msg')


def test_min_score_message_is_reasonable():
    assert 20 <= MIN_SCORE_MESSAGE <= 60
