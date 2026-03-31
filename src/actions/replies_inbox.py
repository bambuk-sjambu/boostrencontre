import asyncio
import logging
from ..session_manager import browser_sessions
from ..database import get_db
from ..conversation_utils import _human_delay_with_pauses, filter_ui_text
from ..rate_limiter import check_daily_limit, increment_daily_count
from ..messaging.ai_messages import generate_reply_message, MY_PROFILE
from ..messaging.conversation_manager import record_message as record_conv_message
from .replies_helpers import _log_reply

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Simple reply functions (inbox / sidebar) -- kept for compat
# ──────────────────────────────────────────────────────────────

async def reply_to_inbox(platform_name: str, style: str = "auto") -> list:
    session = browser_sessions.get(platform_name)
    if not session:
        return []

    allowed, current, limit = await check_daily_limit(platform_name, "replies")
    if not allowed:
        logger.warning(f"Daily reply limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []

    platform = session["platform"]
    my_pseudo = MY_PROFILE.get("pseudo", "ilvousenprie").lower()
    conversations = await platform.get_inbox_conversations()
    replied = []

    for conv in conversations[:10]:
        try:
            sender_text = conv.get("text", "")
            sender_name = sender_text.split("\n")[0].strip() if sender_text else "Unknown"
            if sender_name.lower() == my_pseudo:
                continue

            async with await get_db() as db:
                cursor = await db.execute(
                    "SELECT id FROM activity_log WHERE platform = ? AND action = 'reply' AND target_name = ?",
                    (platform_name, sender_name)
                )
                if await cursor.fetchone():
                    logger.info(f"Already replied to {sender_name} before, skipping")
                    continue

            conv_data = await platform.open_chat_and_read(conv)
            if not conv_data:
                continue

            full_text = conv_data.get("fullText", "")
            if not full_text or len(full_text) < 10:
                continue
            if not conv_data.get("hasMessages"):
                continue

            meaningful_lines = filter_ui_text(full_text, sender_name)
            if len(meaningful_lines) < 1:
                logger.info(f"Chat with {sender_name} has no real message content, skipping")
                continue

            # Record received message in conversation history
            try:
                await record_conv_message(platform_name, sender_name, "received", full_text[:500])
            except Exception as e:
                logger.warning(f"Failed to record received message: {e}")

            reply = await generate_reply_message(
                sender_name=sender_name, conversation_text=full_text,
                style=style, platform=platform_name
            )
            if not reply:
                continue

            success = await platform.reply_in_chat(reply)
            if success:
                await _log_reply(platform_name, sender_name, reply, action="reply", style=style)
                await increment_daily_count(platform_name, "replies")
                replied.append({"name": sender_name, "reply": reply})
                logger.info(f"Replied to {sender_name}: {reply[:50]}...")

            # Re-check limit
            allowed, _, _ = await check_daily_limit(platform_name, "replies")
            if not allowed:
                logger.warning("Daily reply limit reached, stopping")
                break

            await _human_delay_with_pauses(2.0, 5.0)

        except Exception as e:
            logger.error(f"Error replying to conversation: {e}")

    return replied


async def reply_to_sidebar(platform_name: str, style: str = "auto") -> list:
    session = browser_sessions.get(platform_name)
    if not session:
        return []

    allowed, current, limit = await check_daily_limit(platform_name, "replies")
    if not allowed:
        logger.warning(f"Daily reply limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []

    platform = session["platform"]
    my_pseudo = MY_PROFILE.get("pseudo", "ilvousenprie").lower()
    conversations = await platform.get_sidebar_conversations()
    replied = []

    for conv in conversations[:30]:
        try:
            sender_name = conv.get("name", "Unknown")
            if sender_name.lower() == my_pseudo:
                continue

            async with await get_db() as db:
                cursor = await db.execute(
                    "SELECT id FROM activity_log WHERE platform = ? AND action IN ('reply', 'sidebar_reply') AND target_name = ?",
                    (platform_name, sender_name)
                )
                if await cursor.fetchone():
                    logger.info(f"Already replied to {sender_name} before, skipping")
                    continue

            conv_data = await platform.open_sidebar_chat(conv)
            if not conv_data:
                continue
            if conv_data.get("blocked"):
                logger.info(f"Message filters block us from {sender_name}, skipping")
                continue
            if not conv_data.get("hasMessages"):
                continue

            full_text = conv_data.get("fullText", "")
            if not full_text or len(full_text) < 10:
                continue

            meaningful_lines = filter_ui_text(full_text, sender_name)
            if len(meaningful_lines) < 1:
                logger.info(f"Sidebar chat with {sender_name} has no real message content, skipping")
                continue

            if my_pseudo in full_text.lower() and sender_name.lower() not in full_text.lower():
                logger.info(f"Sidebar chat with {sender_name}: only our messages, skipping")
                continue

            # Record received message in conversation history
            try:
                await record_conv_message(platform_name, sender_name, "received", full_text[:500])
            except Exception as e:
                logger.warning(f"Failed to record received message: {e}")

            reply = await generate_reply_message(
                sender_name=sender_name, conversation_text=full_text,
                style=style, platform=platform_name
            )
            if not reply:
                continue

            success = await platform.reply_in_sidebar_chat(reply)
            if success:
                await _log_reply(platform_name, sender_name, reply, action="sidebar_reply", style=style)
                await increment_daily_count(platform_name, "replies")
                replied.append({"name": sender_name, "reply": reply})
                logger.info(f"Sidebar replied to {sender_name}: {reply[:50]}...")

            # Re-check limit
            allowed, _, _ = await check_daily_limit(platform_name, "replies")
            if not allowed:
                logger.warning("Daily reply limit reached, stopping")
                break

            await _human_delay_with_pauses(2.0, 5.0)

        except Exception as e:
            logger.error(f"Error replying to sidebar conversation: {e}")

    return replied
