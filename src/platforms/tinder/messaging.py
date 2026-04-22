"""Tinder messaging — match list parsing + send message to a match.

Per ENG review M2, match parsing is merged here (not a separate matches.py)
until it exceeds ~100 lines.
"""

import asyncio
import logging

from ...browser_utils import _human_type
from .selectors import (
    MATCHES_URL,
    MATCH_LINK,
    MATCH_NAME_FALLBACKS,
    MESSAGE_INPUT_FALLBACKS,
    SEND_BUTTON_FALLBACKS,
)

logger = logging.getLogger(__name__)


class TinderMessagingMixin:
    """Match list + send message flows."""

    async def get_matches(self) -> list:
        """List current matches. Returns [{id, name, href}, ...]."""
        matches = []
        try:
            await self.page.goto(MATCHES_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            match_els = await self.page.query_selector_all(MATCH_LINK)
            for el in match_els[:20]:
                try:
                    href = (await el.get_attribute("href")) or ""
                    match_id = href.rstrip("/").split("/")[-1] if "/" in href else ""
                    name = "Unknown"
                    for name_sel in MATCH_NAME_FALLBACKS:
                        try:
                            name_el = await el.query_selector(name_sel)
                            if name_el:
                                candidate = (await name_el.inner_text()).strip()
                                if candidate:
                                    name = candidate.split()[0]
                                    break
                        except Exception:
                            continue
                    if match_id:
                        matches.append({"id": match_id, "name": name, "href": href})
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error listing Tinder matches: {e}")

        return matches

    async def _find_message_input(self):
        for sel in MESSAGE_INPUT_FALLBACKS:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return el
            except Exception:
                continue
        return None

    async def _find_send_button(self):
        for sel in SEND_BUTTON_FALLBACKS:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return el
            except Exception:
                continue
        return None

    async def _type_and_send_in_current_chat(self, message: str) -> bool:
        """Type and send in the currently open chat. Assumes navigation done."""
        editor = await self._find_message_input()
        if not editor:
            logger.error("Message input not found in current chat")
            return False

        await editor.click()
        await asyncio.sleep(0.3)
        await _human_type(self.page, message)
        await asyncio.sleep(0.5)

        send_btn = await self._find_send_button()
        if send_btn:
            await send_btn.click()
        else:
            await self.page.keyboard.press("Enter")

        await asyncio.sleep(1)
        return True

    async def send_message(self, match_id: str, message: str) -> bool:
        """Open a match chat and send a message. Uses human-like typing."""
        try:
            url = f"https://tinder.com/app/messages/{match_id}"
            if not self.page.url.endswith(f"/messages/{match_id}"):
                await self.page.goto(
                    url, timeout=30000, wait_until="domcontentloaded"
                )
                await asyncio.sleep(2)

            ok = await self._type_and_send_in_current_chat(message)
            if ok:
                logger.info(f"Message sent to match {match_id}")
            return ok

        except Exception as e:
            logger.error(f"Error sending Tinder message to {match_id}: {e}")
            return False
