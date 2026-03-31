"""Daily email summary — generates and sends a recap of the day's activity.

Uses SMTP to send an HTML email with stats, conversations, alerts, and campaign progress.
Scheduler runs as an asyncio background task.
"""

import asyncio
import json
import logging
import os
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as h

import aiosqlite

from . import database as db_mod
from .rate_limiter import DEFAULT_DAILY_LIMITS

logger = logging.getLogger(__name__)

# Background task handle
_scheduler_task: asyncio.Task | None = None

MESSAGE_ACTIONS = ("message", "sidebar_msg", "search_msg")
REPLY_ACTIONS = ("reply", "sidebar_reply", "auto_reply")
PLATFORMS = ("wyylde", "tinder", "meetic")


# --- Email settings helpers ---

async def get_email_settings() -> dict:
    """Load email settings from DB, with defaults."""
    defaults = {
        "email_enabled": False,
        "email_recipient": "",
        "email_time": "22:00",
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
    }
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT data FROM email_settings WHERE id = 1"
        )
        row = await cursor.fetchone()
    if row:
        try:
            saved = json.loads(row[0])
            defaults.update(saved)
        except (json.JSONDecodeError, TypeError):
            pass
    return defaults


async def save_email_settings(settings: dict) -> None:
    """Save email settings to DB."""
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO email_settings (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (json.dumps(settings),),
        )
        await db.commit()


# --- Data collection ---

async def _collect_day_stats(day_str: str) -> dict:
    """Collect all stats for a given day across platforms."""
    day_start = f"{day_str} 00:00:00"
    day_end = f"{day_str} 23:59:59"

    platforms_stats = {}
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        db.row_factory = db_mod.dict_factory

        for platform in PLATFORMS:
            # Action counts
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
            follows = action_counts.get("follow", 0)
            crushes = action_counts.get("crush", 0)
            total = messages + replies + likes + follows + crushes

            if total == 0:
                continue

            # Response rate
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT target_name) as cnt FROM activity_log "
                "WHERE platform = ? AND action IN (?, ?, ?) "
                "AND created_at BETWEEN ? AND ?",
                (platform, *MESSAGE_ACTIONS, day_start, day_end),
            )
            sent_to = (await cursor.fetchone())["cnt"]

            cursor = await db.execute(
                "SELECT COUNT(DISTINCT r.target_name) as cnt FROM activity_log r "
                "WHERE r.platform = ? AND r.action IN (?, ?, ?) "
                "AND r.created_at BETWEEN ? AND ? "
                "AND EXISTS ("
                "  SELECT 1 FROM activity_log m "
                "  WHERE m.platform = r.platform AND m.target_name = r.target_name "
                "  AND m.action IN (?, ?, ?) AND m.id < r.id"
                ")",
                (platform, *REPLY_ACTIONS, day_start, day_end, *MESSAGE_ACTIONS),
            )
            replied_to = (await cursor.fetchone())["cnt"]
            rate = round(replied_to / sent_to * 100, 1) if sent_to > 0 else 0.0

            platforms_stats[platform] = {
                "messages": messages,
                "replies": replies,
                "likes": likes,
                "follows": follows,
                "crushes": crushes,
                "response_rate": rate,
            }

    return platforms_stats


async def _collect_conversations(day_str: str) -> dict:
    """Collect new and active conversations for the day."""
    day_start = f"{day_str} 00:00:00"
    day_end = f"{day_str} 23:59:59"

    result = {"new": [], "active": [], "stage_changes": []}
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        db.row_factory = db_mod.dict_factory

        # New conversations (first message sent today)
        cursor = await db.execute(
            "SELECT platform, contact_name, message_text, stage "
            "FROM conversation_history "
            "WHERE turn_number = 1 AND direction = 'sent' "
            "AND created_at BETWEEN ? AND ? "
            "ORDER BY created_at DESC LIMIT 20",
            (day_start, day_end),
        )
        result["new"] = await cursor.fetchall()

        # Active today (any message exchanged)
        cursor = await db.execute(
            "SELECT platform, contact_name, "
            "COUNT(*) as turns_today, "
            "MAX(stage) as current_stage "
            "FROM conversation_history "
            "WHERE created_at BETWEEN ? AND ? "
            "GROUP BY platform, contact_name "
            "ORDER BY turns_today DESC LIMIT 20",
            (day_start, day_end),
        )
        result["active"] = await cursor.fetchall()

    return result


async def _collect_alerts(day_str: str) -> list:
    """Collect alerts: limits near threshold, errors."""
    alerts = []

    # Check daily limits proximity
    for action, limit in DEFAULT_DAILY_LIMITS.items():
        for platform in PLATFORMS:
            today = str(date.today())
            async with aiosqlite.connect(db_mod.DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT count FROM daily_counters "
                    "WHERE date = ? AND platform = ? AND action = ?",
                    (today, platform, action),
                )
                row = await cursor.fetchone()
            count = row[0] if row else 0
            pct = count / limit * 100 if limit > 0 else 0
            if pct >= 80:
                alerts.append({
                    "type": "limit",
                    "platform": platform,
                    "action": action,
                    "count": count,
                    "limit": limit,
                    "pct": round(pct, 0),
                })

    return alerts


async def _collect_campaigns() -> list:
    """Collect active campaign stats."""
    campaigns = []
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        db.row_factory = db_mod.dict_factory
        cursor = await db.execute(
            "SELECT id, name, platform, status, max_contacts, contacts_done "
            "FROM campaigns WHERE status IN ('active', 'running') "
            "ORDER BY updated_at DESC"
        )
        campaigns = await cursor.fetchall()

        for c in campaigns:
            cursor = await db.execute(
                "SELECT status, COUNT(*) as cnt FROM campaign_contacts "
                "WHERE campaign_id = ? GROUP BY status",
                (c["id"],),
            )
            statuses = {r["status"]: r["cnt"] for r in await cursor.fetchall()}
            c["funnel"] = statuses

    return campaigns


# --- HTML rendering ---

def _render_html(stats: dict, conversations: dict, alerts: list, campaigns: list, day_str: str) -> str:
    """Render the email body as HTML."""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: -apple-system, Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
.container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
h1 {{ color: #e74c3c; font-size: 22px; margin-top: 0; }}
h2 {{ color: #2c3e50; font-size: 16px; border-bottom: 2px solid #e74c3c; padding-bottom: 6px; margin-top: 24px; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
td, th {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }}
th {{ background: #f8f8f8; font-weight: 600; }}
.stat {{ font-size: 24px; font-weight: bold; color: #e74c3c; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
.alert {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 8px 12px; margin: 8px 0; border-radius: 4px; font-size: 13px; }}
.new {{ background: #d4edda; color: #155724; }}
.footer {{ margin-top: 24px; text-align: center; font-size: 12px; color: #999; }}
</style></head><body>
<div class="container">
<h1>BoostRencontre — Resume du {day_str}</h1>
"""

    # Stats per platform
    if stats:
        html += "<h2>Activite du jour</h2><table><tr><th>Plateforme</th><th>Messages</th><th>Reponses</th><th>Likes</th><th>Follows</th><th>Crushes</th><th>Taux</th></tr>"
        for platform, s in stats.items():
            html += f"<tr><td><b>{h(platform.title())}</b></td><td>{s['messages']}</td><td>{s['replies']}</td><td>{s['likes']}</td><td>{s['follows']}</td><td>{s['crushes']}</td><td>{s['response_rate']}%</td></tr>"
        html += "</table>"
    else:
        html += "<p>Aucune activite aujourd'hui.</p>"

    # Conversations
    if conversations["new"]:
        html += f"<h2>Nouvelles conversations ({len(conversations['new'])})</h2><table><tr><th>Contact</th><th>Plateforme</th><th>Premier message</th></tr>"
        for c in conversations["new"][:10]:
            msg_preview = (c.get("message_text") or "")[:60]
            html += f"<tr><td>{h(c['contact_name'])}</td><td>{h(c['platform'])}</td><td>{h(msg_preview)}...</td></tr>"
        html += "</table>"

    if conversations["active"]:
        html += f"<h2>Conversations actives ({len(conversations['active'])})</h2><table><tr><th>Contact</th><th>Plateforme</th><th>Tours aujourd'hui</th><th>Etape</th></tr>"
        for c in conversations["active"][:10]:
            html += f"<tr><td>{h(c['contact_name'])}</td><td>{h(c['platform'])}</td><td>{c['turns_today']}</td><td><span class='badge'>{h(c['current_stage'])}</span></td></tr>"
        html += "</table>"

    # Alerts
    if alerts:
        html += "<h2>Alertes</h2>"
        for a in alerts:
            html += f"<div class='alert'>⚠ <b>{h(a['platform'].title())}</b> — {h(a['action'])}: {a['count']}/{a['limit']} ({a['pct']:.0f}% du quota)</div>"

    # Campaigns
    if campaigns:
        html += "<h2>Campagnes actives</h2><table><tr><th>Campagne</th><th>Plateforme</th><th>Progression</th><th>Funnel</th></tr>"
        for c in campaigns:
            progress = f"{c['contacts_done']}/{c['max_contacts']}"
            funnel_parts = [f"{status}: {cnt}" for status, cnt in (c.get("funnel") or {}).items()]
            funnel_str = ", ".join(funnel_parts) if funnel_parts else "-"
            html += f"<tr><td>{h(c['name'])}</td><td>{h(c['platform'])}</td><td>{progress}</td><td>{h(funnel_str)}</td></tr>"
        html += "</table>"

    html += """<div class='footer'>BoostRencontre — Resume automatique</div>
</div></body></html>"""

    return html


# --- Generate summary (reusable) ---

async def generate_summary(day_str: str | None = None) -> dict:
    """Generate summary data and HTML for a given day (default: today)."""
    if day_str is None:
        day_str = str(date.today())

    stats = await _collect_day_stats(day_str)
    conversations = await _collect_conversations(day_str)
    alerts = await _collect_alerts(day_str)
    campaigns = await _collect_campaigns()
    html = _render_html(stats, conversations, alerts, campaigns, day_str)

    return {
        "day": day_str,
        "stats": stats,
        "conversations": conversations,
        "alerts": alerts,
        "campaigns": campaigns,
        "html": html,
    }


# --- Send email ---

async def send_summary_email(settings: dict | None = None) -> dict:
    """Generate today's summary and send it by email.

    Returns {"status": "sent"} or {"status": "error", "detail": "..."}.
    """
    if settings is None:
        settings = await get_email_settings()

    if not settings.get("email_recipient"):
        return {"status": "error", "detail": "no_recipient_configured"}
    if not settings.get("smtp_host"):
        return {"status": "error", "detail": "no_smtp_configured"}

    summary = await generate_summary()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"BoostRencontre — Resume du {summary['day']}"
    msg["From"] = settings.get("smtp_user", "boostrencontre@local")
    msg["To"] = settings["email_recipient"]
    msg.attach(MIMEText(summary["html"], "html"))

    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            _send_smtp,
            settings,
            msg,
        )
        logger.info(f"Summary email sent to {settings['email_recipient']}")
        return {"status": "sent", "recipient": settings["email_recipient"]}
    except Exception as e:
        logger.error(f"Failed to send summary email: {e}")
        # Fallback: save HTML locally
        fallback_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            f"summary_{summary['day']}.html",
        )
        try:
            with open(fallback_path, "w", encoding="utf-8") as f:
                f.write(summary["html"])
            logger.info(f"Summary saved as fallback: {fallback_path}")
        except Exception:
            pass
        return {"status": "error", "detail": str(e), "fallback": fallback_path}


def _send_smtp(settings: dict, msg: MIMEMultipart) -> None:
    """Blocking SMTP send (run in executor)."""
    port = int(settings.get("smtp_port", 587))
    host = settings["smtp_host"]

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.starttls()

    user = settings.get("smtp_user", "").strip()
    password = settings.get("smtp_password", "").strip()
    if user and password:
        server.login(user, password)

    server.send_message(msg)
    server.quit()


# --- Scheduler ---

async def _scheduler_loop():
    """Background loop: sends the email daily at the configured time."""
    logger.info("Email summary scheduler started")
    while True:
        try:
            settings = await get_email_settings()
            if not settings.get("email_enabled"):
                await asyncio.sleep(300)  # Check again in 5 min
                continue

            send_time = settings.get("email_time", "22:00")
            now = datetime.now()
            try:
                hour, minute = map(int, send_time.split(":"))
            except (ValueError, AttributeError):
                hour, minute = 22, 0

            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.info(f"Next email summary at {target.strftime('%Y-%m-%d %H:%M')}")
            await asyncio.sleep(wait_seconds)

            # Send
            result = await send_summary_email(settings)
            logger.info(f"Scheduled email result: {result}")

            # Wait at least 60s to avoid double-send
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Email summary scheduler stopped")
            return
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(300)


def start_scheduler() -> asyncio.Task | None:
    """Start the background scheduler. Returns the task."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    return _scheduler_task


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
