"""Tinder profile extraction (current card in recs view)."""

import logging

from .selectors import (
    PROFILE_NAME_FALLBACKS,
    PROFILE_AGE_FALLBACKS,
    PROFILE_BIO_FALLBACKS,
    PROFILE_PASSIONS_FALLBACKS,
    PROFILE_DISTANCE_FALLBACKS,
)

logger = logging.getLogger(__name__)


class TinderProfileMixin:
    """Extract profile data from Tinder's current card."""

    async def _query_first(self, selectors: list):
        """Try a list of selectors, return the first matching element or None."""
        for sel in selectors:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return el
            except Exception:
                continue
        return None

    async def _get_current_profile(self) -> dict:
        """Extract info from the currently displayed profile card.

        Returns a dict with keys: name, age, bio, distance, passions (list),
        photo_count (int). Missing fields default to empty string / 0.
        """
        info = {
            "name": "",
            "age": "",
            "bio": "",
            "distance": "",
            "passions": [],
            "photo_count": 0,
        }
        try:
            name_el = await self._query_first(PROFILE_NAME_FALLBACKS)
            if name_el:
                text = (await name_el.inner_text()).strip()
                parts = text.split()
                info["name"] = parts[0] if parts else ""

            age_el = await self._query_first(PROFILE_AGE_FALLBACKS)
            if age_el:
                info["age"] = (await age_el.inner_text()).strip()

            bio_el = await self._query_first(PROFILE_BIO_FALLBACKS)
            if bio_el:
                info["bio"] = (await bio_el.inner_text()).strip()

            distance_el = await self._query_first(PROFILE_DISTANCE_FALLBACKS)
            if distance_el:
                info["distance"] = (await distance_el.inner_text()).strip()

            for sel in PROFILE_PASSIONS_FALLBACKS:
                try:
                    els = await self.page.query_selector_all(sel)
                    for el in els[:8]:
                        text = (await el.inner_text()).strip()
                        if text and len(text) < 40 and text not in info["passions"]:
                            info["passions"].append(text)
                    if info["passions"]:
                        break
                except Exception:
                    continue

            try:
                photos = await self.page.query_selector_all(
                    'div[aria-label*="photo"], [class*="profileCard"] img, [role="img"]'
                )
                info["photo_count"] = len(photos)
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Error extracting Tinder profile: {e}")

        return info

    async def get_profile_info(self, profile_element=None) -> dict:
        """BasePlatform hook — ignore element, extract current card."""
        return await self._get_current_profile()
