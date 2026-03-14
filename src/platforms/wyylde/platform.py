"""Main WyyldePlatform class composing all mixins.

Core methods: open, is_logged_in, like_profiles, _click_follow, _click_crush,
_dismiss_popups, _click_button_by_text, get_inbox_conversations, open_chat_and_read.
"""

import asyncio
import random
import logging

from ..base import BasePlatform
from .profile import WyyldeProfileMixin
from .messaging import WyyldeMessagingMixin
from .search import WyyldeSearchMixin
from .sidebar import WyyldeSidebarMixin
from .selectors import (
    CHAT_PROFILE_BUTTON,
    MEMBER_LINK,
    FOLLOW_ICON,
    CRUSH_ICON,
    SEND_ICON,
    INBOX_CONV_LINK,
    ALL_TAB,
    MODAL_CLOSE,
    DISMISS_BUTTON,
    COOKIE_BUTTON,
    MAIN_CONTENT_MIN_X,
    MEMBER_LINK_MIN_X,
    LOGIN_URL,
    SEARCH_URL,
    MESSAGES_URL,
    MAILBOX_URL,
)

logger = logging.getLogger(__name__)


class WyyldePlatform(
    WyyldeProfileMixin,
    WyyldeMessagingMixin,
    WyyldeSearchMixin,
    WyyldeSidebarMixin,
    BasePlatform,
):
    """Wyylde web automation."""

    LOGIN_URL = LOGIN_URL
    SEARCH_URL = SEARCH_URL
    MESSAGES_URL = MESSAGES_URL
    MAILBOX_URL = MAILBOX_URL

    async def login_url(self) -> str:
        return self.LOGIN_URL

    async def open(self):
        self.page = await self.context.new_page()
        await self.page.goto(self.LOGIN_URL, timeout=60000, wait_until="domcontentloaded")

    async def is_logged_in(self) -> bool:
        try:
            url = self.page.url
            if "app.wyylde.com" in url and "/login" not in url:
                return True
            return False
        except Exception:
            return False

    async def like_profiles(self, count: int, delay_range: tuple, profile_filter: str = "") -> list:
        """Visit online profiles from the chat sidebar, follow + crush each."""
        liked = []

        # Navigate to dashboard where chat sidebar with online profiles is visible
        if "/dashboard" not in self.page.url:
            logger.info("Navigating to dashboard...")
            await self.page.goto(self.LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(5)

        # Get list of chat profiles (online users)
        profile_buttons_data = await self.page.evaluate(f"""() => {{
            return [...document.querySelectorAll('{CHAT_PROFILE_BUTTON}')]
                .map((b, idx) => ({{
                    text: b.innerText.trim(),
                    index: idx
                }}))
                .filter(p => p.text.length > 3);
        }}""")

        logger.info(f"Found {len(profile_buttons_data)} online profiles in chat sidebar")

        if not profile_buttons_data:
            logger.error("No online profiles found in chat sidebar")
            return liked

        # Filter by profile type
        if profile_filter:
            profile_buttons_data = [
                p for p in profile_buttons_data
                if profile_filter.lower() in p["text"].lower()
            ]
            logger.info(f"After filter '{profile_filter}': {len(profile_buttons_data)} profiles")

        if not profile_buttons_data:
            logger.error(f"No profiles matching filter '{profile_filter}'")
            return liked

        # For each profile: click -> find member link -> follow + crush -> go back
        target_profiles = profile_buttons_data[:count]

        for i, p in enumerate(target_profiles):
            idx = p["index"]
            try:
                lines = [l.strip() for l in p["text"].split("\n") if l.strip()]
                display_name = lines[0] if lines else "Unknown"
                logger.info(f"Processing profile {i + 1}/{len(target_profiles)}: {display_name}")

                # Click the chat profile button to open chat popup
                await self.page.evaluate(f"""() => {{
                    const buttons = document.querySelectorAll('{CHAT_PROFILE_BUTTON}');
                    if (buttons[{idx}]) buttons[{idx}].click();
                }}""")
                await asyncio.sleep(2)

                # Find and click the member link in the chat popup
                navigated = await self.page.evaluate(f"""() => {{
                    const links = [...document.querySelectorAll('{MEMBER_LINK}')];
                    for (const link of links) {{
                        const rect = link.getBoundingClientRect();
                        if (rect.x > {MEMBER_LINK_MIN_X} && rect.width > 0 && link.className.includes('flex')) {{
                            link.click();
                            return link.href;
                        }}
                    }}
                    let best = null;
                    let bestX = 0;
                    for (const link of links) {{
                        const rect = link.getBoundingClientRect();
                        if (rect.x > {MEMBER_LINK_MIN_X} && rect.width > 0 && rect.x > bestX) {{
                            bestX = rect.x;
                            best = link;
                        }}
                    }}
                    if (best) {{ best.click(); return best.href; }}
                    return null;
                }}""")

                if not navigated:
                    logger.info(f"No member link found for {display_name}, skipping")
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(1)
                    continue

                logger.info(f"Navigating to profile: {navigated}")

                # Wait for profile page to load
                for _ in range(10):
                    await asyncio.sleep(1)
                    if "/member/" in self.page.url:
                        break
                await asyncio.sleep(2)

                if "/member/" not in self.page.url:
                    logger.info(f"Failed to navigate to profile for {display_name}")
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(1)
                    continue

                profile_info = await self._get_current_profile()
                if not profile_info["name"]:
                    profile_info["name"] = display_name

                # Sometimes just browse the profile without any action (10%)
                if random.random() < 0.1:
                    logger.info(f"Just browsing profile: {display_name} (random skip)")
                    await asyncio.sleep(random.uniform(3, 8))
                    await self.page.goto(self.LOGIN_URL, timeout=15000, wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    continue

                # Follow (skip 20% of the time for variation)
                if random.random() > 0.2:
                    followed = await self._click_follow()
                    if followed:
                        logger.info(f"Followed: {display_name}")
                        profile_info["followed"] = True
                    else:
                        logger.info(f"Follow skipped: {display_name}")
                else:
                    logger.info(f"Follow randomly skipped: {display_name}")
                await asyncio.sleep(1)

                # Crush (skip 30% of the time for variation)
                if random.random() > 0.3:
                    crushed = await self._click_crush()
                    if crushed:
                        logger.info(f"Crushed: {display_name}")
                        profile_info["crushed"] = True
                    else:
                        logger.info(f"Crush skipped: {display_name}")
                else:
                    logger.info(f"Crush randomly skipped: {display_name}")
                await asyncio.sleep(1)

                profile_info["action"] = "like"
                liked.append(profile_info)

                await self._dismiss_popups()

                # Go back to dashboard
                await self.page.goto(self.LOGIN_URL, timeout=15000, wait_until="domcontentloaded")
                await asyncio.sleep(3)

                delay = random.uniform(delay_range[0], delay_range[1])
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Error on profile {i + 1}: {e}")
                try:
                    await self.page.goto(
                        self.LOGIN_URL, timeout=15000, wait_until="domcontentloaded"
                    )
                    await asyncio.sleep(3)
                except Exception:
                    pass

        # Return to dashboard
        try:
            await self.page.goto(self.LOGIN_URL, timeout=15000, wait_until="domcontentloaded")
        except Exception:
            pass

        return liked

    async def _click_button_by_text(self, text: str) -> bool:
        """Click a button matching exact text."""
        try:
            buttons = await self.page.query_selector_all("button")
            for btn in buttons:
                btn_text = await btn.inner_text()
                if btn_text.strip() == text:
                    await btn.click()
                    return True
        except Exception as e:
            logger.debug(f"Could not click '{text}': {e}")
        return False

    async def _click_follow(self) -> bool:
        """Click the follow/Suivre button on the profile page (not sidebar)."""
        try:
            result = await self.page.evaluate(f"""() => {{
                const buttons = [...document.querySelectorAll('button')];
                for (const btn of buttons) {{
                    const svg = btn.querySelector('{FOLLOW_ICON}');
                    if (!svg) continue;
                    const rect = btn.getBoundingClientRect();
                    if (rect.x < {MAIN_CONTENT_MIN_X}) continue;
                    const text = btn.innerText.trim().toLowerCase();
                    if (text.includes('plus suivre') || text.includes('ne plus')) return 'already';
                    btn.click();
                    return 'clicked';
                }}
                return 'not_found';
            }}""")
            if result == 'clicked':
                return True
            elif result == 'already':
                logger.info("Already following this profile")
            else:
                logger.debug("Follow button not found in main area")
        except Exception as e:
            logger.debug(f"Could not click follow: {e}")
        return False

    async def _click_crush(self) -> bool:
        """Click the crush/coup de coeur button on the profile page."""
        try:
            result = await self.page.evaluate(f"""() => {{
                const buttons = [...document.querySelectorAll('button')];
                for (const btn of buttons) {{
                    const svg = btn.querySelector('{CRUSH_ICON}');
                    if (!svg) continue;
                    const rect = btn.getBoundingClientRect();
                    if (rect.x < {MAIN_CONTENT_MIN_X}) continue;
                    btn.click();
                    return 'clicked';
                }}
                for (const btn of buttons) {{
                    if (btn.innerText.includes('coup de coeur')) {{
                        const rect = btn.getBoundingClientRect();
                        if (rect.x < {MAIN_CONTENT_MIN_X}) continue;
                        btn.click();
                        return 'clicked';
                    }}
                }}
                return 'not_found';
            }}""")
            if result == 'clicked':
                return True
            logger.debug("Crush button not found in main area")
        except Exception as e:
            logger.debug(f"Could not click crush: {e}")
        return False

    async def _dismiss_popups(self):
        """Dismiss any modal/cookie/misc popups."""
        try:
            popup_selectors = [MODAL_CLOSE, DISMISS_BUTTON, COOKIE_BUTTON]
            for sel in popup_selectors:
                btn = await self.page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(0.5)
        except Exception:
            pass

    async def get_inbox_conversations(self) -> list:
        """Get conversations from the mailbox inbox page."""
        conversations = []
        try:
            await self.page.goto(self.MAILBOX_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(5)

            # Click "Tous" tab
            await self.page.evaluate(f"""() => {{
                const btn = document.querySelector('{ALL_TAB}');
                if (btn) btn.click();
            }}""")
            await asyncio.sleep(2)

            await self.page.screenshot(path="/tmp/wyylde_mailbox.png")

            convs = await self.page.evaluate("""(sel) => {
                const results = [];
                const links = document.querySelectorAll(sel);
                for (const link of links) {
                    const rect = link.getBoundingClientRect();
                    if (rect.width < 50 || rect.height < 20) continue;
                    const text = (link.innerText || '').trim();
                    if (text.length < 3) continue;
                    results.push({
                        text: text.substring(0, 300),
                        href: link.href,
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    });
                }
                return results;
            }""", INBOX_CONV_LINK)

            logger.info(f"Mailbox inbox: {len(convs)} conversations found")
            for c in convs:
                name = c['text'].split('\n')[0]
                logger.info(f"  {name} -> {c.get('href', '')[:80]}")

            conversations = convs

        except Exception as e:
            logger.error(f"Error getting mailbox: {e}")

        return conversations

    async def open_chat_and_read(self, conv_data: dict) -> dict:
        """Open a mailbox conversation by navigating to its URL and read messages."""
        try:
            sender_text = conv_data.get("text", "")
            sender_name = sender_text.split("\n")[0].strip() if sender_text else "Unknown"
            href = conv_data.get("href", "")

            if href:
                await self.page.goto(href, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(4)

            # Read conversation content from message area (x > 600, w > 300)
            data = await self.page.evaluate("""() => {
                const result = {fullText: '', hasMessages: false, url: window.location.href};

                const allDivs = document.querySelectorAll('div');
                let bestText = '';
                for (const el of allDivs) {
                    const rect = el.getBoundingClientRect();
                    if (rect.x >= 580 && rect.x <= 650 && rect.width > 280 &&
                        rect.width < 400 && rect.y > 60) {
                        const text = (el.innerText || '').trim();
                        if (text.length > bestText.length) bestText = text;
                    }
                }

                result.fullText = bestText.trim().substring(0, 3000);
                result.hasMessages = result.fullText.length > 20;
                return result;
            }""")

            data["sender_name"] = sender_name
            logger.info(
                f"Mailbox conversation with {sender_name}: "
                f"hasMessages={data.get('hasMessages')}, "
                f"text={data.get('fullText', '')[:150]}..."
            )
            return data

        except Exception as e:
            logger.error(f"Error reading mailbox conversation: {e}")
            return {}
