import asyncio
import logging
import random

from .base import BasePlatform

logger = logging.getLogger(__name__)


class MeeticPlatform(BasePlatform):
    """Meetic web automation."""

    LOGIN_URL = "https://www.meetic.fr"

    async def login_url(self) -> str:
        return self.LOGIN_URL

    async def open(self):
        self.page = await self.context.new_page()
        await self.page.goto(self.LOGIN_URL)

    async def is_logged_in(self) -> bool:
        try:
            await self.page.wait_for_selector(
                '[class*="profile-card"],'
                '[class*="js-shuffle"],'
                'a[href*="/app/search"],'
                '[data-test*="shuffle"]',
                timeout=5000
            )
            return True
        except Exception:
            return False

    async def like_profiles(self, count: int, delay_range: tuple, profile_filter: str = "") -> list:
        liked = []

        # Go to shuffle/discovery
        try:
            await self.page.goto("https://www.meetic.fr/app/shuffle")
            await asyncio.sleep(3)
        except Exception as e:
            logger.debug(f"Error navigating to shuffle: {e}")

        for i in range(count):
            try:
                profile_info = await self._get_current_profile()

                # Click like/charm button
                like_btn = await self.page.query_selector(
                    'button[data-test*="like"],'
                    '[class*="like-btn"],'
                    '[class*="js-like"],'
                    'button[class*="charm"],'
                    '[aria-label*="Oui"],'
                    '[aria-label*="Like"]'
                )
                if like_btn:
                    await like_btn.click()
                else:
                    # Fallback: try clicking the heart icon
                    heart = await self.page.query_selector(
                        'svg[class*="heart"],'
                        '[class*="icon-heart"],'
                        '[class*="like"]'
                    )
                    if heart:
                        await heart.click()

                profile_info["action"] = "like"
                liked.append(profile_info)
                logger.info(f"Liked: {profile_info.get('name', 'Unknown')}")

                delay = random.uniform(delay_range[0], delay_range[1])
                await asyncio.sleep(delay)

                await self._dismiss_popups()

            except Exception as e:
                logger.error(f"Error liking profile {i+1}: {e}")
                await asyncio.sleep(2)

        return liked

    async def _get_current_profile(self) -> dict:
        info = {"name": "", "age": "", "bio": "", "interests": []}
        try:
            name_el = await self.page.query_selector(
                '[class*="profile-card__name"],'
                '[class*="username"],'
                'h1[class*="name"],'
                '[data-test*="name"]'
            )
            if name_el:
                info["name"] = (await name_el.inner_text()).strip()

            age_el = await self.page.query_selector(
                '[class*="profile-card__age"],'
                '[class*="age"],'
                '[data-test*="age"]'
            )
            if age_el:
                info["age"] = (await age_el.inner_text()).strip()

            bio_el = await self.page.query_selector(
                '[class*="profile-card__description"],'
                '[class*="about-me"],'
                '[class*="description"],'
                '[data-test*="description"]'
            )
            if bio_el:
                info["bio"] = (await bio_el.inner_text()).strip()

            interest_els = await self.page.query_selector_all(
                '[class*="tag"],'
                '[class*="interest"],'
                '[class*="hobby"]'
            )
            for el in interest_els[:5]:
                text = await el.inner_text()
                if text.strip():
                    info["interests"].append(text.strip())

        except Exception as e:
            logger.debug(f"Error extracting profile: {e}")

        return info

    async def _dismiss_popups(self):
        try:
            popup_selectors = [
                '[class*="modal"] button[class*="close"]',
                'button[class*="dismiss"]',
                '[class*="overlay"] button',
                '[class*="cookie"] button[class*="accept"]',
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
            await self.page.goto("https://www.meetic.fr/app/matches")
            await asyncio.sleep(3)

            match_els = await self.page.query_selector_all(
                'a[href*="/app/conversation/"],'
                '[class*="match-item"],'
                '[class*="conversation-item"]'
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
            await self.page.goto(
                f"https://www.meetic.fr/app/conversation/{match_id}"
            )
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
                '[aria-label*="Envoyer"]'
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
