"""Daily rate limiter for anti-ban protection.

Tracks action counts per day/platform in the daily_counters table
and enforces configurable limits to avoid detection.
"""

import logging
from datetime import date, timedelta

import aiosqlite

from . import database as db_mod

logger = logging.getLogger(__name__)

DEFAULT_DAILY_LIMITS = {
    "likes": 100,
    "messages": 20,
    "replies": 30,
    "follows": 80,
    "crushes": 50,
}


async def get_daily_count(platform: str, action: str) -> int:
    """Return the counter for today for a given platform/action."""
    today = str(date.today())
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT count FROM daily_counters WHERE date = ? AND platform = ? AND action = ?",
            (today, platform, action),
        )
        row = await cursor.fetchone()
    return row[0] if row else 0


async def increment_daily_count(platform: str, action: str) -> int:
    """Increment counter for today and return the new value."""
    today = str(date.today())
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO daily_counters (date, platform, action, count) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(date, platform, action) DO UPDATE SET count = count + 1",
            (today, platform, action),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT count FROM daily_counters WHERE date = ? AND platform = ? AND action = ?",
            (today, platform, action),
        )
        row = await cursor.fetchone()
    return row[0] if row else 1


async def check_daily_limit(platform: str, action: str) -> tuple[bool, int, int]:
    """Check whether the action is still allowed today.

    Returns (allowed, current_count, max_limit).
    """
    current = await get_daily_count(platform, action)
    max_limit = DEFAULT_DAILY_LIMITS.get(action, 100)
    allowed = current < max_limit
    return allowed, current, max_limit


async def get_daily_stats(platform: str) -> dict:
    """Return {action: {count, limit, remaining}} for every tracked action."""
    stats = {}
    for action, limit in DEFAULT_DAILY_LIMITS.items():
        count = await get_daily_count(platform, action)
        stats[action] = {
            "count": count,
            "limit": limit,
            "remaining": max(0, limit - count),
        }
    return stats


async def reset_daily_counters():
    """Delete entries older than 7 days to keep the table small."""
    cutoff = str(date.today() - timedelta(days=7))
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute("DELETE FROM daily_counters WHERE date < ?", (cutoff,))
        await db.commit()
    logger.info(f"Purged daily_counters older than {cutoff}")
