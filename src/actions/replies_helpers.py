import asyncio
import logging
from ..database import get_db
from ..browser_utils import (
    find_tiptap_editor, type_in_editor, click_send_button, debug_editors,
)

logger = logging.getLogger(__name__)


async def _log_rejection(platform_name, name):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            (platform_name, "rejected", name, "REJECTED - stop contact")
        )
        await db.commit()


async def _is_rejected(platform_name, name) -> bool:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM activity_log WHERE platform = ? AND action = 'rejected' AND target_name = ?",
            (platform_name, name)
        )
        return bool(await cursor.fetchone())


async def _replied_recently(platform_name, name, minutes=3) -> bool:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT message_sent FROM activity_log "
            "WHERE platform = ? AND target_name = ? AND action IN ('auto_reply', 'sidebar_reply', 'reply') "
            "AND created_at > datetime('now', '-' || ? || ' minutes') "
            "ORDER BY created_at DESC LIMIT 1",
            (platform_name, name, int(minutes))
        )
        return bool(await cursor.fetchone())


async def _get_last_sent_message(platform_name, name) -> str:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT message_sent FROM activity_log WHERE platform = ? AND target_name = ? "
            "AND message_sent IS NOT NULL ORDER BY created_at DESC LIMIT 1",
            (platform_name, name)
        )
        row = await cursor.fetchone()
    return row[0] if row else ""


async def _log_reply(platform_name, name, reply, action="sidebar_reply", style="auto"):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent, style) VALUES (?, ?, ?, ?, ?)",
            (platform_name, action, name, reply, style)
        )
        await db.commit()


async def _send_reply_in_editor(page, name, reply):
    """Find editor, type reply, click send. Returns True on success."""
    editor_pos = await find_tiptap_editor(page, min_width=80)
    if not editor_pos.get("found"):
        logger.warning(f"  [{name}] Editor not found")
        await debug_editors(page, name)
        return False

    logger.info(f"  [{name}] Editor at ({editor_pos['x']},{editor_pos['y']}) "
                f"{editor_pos['w']}x{editor_pos['h']}")
    await type_in_editor(page, editor_pos, reply)
    await click_send_button(page)
    await asyncio.sleep(2)
    return True


async def _close_sidebar_discussion(page, disc_name: str):
    try:
        closed = await page.evaluate("""(targetName) => {
            const allEls = document.querySelectorAll('button, div');
            for (const el of allEls) {
                const text = (el.innerText || '').trim().split('\\n')[0].trim();
                if (text !== targetName) continue;
                const rect = el.getBoundingClientRect();
                if (rect.x > 990 && rect.x < 1160 && rect.width > 150) {
                    el.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                    return {found: true, x: Math.round(rect.x + rect.width - 10), y: Math.round(rect.y + rect.height/2)};
                }
            }
            return {found: false};
        }""", disc_name)

        if closed.get("found"):
            await page.mouse.move(closed["x"], closed["y"])
            await asyncio.sleep(0.5)

            close_btn = await page.evaluate("""(targetY) => {
                const buttons = document.querySelectorAll('button, svg');
                for (const el of buttons) {
                    const rect = el.getBoundingClientRect();
                    if (Math.abs(rect.y - targetY) > 30) continue;
                    if (rect.x < 1150) continue;
                    const icon = el.querySelector ? el.querySelector('svg[data-icon="xmark"], svg[data-icon="times"]') : null;
                    const isClose = icon || (el.tagName === 'svg' && (el.dataset.icon === 'xmark' || el.dataset.icon === 'times'));
                    if (isClose || (rect.width < 25 && rect.height < 25 && rect.x > 1200)) {
                        if (el.click) el.click();
                        return true;
                    }
                }
                return false;
            }""", closed["y"])

            if close_btn:
                logger.info(f"    -> Discussion closed via X button")
                await asyncio.sleep(0.5)
                return

        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
        logger.info(f"    -> Discussion popup closed (Escape)")
    except Exception as e:
        logger.info(f"    -> Could not close discussion: {e}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
