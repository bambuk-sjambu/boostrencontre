"""Main TinderPlatform class — composes mixins, implements core methods.

Mirrors the Wyylde package structure. Phase 1: minimal refactor of the
existing 193-line `src/platforms/tinder.py` into a package. Later phases add
stealth (2), explorer-mapped selectors (3), swipe+profile polish (4),
full messaging (5), dashboard wiring (6), tests (7), dogfood (8).
"""

import asyncio
import logging

from ..base import BasePlatform
from .profile import TinderProfileMixin
from .swipe import TinderSwipeMixin
from .messaging import TinderMessagingMixin
from .selectors import LOGIN_URL, RECS_URL, MESSAGES_URL

logger = logging.getLogger(__name__)


class TinderPlatform(
    TinderProfileMixin,
    TinderSwipeMixin,
    TinderMessagingMixin,
    BasePlatform,
):
    """Tinder Web automation (desktop Chromium via Playwright)."""

    LOGIN_URL = LOGIN_URL
    RECS_URL = RECS_URL
    MESSAGES_URL = MESSAGES_URL

    def __init__(self, browser_context):
        super().__init__(browser_context)
        self._current_match_id = None

    async def login_url(self) -> str:
        return self.LOGIN_URL

    async def open(self):
        self.page = await self.context.new_page()
        await self.page.goto(
            self.LOGIN_URL, timeout=60000, wait_until="domcontentloaded"
        )

    async def is_logged_in(self) -> bool:
        """Detect logged-in state by checking for recs/matches anchors.

        Tinder Web's React SPA keeps the URL on tinder.com after login; we rely
        on DOM anchors that only exist when authenticated.
        """
        try:
            url = self.page.url or ""
            if "/app/" in url:
                return True
            await self.page.wait_for_selector(
                'a[href*="/app/recs"], a[href*="/app/matches"]',
                timeout=3000,
            )
            return True
        except Exception:
            return False

    async def navigate_to_profile(self, match_id: str) -> dict:
        """Navigate to a match's chat page and read any visible profile info.

        Tinder doesn't expose a separate pre-match profile page, so for a
        match we open the chat and extract whatever the chat header shows
        (name, age, photo). Stores `match_id` for a subsequent
        `send_message_from_profile` call.
        """
        url = f"https://tinder.com/app/messages/{match_id}"
        try:
            await self.page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            self._current_match_id = match_id
        except Exception as e:
            logger.error(f"navigate_to_profile failed for {match_id}: {e}")
            return {}

        info = await self._get_current_profile()
        if match_id and not info.get("name"):
            info["name"] = ""
        return info

    async def send_message_from_profile(
        self, message: str, stay_on_profile: bool = False
    ) -> bool:
        """Send a message in the currently open chat (post `navigate_to_profile`).

        `stay_on_profile` is accepted for action-layer API compatibility with
        Wyylde; it's a no-op on Tinder (chat page is the only relevant view).
        """
        if not self._current_match_id:
            logger.error("send_message_from_profile called without prior navigate_to_profile")
            return False
        return await self.send_message(self._current_match_id, message)
