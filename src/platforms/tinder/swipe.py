"""Tinder swipe (Like / Nope / Super Like) + popup dismissal.

Per security review behavioral gaps:
- Keyboard-only swipe = #1 automation signal. Mix 30-40% mouse-drag variant.
- Zero dwell time on photos = bot. Add bimodal dwell distribution.
- Random inter-action jitter stays in swipe.like_profiles via delay_range.
"""

import asyncio
import logging
import random

from .selectors import (
    LIKE_BUTTON,
    NOPE_BUTTON,
    SUPER_LIKE_BUTTON,
    KEY_LIKE,
    KEY_NOPE,
    KEY_SUPER_LIKE,
    POPUP_DISMISS_FALLBACKS,
    OUT_OF_LIKES_TEXT,
    RATE_LIMIT_TEXT_FALLBACKS,
)

logger = logging.getLogger(__name__)

# Probability of swiping via mouse-drag instead of button/keyboard.
# Security review target: 30-40%. Random per-swipe.
MOUSE_DRAG_PROBABILITY = 0.35

# Dwell time distribution (seconds). Bimodal: fast-reject vs slow-browse.
# Real users vary — some profiles get a 3-4s look, others ~0.8s flick.
FAST_DWELL_RANGE = (0.6, 1.2)
SLOW_DWELL_RANGE = (2.0, 4.2)
SLOW_DWELL_PROBABILITY = 0.30


class TinderSwipeMixin:
    """Swipe actions. Mix button click + keyboard + mouse-drag per turn."""

    async def _dwell_on_card(self):
        """Pause as a human would, looking at photos/bio."""
        if random.random() < SLOW_DWELL_PROBABILITY:
            delay = random.uniform(*SLOW_DWELL_RANGE)
        else:
            delay = random.uniform(*FAST_DWELL_RANGE)
        await asyncio.sleep(delay)

    async def _mouse_drag_swipe(self, direction: str) -> bool:
        """Swipe via mouse drag on the card stack center.

        Simulates a finger-flick: mousedown at card center, mousemove across an
        arc with intermediate points, mouseup past the card edge.
        """
        try:
            viewport = self.page.viewport_size or {"width": 1440, "height": 900}
            cx = viewport["width"] // 2
            cy = viewport["height"] // 2
            end_x = cx + 420 if direction == "right" else cx - 420
            end_y = cy + random.randint(-40, 40)

            await self.page.mouse.move(cx, cy)
            await self.page.mouse.down()

            # Bezier-ish arc: 4 intermediate points
            steps = 6
            for i in range(1, steps + 1):
                t = i / steps
                # Slight vertical curve via sin
                import math
                mid_x = cx + (end_x - cx) * t
                mid_y = cy + (end_y - cy) * t + math.sin(t * math.pi) * 20
                await self.page.mouse.move(mid_x, mid_y, steps=3)
                await asyncio.sleep(random.uniform(0.02, 0.05))

            await self.page.mouse.up()
            return True
        except Exception as e:
            logger.debug(f"Mouse-drag swipe failed: {e}")
            return False

    async def _click_or_key(self, button_selector: str, key: str) -> bool:
        """Try clicking the button; fall back to keyboard press."""
        try:
            btn = await self.page.query_selector(button_selector)
            if btn:
                await btn.click()
                return True
        except Exception as e:
            logger.debug(f"Button click failed ({button_selector}): {e}")
        try:
            await self.page.keyboard.press(key)
            return True
        except Exception as e:
            logger.debug(f"Keyboard fallback failed ({key}): {e}")
            return False

    async def swipe_right(self) -> bool:
        if random.random() < MOUSE_DRAG_PROBABILITY:
            if await self._mouse_drag_swipe("right"):
                return True
        return await self._click_or_key(LIKE_BUTTON, KEY_LIKE)

    async def swipe_left(self) -> bool:
        if random.random() < MOUSE_DRAG_PROBABILITY:
            if await self._mouse_drag_swipe("left"):
                return True
        return await self._click_or_key(NOPE_BUTTON, KEY_NOPE)

    async def swipe_super(self) -> bool:
        return await self._click_or_key(SUPER_LIKE_BUTTON, KEY_SUPER_LIKE)

    async def _dismiss_popups(self):
        """Dismiss match popups, promotions, Gold upsells, etc."""
        for sel in POPUP_DISMISS_FALLBACKS:
            try:
                btn = await self.page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(0.4)
            except Exception as e:
                logger.debug(f"Popup dismiss ({sel}) failed: {e}")

    async def _is_rate_limited(self) -> bool:
        """Detect 'You've seen everyone' / out-of-likes modals."""
        try:
            body_text = await self.page.evaluate("document.body.innerText || ''")
        except Exception:
            return False
        if OUT_OF_LIKES_TEXT in body_text:
            return True
        for text in RATE_LIMIT_TEXT_FALLBACKS:
            if text in body_text:
                return True
        return False

    async def like_profiles(
        self,
        count: int,
        delay_range: tuple,
        profile_filter: str = "",
    ) -> list:
        """Swipe through up to `count` profiles, liking those that pass filter.

        For Phase 1, keeps the stub's simple 'like all' behavior. Scoring-based
        decisions are added in Phase 4. `profile_filter` is accepted for API
        compatibility (see action layer contract).
        """
        results = []
        for i in range(count):
            try:
                if await self._is_rate_limited():
                    logger.info("Tinder rate limit reached — stopping swipes")
                    break

                profile_info = await self._get_current_profile()

                # Dwell on the card as a human would before deciding.
                await self._dwell_on_card()

                liked = await self.swipe_right()
                profile_info["action"] = "like" if liked else "failed"
                results.append(profile_info)
                if liked:
                    logger.info(
                        f"Liked: {profile_info.get('name', 'Unknown')} "
                        f"({profile_info.get('age', '?')})"
                    )

                delay = random.uniform(delay_range[0], delay_range[1])
                await asyncio.sleep(delay)

                await self._dismiss_popups()

            except Exception as e:
                logger.error(f"Error swiping profile {i + 1}: {e}")
                await asyncio.sleep(2)

        return results
