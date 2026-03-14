import asyncio
import logging
import random

from .base import BasePlatform

logger = logging.getLogger(__name__)


class TinderPlatform(BasePlatform):
    """Tinder web automation."""

    LOGIN_URL = "https://tinder.com"

    async def login_url(self) -> str:
        return self.LOGIN_URL

    async def open(self):
        self.page = await self.context.new_page()
        await self.page.goto(self.LOGIN_URL)

    async def is_logged_in(self) -> bool:
        try:
            await self.page.wait_for_selector(
                '[class*="recsCardboard"],'
                '[class*="matchListItem"],'
                'a[href*="/app/recs"]',
                timeout=5000
            )
            return True
        except Exception:
            return False

    async def like_profiles(self, count: int, delay_range: tuple) -> list:
        liked = []
        for i in range(count):
            try:
                profile_info = await self._get_current_profile()

                # Click like button (heart icon or keyboard shortcut)
                like_btn = await self.page.query_selector(
                    'button[class*="like"],'
                    '[aria-label*="Like"],'
                    '[aria-label*="J\'aime"]'
                )
                if like_btn:
                    await like_btn.click()
                else:
                    await self.page.keyboard.press("ArrowRight")

                profile_info["action"] = "like"
                liked.append(profile_info)
                logger.info(f"Liked: {profile_info.get('name', 'Unknown')}")

                # Random delay
                delay = random.uniform(delay_range[0], delay_range[1])
                await asyncio.sleep(delay)

                # Handle potential popups (match, super like promo, etc.)
                await self._dismiss_popups()

            except Exception as e:
                logger.error(f"Error liking profile {i+1}: {e}")
                await asyncio.sleep(2)

        return liked

    async def _get_current_profile(self) -> dict:
        """Extract info from the currently displayed profile."""
        info = {"name": "", "age": "", "bio": "", "interests": []}
        try:
            # Name and age
            name_el = await self.page.query_selector(
                '[class*="Typs(display-1-strong)"],'
                '[itemprop="name"],'
                'h1[class*="name"],'
                'span[class*="name"]'
            )
            if name_el:
                text = await name_el.inner_text()
                parts = text.strip().split()
                info["name"] = parts[0] if parts else ""

            age_el = await self.page.query_selector(
                '[class*="Typs(display-2-regular)"],'
                'span[class*="age"]'
            )
            if age_el:
                info["age"] = await age_el.inner_text()

            # Bio
            bio_el = await self.page.query_selector(
                '[class*="BreakWord"],'
                '[class*="bio"],'
                'div[class*="userBio"]'
            )
            if bio_el:
                info["bio"] = await bio_el.inner_text()

            # Interests/passions
            interest_els = await self.page.query_selector_all(
                '[class*="pill"],'
                '[class*="passion"],'
                '[class*="interest"]'
            )
            for el in interest_els[:5]:
                text = await el.inner_text()
                if text.strip():
                    info["interests"].append(text.strip())

        except Exception as e:
            logger.debug(f"Error extracting profile: {e}")

        return info

    async def _dismiss_popups(self):
        """Dismiss match popups, promotions, etc."""
        try:
            popup_selectors = [
                '[class*="matchAnimation"] button',
                'button[title*"Back"]',
                'button[aria-label*="Back"]',
                '[class*="modal"] button[class*="close"]',
            ]
            for sel in popup_selectors:
                btn = await self.page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(0.5)
        except Exception as e:
            logger.debug(f"Error dismissing popup: {e}")

    async def get_matches(self) -> list:
        matches = []
        try:
            await self.page.goto("https://tinder.com/app/matches")
            await asyncio.sleep(3)

            match_els = await self.page.query_selector_all(
                'a[href*="/app/messages/"],'
                '[class*="matchListItem"]'
            )
            for el in match_els[:10]:
                try:
                    name_el = await el.query_selector('[class*="name"], span')
                    name = await name_el.inner_text() if name_el else "Unknown"
                    href = await el.get_attribute("href") or ""
                    match_id = href.split("/")[-1] if "/" in href else ""
                    matches.append({"id": match_id, "name": name})
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error getting matches: {e}")

        return matches

    async def send_message(self, match_id: str, message: str) -> bool:
        try:
            await self.page.goto(f"https://tinder.com/app/messages/{match_id}")
            await asyncio.sleep(2)

            textarea = await self.page.query_selector(
                'textarea, [contenteditable="true"], input[type="text"]'
            )
            if not textarea:
                logger.error("Message input not found")
                return False

            await textarea.click()
            await textarea.fill(message)
            await asyncio.sleep(1)

            send_btn = await self.page.query_selector(
                'button[type="submit"],'
                'button[class*="send"],'
                '[aria-label*="Send"]'
            )
            if send_btn:
                await send_btn.click()
            else:
                await self.page.keyboard.press("Enter")

            await asyncio.sleep(1)
            logger.info(f"Message sent to {match_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending message to {match_id}: {e}")
            return False

    async def get_profile_info(self, profile_element) -> dict:
        return await self._get_current_profile()
