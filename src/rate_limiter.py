"""Rate limiter for anti-ban protection.

Two strategies:
- **Calendar-day** (default, via `daily_counters` table). Resets at midnight UTC.
  Used by Wyylde and Meetic — loose, matches legacy behavior.
- **Sliding window** (via `activity_log` `created_at` timestamps). Queries the
  last N hours. Used by Tinder per security review (midnight-reset lets a bot
  do 99+99 swipes across midnight, which any real rate-limit detector catches).

Gender-aware Tinder caps per T2-A + security review:
- Free-tier Tinder Web serves ~40-60 right-swipes/12h for male accounts,
  ~100/12h for female. Conservative targets below stay well under the flag zone.
- Right-swipe rate should stay ≤30% of total swipes.
"""

import logging
import os
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

# --- Sliding-window limits (Tinder only) ---
# Key: platform -> {action: (max_count, window_hours)}
# Gender-aware for swipes (reads MY_GENDER env; defaults to male conservative).
_MY_GENDER = (os.getenv("MY_GENDER", "male") or "male").lower()

_TINDER_SWIPE_CAP = 40 if _MY_GENDER == "male" else 80  # per 12h, T2-A conservative

SLIDING_WINDOW_LIMITS = {
    "tinder": {
        "likes": (_TINDER_SWIPE_CAP, 12),
        "messages": (20, 12),
        "replies": (40, 12),
    },
}

PLATFORMS_SLIDING = set(SLIDING_WINDOW_LIMITS.keys())


def _get_sliding_limit(platform: str, action: str) -> tuple[int, int] | None:
    """Return (max_count, window_hours) if platform+action uses sliding window."""
    return SLIDING_WINDOW_LIMITS.get(platform, {}).get(action)


async def _sliding_window_count(platform: str, action: str, window_hours: int) -> int:
    """Count activity_log rows for (platform, action) in the last window_hours."""
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM activity_log "
            "WHERE platform = ? AND action = ? "
            "AND created_at > datetime('now', '-' || ? || ' hours')",
            (platform, action, int(window_hours)),
        )
        row = await cursor.fetchone()
    return row[0] if row else 0


async def get_daily_count(platform: str, action: str) -> int:
    """Return today's counter from daily_counters for platform/action.

    Low-level primitive — always reads daily_counters regardless of whether the
    platform uses a sliding window. Use `check_daily_limit` for the enforcement
    query, which dispatches to the sliding-window source when applicable.
    """
    today = str(date.today())
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT count FROM daily_counters WHERE date = ? AND platform = ? AND action = ?",
            (today, platform, action),
        )
        row = await cursor.fetchone()
    return row[0] if row else 0


async def get_sliding_count(platform: str, action: str) -> int:
    """Return count from activity_log over the platform/action's window.

    Returns 0 for platforms that don't use a sliding window.
    """
    sliding = _get_sliding_limit(platform, action)
    if not sliding:
        return 0
    _max, window_hours = sliding
    return await _sliding_window_count(platform, action, window_hours)


async def increment_daily_count(platform: str, action: str) -> int:
    """Increment counter.

    For sliding-window platforms, the canonical source is activity_log (written
    by the action layer). We still bump daily_counters for the dashboard's
    convenience — but enforcement uses the sliding query.
    """
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
    """Check whether the action is still allowed.

    Returns (allowed, current_count, max_limit). Dispatches to sliding-window
    or calendar-day based on platform.
    """
    sliding = _get_sliding_limit(platform, action)
    if sliding:
        max_limit, window_hours = sliding
        current = await _sliding_window_count(platform, action, window_hours)
        return current < max_limit, current, max_limit

    current = await get_daily_count(platform, action)
    max_limit = DEFAULT_DAILY_LIMITS.get(action, 100)
    return current < max_limit, current, max_limit


async def get_daily_stats(platform: str) -> dict:
    """Return {action: {count, limit, remaining, window}} for every tracked action."""
    stats = {}
    if platform in PLATFORMS_SLIDING:
        for action, (max_limit, window_hours) in SLIDING_WINDOW_LIMITS[platform].items():
            count = await _sliding_window_count(platform, action, window_hours)
            stats[action] = {
                "count": count,
                "limit": max_limit,
                "remaining": max(0, max_limit - count),
                "window": f"{window_hours}h sliding",
            }
        return stats

    for action, limit in DEFAULT_DAILY_LIMITS.items():
        count = await get_daily_count(platform, action)
        stats[action] = {
            "count": count,
            "limit": limit,
            "remaining": max(0, limit - count),
            "window": "calendar-day",
        }
    return stats


async def reset_daily_counters():
    """Delete entries older than 7 days to keep the table small."""
    cutoff = str(date.today() - timedelta(days=7))
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute("DELETE FROM daily_counters WHERE date < ?", (cutoff,))
        await db.commit()
    logger.info(f"Purged daily_counters older than {cutoff}")
