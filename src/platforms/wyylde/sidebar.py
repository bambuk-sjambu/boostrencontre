"""Chat sidebar methods for Wyylde platform.

Mixin providing sidebar visibility, discussion list management,
conversation listing, chat opening, and online profile listing.
"""

import asyncio
import logging

from .selectors import (
    CHAT_PROFILE_BUTTON,
    CHAT_SIDEBAR_MIN_X,
    CHAT_SIDEBAR_MAX_X,
    LOGIN_URL,
)

logger = logging.getLogger(__name__)


class WyyldeSidebarMixin:
    """Chat sidebar interaction methods for Wyylde."""

    async def _ensure_chat_sidebar_visible(self):
        """Make sure we're on dashboard and chat sidebar is visible."""
        if "/dashboard" not in self.page.url and "/member/" not in self.page.url:
            await self.page.goto(LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(5)

    async def _open_discussions_list(self):
        """Click 'Discussions en cours' button to expand the discussions list."""
        await self.page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                const text = (btn.innerText || '').trim();
                if (text.match(/\\d+\\s+Discussions\\s+(en cours|non lues)/)) {
                    btn.click();
                    return true;
                }
            }
            // Fallback: look for the button by position
            for (const btn of btns) {
                const text = (btn.innerText || '').trim();
                const rect = btn.getBoundingClientRect();
                if (text.includes('Discussions') && rect.x > 900) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }""")
        await asyncio.sleep(2)

    async def get_sidebar_conversations(self) -> list:
        """Get conversations from the chat sidebar 'Discussions en cours'."""
        conversations = []
        try:
            await self._ensure_chat_sidebar_visible()
            await self._open_discussions_list()

            convs = await self.page.evaluate(f"""() => {{
                const results = [];
                const seen = new Set();
                const allEls = document.querySelectorAll('button, div, span, a');
                for (const el of allEls) {{
                    const rect = el.getBoundingClientRect();
                    const text = (el.innerText || '').trim();
                    if (rect.x < {CHAT_SIDEBAR_MIN_X} || rect.x > {CHAT_SIDEBAR_MAX_X}) continue;
                    if (rect.height > 45 || rect.height < 8 || rect.width < 30) continue;
                    if (text.length < 3 || text.length > 40) continue;
                    if (text.match(/(Homme|Femme|Couple|Travesti|Gay|Transgenre|Discussion|contact|Près|Chat|Recherche|LIVE|voyeur|\\d+\\s*ans|#LCS|New)/i)) continue;
                    if (seen.has(text)) continue;
                    seen.add(text);
                    results.push({{
                        name: text,
                        x: Math.round(rect.x), y: Math.round(rect.y),
                        w: Math.round(rect.width), h: Math.round(rect.height),
                        tag: el.tagName
                    }});
                }}
                return results;
            }}""")

            logger.info(f"Chat sidebar: {len(convs)} discussions found")
            for c in convs[:10]:
                logger.info(f"  {c['name']}")

            conversations = convs

        except Exception as e:
            logger.error(f"Error getting sidebar conversations: {e}")

        return conversations

    async def open_sidebar_chat(self, conv: dict) -> dict:
        """Open a sidebar chat by clicking the discussion name.
        This opens a chat popup with messages."""
        try:
            name = conv.get("name", "")

            # Click the discussion name in the sidebar list
            clicked = False
            for sel_type in ['button', 'div', 'span']:
                try:
                    loc = self.page.locator(f'{sel_type}:text-is("{name}")')
                    count = await loc.count()
                    for i in range(count):
                        box = await loc.nth(i).bounding_box()
                        if box and box["x"] > 1000 and box["x"] < 1200 and box["height"] < 50:
                            await loc.nth(i).scroll_into_view_if_needed()
                            await asyncio.sleep(0.3)
                            await loc.nth(i).click()
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception:
                    continue

            if not clicked:
                logger.error(f"Could not find sidebar element for {name}")
                return {}

            await asyncio.sleep(3)

            # Read messages from the chat popup
            data = await self.page.evaluate("""(targetName) => {
                const result = {fullText: '', hasMessages: false, blocked: false};

                // Check for blocking filter
                const allText = document.body.innerText || '';
                if (allText.includes('filtres des messages de ce membre')) {
                    result.blocked = true;
                    return result;
                }

                // Find chat popup container with contact name and messages
                const candidates = [];
                const allDivs = document.querySelectorAll('div');
                for (const div of allDivs) {
                    const rect = div.getBoundingClientRect();
                    if (rect.width < 150 || rect.width > 350) continue;
                    if (rect.height < 100) continue;
                    const text = (div.innerText || '').trim();
                    if (text.length < 20) continue;
                    if (!text.includes(targetName)) continue;
                    candidates.push({
                        text, len: text.length,
                        x: rect.x, y: rect.y, h: rect.height, w: rect.width
                    });
                }

                candidates.sort((a, b) => b.len - a.len);
                if (candidates.length > 0) {
                    const best = candidates[0];
                    result.fullText = best.text.substring(0, 3000);
                    const hasTimestamp = best.text.match(/(Aujourd|Hier|\\d{2}:\\d{2}|à \\d)/);
                    const hasLength = best.text.length > (targetName.length + 50);
                    result.hasMessages = !!(hasTimestamp || hasLength);
                }

                return result;
            }""", name)

            data["sender_name"] = name
            logger.info(
                f"Sidebar chat with {name}: hasMessages={data.get('hasMessages')}, "
                f"blocked={data.get('blocked')}, text={data.get('fullText', '')[:150]}..."
            )
            return data

        except Exception as e:
            logger.error(f"Error opening sidebar chat {conv.get('name')}: {e}")
            return {}

    async def get_matches(self) -> list:
        """Get online profiles from chat sidebar (dashboard).
        These are the profiles we can message via 'Lui ecrire'."""
        matches = []
        try:
            if "/dashboard" not in self.page.url:
                await self.page.goto(LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(5)

            logger.info(f"Dashboard page URL: {self.page.url}")

            profiles = await self.page.evaluate(f"""() => {{
                const buttons = document.querySelectorAll('{CHAT_PROFILE_BUTTON}');
                return [...buttons].map((b, idx) => ({{
                    text: b.innerText.trim(),
                    index: idx
                }})).filter(p => p.text.length > 3);
            }}""")

            logger.info(f"Found {len(profiles)} online profiles in chat sidebar")

            for p in profiles[:10]:
                lines = [l.strip() for l in p["text"].split("\n") if l.strip()]
                name = lines[0] if lines else "Unknown"
                matches.append({"id": str(p["index"]), "name": name})

        except Exception as e:
            logger.error(f"Error getting matches: {e}")

        return matches
