"""Tests for the metrics tracker module — log messages, detect replies, stats."""

import pytest
import aiosqlite

from src.metrics.tracker import (
    ensure_metrics_table,
    log_message_sent,
    check_reply_received,
    get_stats,
    get_recent_messages,
)


@pytest.fixture
async def db(tmp_path):
    """Create a temp SQLite DB with the metrics table for each test."""
    db_path = str(tmp_path / "test_metrics.db")
    conn = await aiosqlite.connect(db_path)
    await ensure_metrics_table(conn)
    yield conn
    await conn.close()


# --- ensure_metrics_table ---

@pytest.mark.asyncio
async def test_ensure_metrics_table_creates_table(db):
    """Table message_metrics should exist after ensure_metrics_table."""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='message_metrics'"
    )
    row = await cursor.fetchone()
    assert row is not None, "message_metrics table should exist"


@pytest.mark.asyncio
async def test_ensure_metrics_table_idempotent(db):
    """Calling ensure_metrics_table twice should not fail."""
    await ensure_metrics_table(db)
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='message_metrics'"
    )
    row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_ensure_metrics_table_creates_indexes(db):
    """Indexes idx_metrics_platform and idx_metrics_target should exist."""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    )
    indexes = [row[0] for row in await cursor.fetchall()]
    assert "idx_metrics_platform" in indexes
    assert "idx_metrics_target" in indexes


# --- log_message_sent ---

@pytest.mark.asyncio
async def test_log_message_sent_returns_id(db):
    """log_message_sent should return the row ID."""
    row_id = await log_message_sent(db, "wyylde", "Alice", "romantique")
    assert isinstance(row_id, int)
    assert row_id >= 1


@pytest.mark.asyncio
async def test_log_message_sent_inserts_row(db):
    """Logged message should be retrievable from the DB."""
    await log_message_sent(db, "wyylde", "Bob", "auto", template_id="tmpl_a")
    cursor = await db.execute(
        "SELECT platform, target_name, style, template_id, reply_detected "
        "FROM message_metrics WHERE target_name = 'Bob'"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "wyylde"
    assert row[1] == "Bob"
    assert row[2] == "auto"
    assert row[3] == "tmpl_a"
    assert row[4] == 0  # reply_detected default


@pytest.mark.asyncio
async def test_log_message_sent_no_template(db):
    """template_id should be NULL when not provided."""
    await log_message_sent(db, "tinder", "Clara", "direct_sexe")
    cursor = await db.execute(
        "SELECT template_id FROM message_metrics WHERE target_name = 'Clara'"
    )
    row = await cursor.fetchone()
    assert row[0] is None


@pytest.mark.asyncio
async def test_log_message_sent_sets_sent_at(db):
    """sent_at should be a positive float (timestamp)."""
    await log_message_sent(db, "wyylde", "Diana", "auto")
    cursor = await db.execute(
        "SELECT sent_at FROM message_metrics WHERE target_name = 'Diana'"
    )
    row = await cursor.fetchone()
    assert row[0] is not None
    assert row[0] > 0


@pytest.mark.asyncio
async def test_log_multiple_messages(db):
    """Multiple messages for the same target should create separate rows."""
    await log_message_sent(db, "wyylde", "Eve", "auto")
    await log_message_sent(db, "wyylde", "Eve", "romantique")
    cursor = await db.execute(
        "SELECT COUNT(*) FROM message_metrics WHERE target_name = 'Eve'"
    )
    count = (await cursor.fetchone())[0]
    assert count == 2


# --- check_reply_received ---

@pytest.mark.asyncio
async def test_check_reply_no_pending(db):
    """No pending message -> returns False."""
    result = await check_reply_received(db, "wyylde", "Nobody")
    assert result is False


@pytest.mark.asyncio
async def test_check_reply_marks_replied(db):
    """Should mark the latest un-replied message as replied."""
    await log_message_sent(db, "wyylde", "Frank", "auto")
    result = await check_reply_received(db, "wyylde", "Frank")
    assert result is True
    cursor = await db.execute(
        "SELECT reply_detected, reply_at FROM message_metrics WHERE target_name = 'Frank'"
    )
    row = await cursor.fetchone()
    assert row[0] == 1
    assert row[1] is not None
    assert row[1] > 0


@pytest.mark.asyncio
async def test_check_reply_only_marks_latest_unreplied(db):
    """With two messages, only the latest un-replied should be marked."""
    await log_message_sent(db, "wyylde", "Grace", "auto")
    await log_message_sent(db, "wyylde", "Grace", "romantique")
    # First reply marks the latest (second message)
    result = await check_reply_received(db, "wyylde", "Grace")
    assert result is True
    cursor = await db.execute(
        "SELECT reply_detected FROM message_metrics "
        "WHERE target_name = 'Grace' ORDER BY id"
    )
    rows = await cursor.fetchall()
    assert rows[0][0] == 0  # first message still un-replied
    assert rows[1][0] == 1  # second message marked as replied


@pytest.mark.asyncio
async def test_check_reply_already_replied(db):
    """If all messages already replied, returns False."""
    await log_message_sent(db, "wyylde", "Heidi", "auto")
    await check_reply_received(db, "wyylde", "Heidi")
    # Second call should find no un-replied message
    result = await check_reply_received(db, "wyylde", "Heidi")
    assert result is False


@pytest.mark.asyncio
async def test_check_reply_wrong_platform(db):
    """Reply check on a different platform should not match."""
    await log_message_sent(db, "wyylde", "Iris", "auto")
    result = await check_reply_received(db, "tinder", "Iris")
    assert result is False


# --- get_stats ---

@pytest.mark.asyncio
async def test_stats_empty(db):
    """Empty DB should return zero stats."""
    stats = await get_stats(db)
    assert stats["total_sent"] == 0
    assert stats["total_replied"] == 0
    assert stats["global_rate"] == 0.0
    assert stats["by_style"] == {}
    assert stats["by_template"] == {}


@pytest.mark.asyncio
async def test_stats_totals(db):
    """Stats should count total sent and replied correctly."""
    await log_message_sent(db, "wyylde", "A", "auto")
    await log_message_sent(db, "wyylde", "B", "auto")
    await log_message_sent(db, "wyylde", "C", "romantique")
    await check_reply_received(db, "wyylde", "A")
    stats = await get_stats(db)
    assert stats["total_sent"] == 3
    assert stats["total_replied"] == 1
    assert stats["global_rate"] == round(1 / 3, 3)


@pytest.mark.asyncio
async def test_stats_by_style(db):
    """Stats should group by style."""
    await log_message_sent(db, "wyylde", "A", "romantique")
    await log_message_sent(db, "wyylde", "B", "romantique")
    await log_message_sent(db, "wyylde", "C", "auto")
    await check_reply_received(db, "wyylde", "A")
    stats = await get_stats(db)
    assert "romantique" in stats["by_style"]
    assert stats["by_style"]["romantique"]["sent"] == 2
    assert stats["by_style"]["romantique"]["replied"] == 1
    assert stats["by_style"]["romantique"]["rate"] == 0.5
    assert stats["by_style"]["auto"]["sent"] == 1
    assert stats["by_style"]["auto"]["replied"] == 0


@pytest.mark.asyncio
async def test_stats_by_template(db):
    """Stats should group by template_id (excluding NULL templates)."""
    await log_message_sent(db, "wyylde", "A", "auto", template_id="tmpl_x")
    await log_message_sent(db, "wyylde", "B", "auto", template_id="tmpl_x")
    await log_message_sent(db, "wyylde", "C", "auto")  # no template
    await check_reply_received(db, "wyylde", "A")
    stats = await get_stats(db)
    assert "tmpl_x" in stats["by_template"]
    assert stats["by_template"]["tmpl_x"]["sent"] == 2
    assert stats["by_template"]["tmpl_x"]["replied"] == 1
    # NULL template should not appear in by_template
    assert None not in stats["by_template"]


@pytest.mark.asyncio
async def test_stats_platform_filter(db):
    """Stats should filter by platform when provided."""
    await log_message_sent(db, "wyylde", "A", "auto")
    await log_message_sent(db, "tinder", "B", "auto")
    stats_wyylde = await get_stats(db, platform="wyylde")
    assert stats_wyylde["total_sent"] == 1
    stats_tinder = await get_stats(db, platform="tinder")
    assert stats_tinder["total_sent"] == 1
    stats_all = await get_stats(db)
    assert stats_all["total_sent"] == 2


# --- get_recent_messages ---

@pytest.mark.asyncio
async def test_recent_messages_empty(db):
    """Empty DB returns empty list."""
    result = await get_recent_messages(db)
    assert result == []


@pytest.mark.asyncio
async def test_recent_messages_returns_dicts(db):
    """Each row should be a dict with expected keys."""
    await log_message_sent(db, "wyylde", "Alice", "auto")
    result = await get_recent_messages(db)
    assert len(result) == 1
    row = result[0]
    expected_keys = {"id", "platform", "target_name", "style", "template_id",
                     "sent_at", "reply_detected", "reply_at"}
    assert set(row.keys()) == expected_keys
    assert row["platform"] == "wyylde"
    assert row["target_name"] == "Alice"
    assert row["reply_detected"] is False


@pytest.mark.asyncio
async def test_recent_messages_order(db):
    """Messages should be ordered by most recent first."""
    await log_message_sent(db, "wyylde", "First", "auto")
    await log_message_sent(db, "wyylde", "Second", "auto")
    result = await get_recent_messages(db)
    assert result[0]["target_name"] == "Second"
    assert result[1]["target_name"] == "First"


@pytest.mark.asyncio
async def test_recent_messages_limit(db):
    """Limit parameter should cap the number of results."""
    for i in range(10):
        await log_message_sent(db, "wyylde", f"User_{i}", "auto")
    result = await get_recent_messages(db, limit=3)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_recent_messages_platform_filter(db):
    """Platform filter should only return matching messages."""
    await log_message_sent(db, "wyylde", "A", "auto")
    await log_message_sent(db, "tinder", "B", "auto")
    result = await get_recent_messages(db, platform="wyylde")
    assert len(result) == 1
    assert result[0]["platform"] == "wyylde"


@pytest.mark.asyncio
async def test_recent_messages_reply_status(db):
    """reply_detected should be True after check_reply_received."""
    await log_message_sent(db, "wyylde", "Bob", "auto")
    await check_reply_received(db, "wyylde", "Bob")
    result = await get_recent_messages(db)
    assert result[0]["reply_detected"] is True
    assert result[0]["reply_at"] is not None
