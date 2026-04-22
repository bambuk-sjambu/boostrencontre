"""Tinder-specific reply flow.

Tinder has no chat sidebar and no inbox like Wyylde. Replies work by iterating
the match list at `/app/messages`, detecting matches with unread indicators
(red dot / bold text / distinct styling), opening each, reading the last
message from them, and replying.

Dispatched from:
  actions/replies_inbox.py::reply_to_inbox       (platform == "tinder")
  actions/replies_unread.py::check_and_reply_unread  (platform == "tinder")
  actions/replies_unread.py::reply_to_unread_sidebar (platform == "tinder")
"""

import asyncio
import logging

from ..session_manager import browser_sessions
from ..database import get_db
from ..conversation_utils import _human_delay_with_pauses, check_rejection
from ..rate_limiter import check_daily_limit, increment_daily_count
from ..messaging.ai_messages import generate_reply_message, MY_PROFILE
from ..messaging.conversation_manager import record_message as record_conv_message
from .replies_helpers import (
    _is_rejected, _replied_recently, _log_reply, _log_rejection,
)
from ..platforms.tinder.selectors import MATCHES_URL, MATCH_LINK

logger = logging.getLogger(__name__)


async def _list_unread_matches(page) -> list:
    """Return [{id, name, href}] for matches currently showing an unread indicator.

    Tinder Web marks unread via:
    - a dot element inside the match row (class varies; we match on position / tag)
    - bold text styling on the name
    - the `aria-label` on the link often includes "unread" or "new"
    """
    try:
        await page.goto(MATCHES_URL, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
    except Exception as e:
        logger.error(f"Failed to load Tinder matches page: {e}")
        return []

    try:
        unread = await page.evaluate(r"""(selector) => {
            const results = [];
            const links = document.querySelectorAll(selector);
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                const parts = href.replace(/\/$/, '').split('/');
                const id = parts[parts.length - 1] || '';
                if (!id) continue;

                let name = '';
                const nameEl = a.querySelector('[class*="name"], span, h3');
                if (nameEl) {
                    name = (nameEl.innerText || '').trim().split('\n')[0].trim();
                }
                if (!name) name = 'Unknown';

                // Unread heuristics
                const aria = (a.getAttribute('aria-label') || '').toLowerCase();
                const hasAriaUnread = aria.includes('unread') || aria.includes('new message');

                // Red dot / badge detection via computed style
                let hasDot = false;
                const dots = a.querySelectorAll('div, span');
                for (const d of dots) {
                    const r = d.getBoundingClientRect();
                    if (r.width > 0 && r.width < 16 && r.height > 0 && r.height < 16) {
                        const bg = getComputedStyle(d).backgroundColor || '';
                        if (bg.match(/rgb\(\s*255\s*,\s*[0-9]+\s*,\s*[0-9]+\s*\)/) && bg !== 'rgba(0, 0, 0, 0)') {
                            hasDot = true;
                            break;
                        }
                    }
                }

                // Bold name text styling
                let isBold = false;
                if (nameEl) {
                    const fw = getComputedStyle(nameEl).fontWeight || '';
                    isBold = (parseInt(fw, 10) >= 600) || fw === 'bold';
                }

                const unread = hasAriaUnread || hasDot || isBold;
                if (unread) {
                    results.push({id, name, href, unread: true});
                }
            }
            return results;
        }""", MATCH_LINK)
        return unread or []
    except Exception as e:
        logger.error(f"Error parsing Tinder unread matches: {e}")
        return []


async def _read_last_received_message(page) -> str:
    """Extract the most recent message the match sent us from the open chat."""
    try:
        return await page.evaluate(r"""() => {
            // Message bubbles usually have aria-label or specific class patterns.
            // Received messages are typically on the left, sent on the right.
            const bubbles = document.querySelectorAll('[class*="msg"], [class*="message"], [role="listitem"]');
            let lastReceived = '';
            for (const b of bubbles) {
                const r = b.getBoundingClientRect();
                const text = (b.innerText || '').trim();
                if (!text || text.length < 2) continue;
                // Heuristic: received messages are left-aligned (x < viewport/2)
                if (r.x < window.innerWidth / 2) {
                    lastReceived = text;
                }
            }
            return lastReceived;
        }""")
    except Exception as e:
        logger.debug(f"Failed to read last received message: {e}")
        return ""


async def reply_to_tinder_matches(platform_name: str, style: str = "auto") -> list:
    """Main Tinder reply entry point. Iterates unread matches, sends one reply each."""
    session = browser_sessions.get(platform_name)
    if not session:
        logger.warning(f"No browser session for {platform_name}")
        return []

    allowed, current, limit = await check_daily_limit(platform_name, "replies")
    if not allowed:
        logger.warning(
            f"Daily reply limit reached ({current}/{limit}) for {platform_name}, aborting"
        )
        return []

    platform = session["platform"]
    page = platform.page
    my_pseudo = (MY_PROFILE.get("pseudo", "") or "").lower()
    replied = []

    unread = await _list_unread_matches(page)
    logger.info(f"Tinder: found {len(unread)} unread matches")

    for match in unread:
        if current + len(replied) >= limit:
            logger.info("Tinder reply limit reached mid-run")
            break

        name = match.get("name", "").strip()
        match_id = match.get("id", "").strip()
        if not match_id or not name:
            continue
        if name.lower() == my_pseudo:
            continue

        if await _is_rejected(platform_name, name):
            logger.info(f"Tinder: {name} rejected, skipping")
            continue

        if await _replied_recently(platform_name, name, minutes=120):
            logger.info(f"Tinder: already replied to {name} recently, skipping")
            continue

        try:
            await page.goto(
                f"https://tinder.com/app/messages/{match_id}",
                timeout=30000, wait_until="domcontentloaded",
            )
            await asyncio.sleep(3)

            last_msg = await _read_last_received_message(page)
            if not last_msg or len(last_msg) < 2:
                logger.info(f"Tinder: {name} has no readable last message, skipping")
                continue

            if check_rejection(last_msg):
                logger.info(f"Tinder: rejection detected from {name}")
                await _log_rejection(platform_name, name)
                continue

            try:
                await record_conv_message(platform_name, name, "received", last_msg[:500])
            except Exception as e:
                logger.debug(f"record_conv_message failed for {name}: {e}")

            reply = await generate_reply_message(
                name, last_msg, style=style, platform=platform_name
            )
            if not reply:
                logger.warning(f"Tinder: no reply generated for {name}")
                continue

            # Type + send in the currently open chat (avoid re-navigation)
            success = await platform._type_and_send_in_current_chat(reply)
            if not success:
                logger.warning(f"Tinder: failed to send reply to {name}")
                continue

            await _log_reply(platform_name, name, reply, action="reply", style=style)
            await increment_daily_count(platform_name, "replies")

            try:
                await record_conv_message(platform_name, name, "sent", reply[:500])
            except Exception as e:
                logger.debug(f"record_conv_message (sent) failed for {name}: {e}")

            replied.append({"name": name, "reply": reply, "match_id": match_id})
            logger.info(f"Tinder: replied to {name}: {reply[:60]}...")

            await _human_delay_with_pauses(3.0, 8.0)

        except Exception as e:
            logger.error(f"Tinder reply error for {name}: {e}")

    return replied
