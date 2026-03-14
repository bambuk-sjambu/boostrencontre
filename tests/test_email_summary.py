"""Tests for the daily email summary module."""

import json
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import aiosqlite
import src.database as db_mod
from src.database import init_db, get_db
from src.email_summary import (
    get_email_settings,
    save_email_settings,
    generate_summary,
    send_summary_email,
    _render_html,
    _collect_day_stats,
    _collect_conversations,
    _collect_alerts,
    _collect_campaigns,
    start_scheduler,
    stop_scheduler,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp DB for each test."""
    db_mod.DB_PATH = str(tmp_path / "test.db")
    await init_db()
    # Create email_settings table
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS email_settings ("
            "id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
        )
        await db.commit()
    yield
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


# --- Settings ---

@pytest.mark.asyncio
async def test_get_default_settings():
    """Default settings when nothing is saved."""
    settings = await get_email_settings()
    assert settings["email_enabled"] is False
    assert settings["email_time"] == "22:00"
    assert settings["email_recipient"] == ""
    assert settings["smtp_host"] == ""


@pytest.mark.asyncio
async def test_save_and_load_settings():
    """Save settings and reload them."""
    await save_email_settings({
        "email_enabled": True,
        "email_recipient": "test@example.com",
        "email_time": "08:30",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "user",
        "smtp_password": "secret",
    })
    settings = await get_email_settings()
    assert settings["email_enabled"] is True
    assert settings["email_recipient"] == "test@example.com"
    assert settings["email_time"] == "08:30"
    assert settings["smtp_host"] == "smtp.example.com"
    assert settings["smtp_password"] == "secret"


@pytest.mark.asyncio
async def test_save_overwrites_existing():
    """Saving twice should overwrite, not duplicate."""
    await save_email_settings({"email_recipient": "a@b.com"})
    await save_email_settings({"email_recipient": "c@d.com"})
    settings = await get_email_settings()
    assert settings["email_recipient"] == "c@d.com"


# --- Data collection ---

@pytest.mark.asyncio
async def test_collect_day_stats_empty():
    """No activity returns empty dict."""
    stats = await _collect_day_stats("2026-03-10")
    assert stats == {}


@pytest.mark.asyncio
async def test_collect_day_stats_with_data():
    """Stats should reflect logged activity."""
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("wyylde", "message", "Alice", "2026-03-10 14:00:00"),
        )
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("wyylde", "like", "Bob", "2026-03-10 15:00:00"),
        )
        await db.commit()

    stats = await _collect_day_stats("2026-03-10")
    assert "wyylde" in stats
    assert stats["wyylde"]["messages"] == 1
    assert stats["wyylde"]["likes"] == 1


@pytest.mark.asyncio
async def test_collect_conversations_empty():
    """No conversations returns empty lists."""
    convs = await _collect_conversations("2026-03-10")
    assert convs["new"] == []
    assert convs["active"] == []


@pytest.mark.asyncio
async def test_collect_conversations_with_data():
    """Should find new conversations from conversation_history."""
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversation_history "
            "(platform, contact_name, direction, message_text, stage, turn_number, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("wyylde", "Clara", "sent", "Salut Clara!", "accroche", 1, "2026-03-10 10:00:00"),
        )
        await db.commit()

    convs = await _collect_conversations("2026-03-10")
    assert len(convs["new"]) == 1
    assert convs["new"][0]["contact_name"] == "Clara"
    assert len(convs["active"]) == 1


@pytest.mark.asyncio
async def test_collect_alerts_no_limits():
    """No alerts when counters are low."""
    alerts = await _collect_alerts("2026-03-10")
    assert alerts == []


@pytest.mark.asyncio
async def test_collect_campaigns_empty():
    """No active campaigns returns empty list."""
    campaigns = await _collect_campaigns()
    assert campaigns == []


# --- HTML rendering ---

def test_render_html_empty():
    """Render with no data produces valid HTML."""
    html = _render_html({}, {"new": [], "active": [], "stage_changes": []}, [], [], "2026-03-10")
    assert "Resume du 2026-03-10" in html
    assert "Aucune activite" in html
    assert "</html>" in html


def test_render_html_with_stats():
    """Render with stats shows platform data."""
    stats = {"wyylde": {"messages": 5, "replies": 2, "likes": 10, "follows": 3, "crushes": 1, "response_rate": 40.0}}
    html = _render_html(stats, {"new": [], "active": [], "stage_changes": []}, [], [], "2026-03-10")
    assert "Wyylde" in html
    assert "40.0%" in html


def test_render_html_with_alerts():
    """Render with alerts shows warning."""
    alerts = [{"type": "limit", "platform": "wyylde", "action": "messages", "count": 18, "limit": 20, "pct": 90}]
    html = _render_html({}, {"new": [], "active": [], "stage_changes": []}, alerts, [], "2026-03-10")
    assert "messages" in html
    assert "18/20" in html


def test_render_html_with_campaigns():
    """Render with campaigns shows funnel."""
    campaigns = [{"name": "Test", "platform": "wyylde", "contacts_done": 5, "max_contacts": 20, "funnel": {"contacted": 3, "replied": 2}}]
    html = _render_html({}, {"new": [], "active": [], "stage_changes": []}, [], campaigns, "2026-03-10")
    assert "Test" in html
    assert "5/20" in html


# --- generate_summary ---

@pytest.mark.asyncio
async def test_generate_summary_structure():
    """Summary should return all expected keys."""
    summary = await generate_summary("2026-03-10")
    assert "day" in summary
    assert "stats" in summary
    assert "conversations" in summary
    assert "alerts" in summary
    assert "campaigns" in summary
    assert "html" in summary
    assert summary["day"] == "2026-03-10"


# --- send_summary_email ---

@pytest.mark.asyncio
async def test_send_email_no_recipient():
    """Should fail gracefully without recipient."""
    await save_email_settings({"smtp_host": "smtp.test.com"})
    result = await send_summary_email()
    assert result["status"] == "error"
    assert "no_recipient" in result["detail"]


@pytest.mark.asyncio
async def test_send_email_no_smtp():
    """Should fail gracefully without SMTP config."""
    await save_email_settings({"email_recipient": "a@b.com"})
    result = await send_summary_email()
    assert result["status"] == "error"
    assert "no_smtp" in result["detail"]


@pytest.mark.asyncio
async def test_send_email_smtp_error_saves_fallback(tmp_path):
    """SMTP failure should save HTML fallback."""
    settings = {
        "email_recipient": "a@b.com",
        "smtp_host": "smtp.fake.invalid",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
    }
    await save_email_settings(settings)

    with patch("src.email_summary._send_smtp", side_effect=ConnectionRefusedError("test")):
        result = await send_summary_email(settings)

    assert result["status"] == "error"
    assert "fallback" in result


@pytest.mark.asyncio
async def test_send_email_success():
    """Successful send returns sent status."""
    settings = {
        "email_recipient": "a@b.com",
        "smtp_host": "smtp.test.com",
        "smtp_port": 587,
        "smtp_user": "user",
        "smtp_password": "pass",
    }
    with patch("src.email_summary._send_smtp"):
        result = await send_summary_email(settings)

    assert result["status"] == "sent"
    assert result["recipient"] == "a@b.com"


# --- Scheduler ---

def test_start_stop_scheduler():
    """Scheduler should start and stop without errors."""
    import asyncio

    async def _test():
        task = start_scheduler()
        assert task is not None
        assert not task.done()
        stop_scheduler()
        # Give it a moment to cancel
        await asyncio.sleep(0.1)

    asyncio.get_event_loop().run_until_complete(_test())
