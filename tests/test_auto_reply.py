"""Tests for auto_reply module (start, stop, loop)."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# --- start_auto_reply ---

@pytest.mark.asyncio
async def test_start_auto_reply_creates_task():
    """start_auto_reply creates an asyncio task and stores it."""
    from src.actions import auto_reply

    # Reset state
    auto_reply._monitoring_tasks.clear()

    with patch.object(auto_reply, "_auto_reply_loop", new_callable=AsyncMock) as mock_loop:
        # create_task needs a real coroutine
        mock_loop.return_value = None
        auto_reply.start_auto_reply("wyylde", style="romantique", interval=30)

        assert "wyylde" in auto_reply._monitoring_tasks
        task = auto_reply._monitoring_tasks["wyylde"]
        assert isinstance(task, asyncio.Task)

        # Cleanup
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        auto_reply._monitoring_tasks.clear()


@pytest.mark.asyncio
async def test_start_auto_reply_already_running_guard():
    """start_auto_reply does nothing when already running for same platform."""
    from src.actions import auto_reply

    auto_reply._monitoring_tasks.clear()

    with patch.object(auto_reply, "_auto_reply_loop", new_callable=AsyncMock) as mock_loop:
        mock_loop.return_value = None
        auto_reply.start_auto_reply("wyylde")
        first_task = auto_reply._monitoring_tasks["wyylde"]

        # Call again — should keep the same task
        auto_reply.start_auto_reply("wyylde")
        assert auto_reply._monitoring_tasks["wyylde"] is first_task

        # Cleanup
        first_task.cancel()
        try:
            await first_task
        except (asyncio.CancelledError, Exception):
            pass
        auto_reply._monitoring_tasks.clear()


@pytest.mark.asyncio
async def test_start_auto_reply_multiple_platforms():
    """start_auto_reply can run on different platforms simultaneously."""
    from src.actions import auto_reply

    auto_reply._monitoring_tasks.clear()

    with patch.object(auto_reply, "_auto_reply_loop", new_callable=AsyncMock) as mock_loop:
        mock_loop.return_value = None
        auto_reply.start_auto_reply("wyylde")
        auto_reply.start_auto_reply("tinder")

        assert "wyylde" in auto_reply._monitoring_tasks
        assert "tinder" in auto_reply._monitoring_tasks
        assert auto_reply._monitoring_tasks["wyylde"] is not auto_reply._monitoring_tasks["tinder"]

        # Cleanup
        for t in auto_reply._monitoring_tasks.values():
            t.cancel()
        for t in list(auto_reply._monitoring_tasks.values()):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        auto_reply._monitoring_tasks.clear()


# --- stop_auto_reply ---

@pytest.mark.asyncio
async def test_stop_auto_reply_cancels_task():
    """stop_auto_reply cancels the running task and removes it."""
    from src.actions import auto_reply

    auto_reply._monitoring_tasks.clear()

    with patch.object(auto_reply, "_auto_reply_loop", new_callable=AsyncMock) as mock_loop:
        mock_loop.return_value = None
        auto_reply.start_auto_reply("wyylde")
        task = auto_reply._monitoring_tasks["wyylde"]

        auto_reply.stop_auto_reply("wyylde")

        assert "wyylde" not in auto_reply._monitoring_tasks
        # Task.cancel() was called — wait for it to finish then verify
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        assert task.done()


@pytest.mark.asyncio
async def test_stop_auto_reply_noop_when_not_running():
    """stop_auto_reply does nothing when platform has no running task."""
    from src.actions import auto_reply

    auto_reply._monitoring_tasks.clear()

    # Should not raise
    auto_reply.stop_auto_reply("wyylde")
    assert "wyylde" not in auto_reply._monitoring_tasks


@pytest.mark.asyncio
async def test_stop_auto_reply_only_affects_target_platform():
    """stop_auto_reply only stops the specified platform."""
    from src.actions import auto_reply

    auto_reply._monitoring_tasks.clear()

    with patch.object(auto_reply, "_auto_reply_loop", new_callable=AsyncMock) as mock_loop:
        mock_loop.return_value = None
        auto_reply.start_auto_reply("wyylde")
        auto_reply.start_auto_reply("tinder")

        auto_reply.stop_auto_reply("wyylde")

        assert "wyylde" not in auto_reply._monitoring_tasks
        assert "tinder" in auto_reply._monitoring_tasks

        # Cleanup
        auto_reply._monitoring_tasks["tinder"].cancel()
        try:
            await auto_reply._monitoring_tasks["tinder"]
        except (asyncio.CancelledError, Exception):
            pass
        auto_reply._monitoring_tasks.clear()


# --- _auto_reply_loop ---

@pytest.mark.asyncio
async def test_auto_reply_loop_calls_reply():
    """_auto_reply_loop calls reply_to_unread_sidebar on each iteration."""
    from src.actions import auto_reply

    mock_sessions = {"wyylde": MagicMock()}

    with patch.object(auto_reply, "browser_sessions", mock_sessions), \
         patch.object(auto_reply, "reply_to_unread_sidebar", new_callable=AsyncMock) as mock_reply:
        mock_reply.return_value = ["Alice"]

        # Run loop once then remove platform to stop it
        call_count = 0
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            # After first iteration, remove platform to break loop
            if call_count >= 1:
                mock_sessions.clear()
            await original_sleep(0)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await auto_reply._auto_reply_loop("wyylde", style="romantique", interval=60)

        mock_reply.assert_called_with("wyylde", style="romantique")


@pytest.mark.asyncio
async def test_auto_reply_loop_recovers_from_error():
    """_auto_reply_loop continues after an error in reply_to_unread_sidebar."""
    from src.actions import auto_reply

    mock_sessions = {"wyylde": MagicMock()}
    call_count = 0

    with patch.object(auto_reply, "browser_sessions", mock_sessions), \
         patch.object(auto_reply, "reply_to_unread_sidebar", new_callable=AsyncMock) as mock_reply:
        # First call raises, second succeeds
        mock_reply.side_effect = [RuntimeError("network error"), ["Bob"]]

        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                mock_sessions.clear()
            await original_sleep(0)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await auto_reply._auto_reply_loop("wyylde", style="auto", interval=60)

        # Should have been called twice (once with error, once successfully)
        assert mock_reply.call_count == 2


@pytest.mark.asyncio
async def test_auto_reply_loop_stops_when_session_removed():
    """_auto_reply_loop exits when platform is removed from browser_sessions."""
    from src.actions import auto_reply

    # Empty sessions = loop should exit immediately
    with patch.object(auto_reply, "browser_sessions", {}), \
         patch.object(auto_reply, "reply_to_unread_sidebar", new_callable=AsyncMock) as mock_reply:
        await auto_reply._auto_reply_loop("wyylde", style="auto", interval=60)

    # reply should never be called since session was not present
    mock_reply.assert_not_called()
