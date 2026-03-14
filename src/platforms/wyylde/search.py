"""Search-based navigation for Wyylde platform.

Mixin providing search filter application, result extraction,
result clicking, and profile arrow navigation.
"""

import asyncio
import logging

from .selectors import (
    MEMBER_LINK,
    SEARCH_SUBMIT,
    NEXT_PROFILE_ICON,
    SEARCH_URL,
)

logger = logging.getLogger(__name__)


class WyyldeSearchMixin:
    """Search and result navigation methods for Wyylde."""

    async def apply_search_filters(self, profile_type: str = "", desires: list = None) -> bool:
        """Apply search filters on the search page.
        profile_type: 'couple', 'femme', 'homme', etc.
        desires: list of desires like ['Gang bang', 'Echangisme']"""
        if "/search" not in self.page.url:
            await self.page.goto(SEARCH_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

        # Reset all filters
        await self.page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                if (btn.innerText.trim() === 'Effacer') { btn.click(); return; }
            }
        }""")
        await asyncio.sleep(2)

        # Open "Criteres principaux" tab
        await self.page.evaluate("""() => {
            const tabs = document.querySelectorAll('b, span, div, button');
            for (const tab of tabs) {
                const text = (tab.innerText || '').trim();
                if (text.includes('Critères') && text.includes('principaux')) {
                    tab.click(); return;
                }
            }
        }""")
        await asyncio.sleep(1)

        # Apply profile type filter
        if profile_type:
            applied = await self.page.evaluate("""(targetType) => {
                const labels = document.querySelectorAll('label, span, div');
                for (const label of labels) {
                    const text = (label.innerText || '').trim().toLowerCase();
                    if (text.includes(targetType.toLowerCase())) {
                        const rect = label.getBoundingClientRect();
                        if (rect.x > 400 && rect.x < 600 && rect.width > 0) {
                            const checkbox = label.querySelector('input[type="checkbox"]') ||
                                           label.previousElementSibling;
                            if (checkbox && checkbox.type === 'checkbox') {
                                checkbox.click();
                                return 'checkbox';
                            }
                            label.click();
                            return 'label';
                        }
                    }
                }
                return null;
            }""", profile_type)
            logger.info(f"Profile type filter '{profile_type}': {applied}")
            await asyncio.sleep(1)

        # Apply desire filters
        if desires:
            await self.page.evaluate("""() => {
                const tabs = document.querySelectorAll('b, span, div, button');
                for (const tab of tabs) {
                    const text = (tab.innerText || '').trim();
                    if (text === 'Envies') {
                        tab.click(); return;
                    }
                }
            }""")
            await asyncio.sleep(2)

            for desire in desires:
                await self.page.evaluate("""(targetDesire) => {
                    const labels = document.querySelectorAll('label, span, div');
                    for (const label of labels) {
                        const text = (label.innerText || '').trim().toLowerCase();
                        if (text.includes(targetDesire.toLowerCase())) {
                            const rect = label.getBoundingClientRect();
                            if (rect.x > 400 && rect.x < 600 && rect.width > 0) {
                                const checkbox = label.querySelector('input[type="checkbox"]') ||
                                               label.previousElementSibling;
                                if (checkbox && checkbox.type === 'checkbox') {
                                    checkbox.click();
                                    return;
                                }
                                label.click();
                                return;
                            }
                        }
                    }
                }""", desire)
                await asyncio.sleep(0.5)

            logger.info(f"Desire filters applied: {desires}")

        # Submit search
        await self.page.evaluate(f"""() => {{
            const submit = document.querySelector('{SEARCH_SUBMIT}');
            if (submit) submit.click();
        }}""")
        await asyncio.sleep(3)

        # Close filter panel
        await self.page.keyboard.press("Escape")
        await asyncio.sleep(1)

        logger.info(f"Search filters applied: type={profile_type}, desires={desires}")
        return True

    async def get_search_results(self) -> list:
        """Navigate to search page and extract profile links from results."""
        if "/search" not in self.page.url:
            await self.page.goto(SEARCH_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(4)

        # Close filter panel if open
        await self.page.keyboard.press("Escape")
        await asyncio.sleep(1)

        profiles = await self.page.evaluate("""(sel) => {
            const results = [];
            const seen = new Set();
            const links = document.querySelectorAll(sel);
            for (const a of links) {
                const rect = a.getBoundingClientRect();
                if (rect.x < 330 || rect.x > 960 || rect.width < 50 || rect.y < 60) continue;
                const href = a.href;
                if (seen.has(href)) continue;
                seen.add(href);
                const text = (a.innerText || '').trim().substring(0, 200);
                results.push({href, text, x: Math.round(rect.x), y: Math.round(rect.y)});
            }
            return results;
        }""", MEMBER_LINK)

        logger.info(f"Search results: {len(profiles)} profiles found")
        return profiles

    async def click_search_result(self, index: int = 0) -> bool:
        """Click a search result by index to navigate to their profile."""
        results = await self.get_search_results()
        if index >= len(results):
            logger.error(f"Search result index {index} out of range ({len(results)} results)")
            return False

        href = results[index]["href"]
        await self.page.goto(href, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        if "/member/" not in self.page.url:
            logger.error(f"Failed to navigate to profile: {self.page.url}")
            return False

        logger.info(f"Navigated to search result {index}: {href}")
        return True

    async def go_to_next_profile(self) -> bool:
        """Click the right arrow at top of profile to go to next search result.
        Returns True if navigation succeeded."""
        if "/member/" not in self.page.url:
            return False

        clicked = await self.page.evaluate("""(sel) => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const svg = btn.querySelector(sel);
                if (!svg) continue;
                const rect = btn.getBoundingClientRect();
                if (rect.y < 60 && rect.x > 280 && rect.width > 0) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }""", NEXT_PROFILE_ICON)

        if not clicked:
            logger.info("Next profile arrow not found")
            return False

        await asyncio.sleep(3)
        logger.info(f"Navigated to next profile: {self.page.url}")
        return True
