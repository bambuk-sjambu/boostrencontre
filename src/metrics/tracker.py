"""
Metrics tracker — log sent messages and track reply rates.

Stores data in SQLite via aiosqlite. Provides stats grouped by style and template.

Tables created:
    message_metrics — one row per message sent
        id, platform, target_name, style, template_id,
        sent_at, reply_detected, reply_at
"""

import time
from typing import Any, Optional

import aiosqlite

# ---------------------------------------------------------------------------
# Table setup
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS message_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    target_name TEXT NOT NULL,
    style TEXT NOT NULL DEFAULT 'auto',
    template_id TEXT DEFAULT NULL,
    sent_at REAL NOT NULL,
    reply_detected INTEGER NOT NULL DEFAULT 0,
    reply_at REAL DEFAULT NULL
)
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_metrics_platform
    ON message_metrics (platform)
"""

_CREATE_INDEX_TARGET_SQL = """
CREATE INDEX IF NOT EXISTS idx_metrics_target
    ON message_metrics (platform, target_name)
"""


async def ensure_metrics_table(db: aiosqlite.Connection) -> None:
    """Create the message_metrics table if it does not exist."""
    await db.execute(_CREATE_TABLE_SQL)
    await db.execute(_CREATE_INDEX_SQL)
    await db.execute(_CREATE_INDEX_TARGET_SQL)
    await db.commit()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

async def log_message_sent(
    db: aiosqlite.Connection,
    platform: str,
    target_name: str,
    style: str,
    template_id: Optional[str] = None,
) -> int:
    """
    Log a message that was just sent.

    Args:
        db: aiosqlite connection.
        platform: Platform name (e.g. "wyylde").
        target_name: Recipient pseudo.
        style: Message style used (e.g. "romantique", "auto").
        template_id: Optional template identifier if a template was used.

    Returns:
        Row ID of the inserted record.
    """
    now = time.time()
    cursor = await db.execute(
        """
        INSERT INTO message_metrics (platform, target_name, style, template_id, sent_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (platform, target_name, style, template_id, now),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Reply detection
# ---------------------------------------------------------------------------

async def check_reply_received(
    db: aiosqlite.Connection,
    platform: str,
    target_name: str,
) -> bool:
    """
    Mark the most recent un-replied message to target_name as replied.

    Finds the latest row where reply_detected=0 for this platform+target
    and sets reply_detected=1, reply_at=now.

    Args:
        db: aiosqlite connection.
        platform: Platform name.
        target_name: The pseudo who replied.

    Returns:
        True if a row was updated, False if no pending message was found.
    """
    now = time.time()
    cursor = await db.execute(
        """
        UPDATE message_metrics
        SET reply_detected = 1, reply_at = ?
        WHERE id = (
            SELECT id FROM message_metrics
            WHERE platform = ? AND target_name = ? AND reply_detected = 0
            ORDER BY sent_at DESC
            LIMIT 1
        )
        """,
        (now, platform, target_name),
    )
    await db.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

async def get_stats(
    db: aiosqlite.Connection,
    platform: Optional[str] = None,
) -> dict[str, Any]:
    """
    Compute message statistics grouped by style and by template.

    Args:
        db: aiosqlite connection.
        platform: If provided, filter to this platform only.

    Returns:
        {
            "total_sent": int,
            "total_replied": int,
            "global_rate": float,  # 0.0 - 1.0
            "by_style": {
                "romantique": {"sent": 10, "replied": 3, "rate": 0.3},
                ...
            },
            "by_template": {
                "template_a": {"sent": 5, "replied": 2, "rate": 0.4},
                ...
            },
        }
    """
    where_clause = ""
    params: list[Any] = []
    if platform:
        where_clause = "WHERE platform = ?"
        params = [platform]

    # -- By style --
    by_style: dict[str, dict[str, Any]] = {}
    async with db.execute(
        f"""
        SELECT style,
               COUNT(*) as sent,
               SUM(reply_detected) as replied
        FROM message_metrics
        {where_clause}
        GROUP BY style
        ORDER BY sent DESC
        """,
        params,
    ) as cursor:
        async for row in cursor:
            style_name, sent, replied = row[0], row[1], row[2] or 0
            by_style[style_name] = {
                "sent": sent,
                "replied": replied,
                "rate": round(replied / sent, 3) if sent > 0 else 0.0,
            }

    # -- By template --
    by_template: dict[str, dict[str, Any]] = {}
    if where_clause:
        tmpl_where = f"{where_clause} AND template_id IS NOT NULL"
        tmpl_params = list(params)
    else:
        tmpl_where = "WHERE template_id IS NOT NULL"
        tmpl_params = []

    async with db.execute(
        f"""
        SELECT template_id,
               COUNT(*) as sent,
               SUM(reply_detected) as replied
        FROM message_metrics
        {tmpl_where}
        GROUP BY template_id
        ORDER BY sent DESC
        """,
        tmpl_params,
    ) as cursor:
        async for row in cursor:
            tmpl_id, sent, replied = row[0], row[1], row[2] or 0
            by_template[tmpl_id] = {
                "sent": sent,
                "replied": replied,
                "rate": round(replied / sent, 3) if sent > 0 else 0.0,
            }

    # -- Totals --
    total_sent = sum(s["sent"] for s in by_style.values())
    total_replied = sum(s["replied"] for s in by_style.values())

    return {
        "total_sent": total_sent,
        "total_replied": total_replied,
        "global_rate": round(total_replied / total_sent, 3) if total_sent > 0 else 0.0,
        "by_style": by_style,
        "by_template": by_template,
    }


# ---------------------------------------------------------------------------
# Recent messages (useful for dashboard)
# ---------------------------------------------------------------------------

async def get_recent_messages(
    db: aiosqlite.Connection,
    platform: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Return the most recent sent messages with reply status.

    Args:
        db: aiosqlite connection.
        platform: Optional platform filter.
        limit: Max rows to return (default 50).

    Returns:
        List of dicts with keys: id, platform, target_name, style,
        template_id, sent_at, reply_detected, reply_at.
    """
    where_clause = ""
    params: list[Any] = []
    if platform:
        where_clause = "WHERE platform = ?"
        params = [platform]

    params.append(limit)

    rows = []
    async with db.execute(
        f"""
        SELECT id, platform, target_name, style, template_id,
               sent_at, reply_detected, reply_at
        FROM message_metrics
        {where_clause}
        ORDER BY sent_at DESC
        LIMIT ?
        """,
        params,
    ) as cursor:
        async for row in cursor:
            rows.append({
                "id": row[0],
                "platform": row[1],
                "target_name": row[2],
                "style": row[3],
                "template_id": row[4],
                "sent_at": row[5],
                "reply_detected": bool(row[6]),
                "reply_at": row[7],
            })

    return rows
