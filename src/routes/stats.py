"""Statistics routes for the dashboard."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..database import get_db, dict_factory
from .deps import validate_platform

logger = logging.getLogger(__name__)

router = APIRouter()

MESSAGE_ACTIONS = ("message", "sidebar_msg", "search_msg")
REPLY_ACTIONS = ("reply", "sidebar_reply", "auto_reply")


@router.get("/stats/{platform}")
async def get_stats(platform: str, days: int = 7):
    """Activity statistics for the dashboard."""
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if days < 1 or days > 90:
        days = 7

    today_start = datetime.now(timezone.utc).strftime("%Y-%m-%d 00:00:00")
    period_start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")

    async with await get_db() as db:
        db.row_factory = dict_factory

        # --- Today's counts ---
        today = await _count_today(db, platform, today_start)

        # --- Period stats ---
        period = await _count_period(db, platform, period_start)

        # --- By style ---
        by_style = await _count_by_style(db, platform, period_start)

        # --- By day ---
        by_day = await _count_by_day(db, platform, days)

        # --- Recent conversations ---
        recent = await _recent_conversations(db, platform)

    return {
        "today": today,
        "period": period,
        "by_style": by_style,
        "by_day": by_day,
        "recent_conversations": recent,
    }


async def _count_today(db, platform: str, today_start: str) -> dict:
    """Count today's activity by action type."""
    cursor = await db.execute(
        "SELECT action, COUNT(*) as cnt FROM activity_log "
        "WHERE platform = ? AND created_at >= ? GROUP BY action",
        (platform, today_start),
    )
    rows = await cursor.fetchall()
    action_counts = {r["action"]: r["cnt"] for r in rows}

    messages_sent = sum(action_counts.get(a, 0) for a in MESSAGE_ACTIONS)
    replies_sent = sum(action_counts.get(a, 0) for a in REPLY_ACTIONS)

    return {
        "messages_sent": messages_sent,
        "replies_sent": replies_sent,
        "likes": action_counts.get("like", 0),
        "follows": action_counts.get("follow", 0),
        "crushes": action_counts.get("crush", 0),
    }


async def _count_period(db, platform: str, period_start: str) -> dict:
    """Count messages sent and replies received over a period."""
    # Messages we sent
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM activity_log "
        "WHERE platform = ? AND action IN (?, ?, ?) AND created_at >= ?",
        (platform, *MESSAGE_ACTIONS, period_start),
    )
    row = await cursor.fetchone()
    messages_sent = row["cnt"] if row else 0

    # Replies received: count reply actions where target_name matches
    # someone we previously messaged
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM activity_log r "
        "WHERE r.platform = ? AND r.action IN (?, ?, ?) AND r.created_at >= ? "
        "AND EXISTS ("
        "  SELECT 1 FROM activity_log m "
        "  WHERE m.platform = r.platform AND m.target_name = r.target_name "
        "  AND m.action IN (?, ?, ?) AND m.id < r.id"
        ")",
        (platform, *REPLY_ACTIONS, period_start, *MESSAGE_ACTIONS),
    )
    row = await cursor.fetchone()
    replies_received = row["cnt"] if row else 0

    rate = round((replies_received / messages_sent * 100), 1) if messages_sent > 0 else 0.0

    return {
        "messages_sent": messages_sent,
        "replies_received": replies_received,
        "response_rate": rate,
    }


async def _count_by_style(db, platform: str, period_start: str) -> list:
    """Count messages and responses by style."""
    cursor = await db.execute(
        "SELECT COALESCE(style, 'auto') as style, COUNT(*) as sent FROM activity_log "
        "WHERE platform = ? AND action IN (?, ?, ?) AND created_at >= ? "
        "GROUP BY COALESCE(style, 'auto')",
        (platform, *MESSAGE_ACTIONS, period_start),
    )
    style_rows = await cursor.fetchall()

    results = []
    for sr in style_rows:
        style_name = sr["style"]
        sent = sr["sent"]

        # Count replies for this style's targets
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM activity_log r "
            "WHERE r.platform = ? AND r.action IN (?, ?, ?) AND r.created_at >= ? "
            "AND EXISTS ("
            "  SELECT 1 FROM activity_log m "
            "  WHERE m.platform = r.platform AND m.target_name = r.target_name "
            "  AND m.action IN (?, ?, ?) AND COALESCE(m.style, 'auto') = ? "
            "  AND m.id < r.id"
            ")",
            (platform, *REPLY_ACTIONS, period_start, *MESSAGE_ACTIONS, style_name),
        )
        row = await cursor.fetchone()
        responses = row["cnt"] if row else 0

        rate = round((responses / sent * 100), 1) if sent > 0 else 0.0
        results.append({"style": style_name, "sent": sent, "responses": responses, "rate": rate})

    results.sort(key=lambda x: x["rate"], reverse=True)
    return results


async def _count_by_day(db, platform: str, days: int) -> list:
    """Count activity per day for the last N days."""
    result = []
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        day_start = f"{day} 00:00:00"
        day_end = f"{day} 23:59:59"

        cursor = await db.execute(
            "SELECT action, COUNT(*) as cnt FROM activity_log "
            "WHERE platform = ? AND created_at BETWEEN ? AND ? "
            "GROUP BY action",
            (platform, day_start, day_end),
        )
        rows = await cursor.fetchall()
        action_counts = {r["action"]: r["cnt"] for r in rows}

        messages = sum(action_counts.get(a, 0) for a in MESSAGE_ACTIONS)
        replies = sum(action_counts.get(a, 0) for a in REPLY_ACTIONS)
        likes = action_counts.get("like", 0)

        result.append({"date": day, "messages": messages, "replies": replies, "likes": likes})

    return result


async def _recent_conversations(db, platform: str) -> list:
    """Get the 10 most recent conversations."""
    cursor = await db.execute(
        "SELECT target_name, action, message_sent, created_at FROM activity_log "
        "WHERE platform = ? AND action IN (?, ?, ?, ?, ?, ?) "
        "ORDER BY created_at DESC LIMIT 20",
        (platform, *MESSAGE_ACTIONS, *REPLY_ACTIONS),
    )
    rows = await cursor.fetchall()

    # Deduplicate by target_name, keep the most recent
    seen = set()
    conversations = []
    for r in rows:
        name = r["target_name"]
        if name in seen:
            continue
        seen.add(name)

        # Check if this person replied (has a reply action after our message)
        cursor2 = await db.execute(
            "SELECT id FROM activity_log WHERE platform = ? AND target_name = ? "
            "AND action IN (?, ?, ?)",
            (platform, name, *REPLY_ACTIONS),
        )
        has_reply = bool(await cursor2.fetchone())

        msg_preview = (r["message_sent"] or "")[:80]
        conversations.append({
            "name": name,
            "last_message": msg_preview,
            "timestamp": r["created_at"],
            "replied": has_reply,
        })
        if len(conversations) >= 10:
            break

    return conversations
