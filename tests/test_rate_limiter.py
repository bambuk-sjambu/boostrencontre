"""Tests for src/rate_limiter.py — daily counters and limit checks."""

import os
import tempfile
from datetime import date, timedelta

import aiosqlite
import pytest

import src.database as db_mod


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp DB with daily_counters table for every test."""
    db_path = str(tmp_path / "test_rate.db")
    original = db_mod.DB_PATH
    db_mod.DB_PATH = db_path

    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_counters (
                date TEXT NOT NULL,
                platform TEXT NOT NULL,
                action TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (date, platform, action)
            )
        """)
        await db.commit()

    yield

    db_mod.DB_PATH = original
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.mark.asyncio
async def test_get_daily_count_returns_zero_when_empty():
    from src.rate_limiter import get_daily_count
    count = await get_daily_count("wyylde", "likes")
    assert count == 0


@pytest.mark.asyncio
async def test_increment_daily_count_increments():
    from src.rate_limiter import increment_daily_count, get_daily_count
    new_count = await increment_daily_count("wyylde", "likes")
    assert new_count == 1
    new_count = await increment_daily_count("wyylde", "likes")
    assert new_count == 2
    count = await get_daily_count("wyylde", "likes")
    assert count == 2


@pytest.mark.asyncio
async def test_check_daily_limit_allowed():
    from src.rate_limiter import check_daily_limit
    allowed, current, limit = await check_daily_limit("wyylde", "likes")
    assert allowed is True
    assert current == 0
    assert limit == 100


@pytest.mark.asyncio
async def test_check_daily_limit_blocked():
    from src.rate_limiter import check_daily_limit, increment_daily_count, DEFAULT_DAILY_LIMITS
    for _ in range(DEFAULT_DAILY_LIMITS["messages"]):
        await increment_daily_count("wyylde", "messages")
    allowed, current, limit = await check_daily_limit("wyylde", "messages")
    assert allowed is False
    assert current == DEFAULT_DAILY_LIMITS["messages"]


@pytest.mark.asyncio
async def test_get_daily_stats_returns_all_actions():
    from src.rate_limiter import get_daily_stats, DEFAULT_DAILY_LIMITS
    stats = await get_daily_stats("wyylde")
    assert set(stats.keys()) == set(DEFAULT_DAILY_LIMITS.keys())
    for action, data in stats.items():
        assert "count" in data
        assert "limit" in data
        assert "remaining" in data
        assert data["count"] == 0
        assert data["remaining"] == data["limit"]


@pytest.mark.asyncio
async def test_counters_are_per_day():
    """Counters for a different date should not affect today's count."""
    from src.rate_limiter import get_daily_count
    yesterday = str(date.today() - timedelta(days=1))
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO daily_counters (date, platform, action, count) VALUES (?, ?, ?, ?)",
            (yesterday, "wyylde", "likes", 99),
        )
        await db.commit()
    count = await get_daily_count("wyylde", "likes")
    assert count == 0


@pytest.mark.asyncio
async def test_counters_are_per_platform():
    from src.rate_limiter import increment_daily_count, get_daily_count
    await increment_daily_count("wyylde", "likes")
    await increment_daily_count("wyylde", "likes")
    await increment_daily_count("tinder", "likes")
    assert await get_daily_count("wyylde", "likes") == 2
    assert await get_daily_count("tinder", "likes") == 1


@pytest.mark.asyncio
async def test_reset_daily_counters():
    from src.rate_limiter import reset_daily_counters
    old_date = str(date.today() - timedelta(days=10))
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO daily_counters (date, platform, action, count) VALUES (?, ?, ?, ?)",
            (old_date, "wyylde", "likes", 50),
        )
        await db.commit()
    await reset_daily_counters()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT count FROM daily_counters WHERE date = ?", (old_date,)
        )
        assert await cursor.fetchone() is None
