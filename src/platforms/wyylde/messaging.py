"""Messaging methods for Wyylde platform.

Mixin providing message sending via "Lui ecrire" modal,
legacy send_message wrapper, mailbox reply, sidebar chat reply,
and shared send button utility.
"""

import asyncio
import logging

from ...browser_utils import _human_type
from .selectors import (
    LUI_ECRIRE_ICON,
    SEND_ICON,
    TIPTAP_EDITOR,
    CONTENTEDITABLE_FALLBACK,
    MAIN_CONTENT_MIN_X,
)

logger = logging.getLogger(__name__)


class WyyldeMessagingMixin:
    """Message sending and replying methods for Wyylde."""

    async def send_message_from_profile(self, message: str, stay_on_profile: bool = False) -> bool:
        """Send a message from the current profile page via 'Lui ecrire'.
        Must already be on a /member/ page.
        If stay_on_profile=True, don't navigate away after sending."""
        try:
            if "/member/" not in self.page.url:
                logger.error("Not on a profile page")
                return False

            await self._dismiss_popups()

            # Click "Lui ecrire" button
            msg_clicked = await self.page.evaluate(f"""() => {{
                const buttons = [...document.querySelectorAll('button')];
                for (const btn of buttons) {{
                    const svg = btn.querySelector('{LUI_ECRIRE_ICON}');
                    const text = btn.innerText.trim().toLowerCase();
                    if (svg && (text.includes('crire') || text.includes('écrire'))) {{
                        const rect = btn.getBoundingClientRect();
                        if (rect.x > {MAIN_CONTENT_MIN_X} && rect.width > 0) {{
                            btn.click(); return 'clicked';
                        }}
                    }}
                }}
                return 'not_found';
            }}""")

            if msg_clicked == 'not_found':
                logger.error("'Lui ecrire' button not found")
                return False

            logger.info("Clicked 'Lui ecrire'")
            await self._dismiss_popups()
            await asyncio.sleep(2)
            await self.page.screenshot(path="/tmp/wyylde_after_lui_ecrire.png")

            # Find the message editor (modal or chat popup)
            editor_pos = await self._find_editor(wide_first=True)
            if not editor_pos:
                logger.error("Message editor not found")
                return False

            logger.info(
                f"Modal editor found at center ({editor_pos['x']}, {editor_pos['y']}), "
                f"width={editor_pos['w']}"
            )

            # Click directly on the editor using Playwright coordinates
            await self.page.mouse.click(editor_pos["x"], editor_pos["y"])
            await asyncio.sleep(0.5)

            # Type the message
            await _human_type(self.page, message)
            await asyncio.sleep(1)

            # Verify text was typed
            typed_text = await self.page.evaluate("""(sel) => {
                const editors = document.querySelectorAll(sel);
                let best = null, bestW = 0;
                for (const e of editors) {
                    const rect = e.getBoundingClientRect();
                    if (rect.width > bestW) { bestW = rect.width; best = e; }
                }
                return best ? best.innerText.trim() : '';
            }""", TIPTAP_EDITOR)
            logger.info(f"Editor content after typing: '{typed_text[:50]}...'")

            if not typed_text:
                logger.error("Text was not typed into editor")
                return False

            # Find and click the send button
            await asyncio.sleep(0.5)

            send_clicked = await self.page.evaluate(f"""() => {{
                const buttons = [...document.querySelectorAll('button')];

                // Find send button in the MODAL (not sidebar)
                for (const btn of buttons) {{
                    const svg = btn.querySelector('{SEND_ICON}');
                    if (!svg) continue;
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && !btn.disabled && rect.x < 920 && rect.x > {MAIN_CONTENT_MIN_X}) {{
                        btn.click();
                        return 'paper-plane-top-modal (' + Math.round(rect.x) + ',' + Math.round(rect.y) + ')';
                    }}
                }}

                // Fallback: any enabled paper-plane-top
                for (const btn of buttons) {{
                    const svg = btn.querySelector('{SEND_ICON}');
                    if (svg && !btn.disabled && btn.getBoundingClientRect().width > 0) {{
                        btn.click();
                        return 'paper-plane-top-any';
                    }}
                }}

                return 'not_found';
            }}""")

            if send_clicked == 'not_found':
                logger.info("Send button not found or disabled, trying Enter")
                await self.page.keyboard.press("Enter")
            else:
                logger.info(f"Clicked send: {send_clicked}")

            await asyncio.sleep(2)
            await self.page.screenshot(path="/tmp/wyylde_after_send.png")
            logger.info(f"Message sent via 'Lui ecrire' ({send_clicked})")

            # Check for confirmation
            await asyncio.sleep(1)
            confirmation = await self.page.evaluate("""(sel) => {
                const text = document.body.innerText || '';
                if (text.includes('Message envoyé')) return 'banner';
                const editors = document.querySelectorAll(sel);
                for (const e of editors) {
                    if (e.innerText.trim() === '') return 'editor_cleared';
                }
                return null;
            }""", TIPTAP_EDITOR)
            if confirmation:
                logger.info(f"Send confirmed: {confirmation}")
            else:
                logger.warning("No 'Message envoye' confirmation detected")

            if not stay_on_profile:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(1)
                await self.page.goto(self.LOGIN_URL, timeout=15000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
            else:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(1)

            return True

        except Exception as e:
            logger.error(f"Error sending message from profile: {e}")
            if not stay_on_profile:
                try:
                    await self.page.goto(
                        self.LOGIN_URL, timeout=15000, wait_until="domcontentloaded"
                    )
                    await asyncio.sleep(3)
                except Exception:
                    pass
            return False

    async def send_message(self, match_id: str, message: str) -> bool:
        """Legacy method -- navigate to profile and send message in one step."""
        profile = await self.navigate_to_profile(match_id)
        if not profile:
            return False
        return await self.send_message_from_profile(message)

    async def reply_in_chat(self, message: str) -> bool:
        """Reply in the currently open mailbox conversation.
        Finds the TipTap editor on the page."""
        try:
            editor_pos = await self._find_editor(wide_first=False)
            if not editor_pos:
                logger.error("Reply editor not found")
                return False

            logger.info(f"Chat editor at ({editor_pos['x']}, {editor_pos['y']}), w={editor_pos['w']}")

            await self.page.mouse.click(editor_pos["x"], editor_pos["y"])
            await asyncio.sleep(0.5)
            await _human_type(self.page, message)
            await asyncio.sleep(1)

            sent = await self._click_send_button()
            if not sent:
                await self.page.keyboard.press("Enter")

            await asyncio.sleep(2)
            logger.info(f"Chat reply sent ({len(message)} chars)")
            return True

        except Exception as e:
            logger.error(f"Error replying in chat: {e}")
            return False

    async def reply_in_sidebar_chat(self, message: str) -> bool:
        """Reply in the currently open chat popup.
        The chat popup has a TipTap editor (~x=705, y=747, w=222)
        and paper-plane-top send button (~x=940, y=753)."""
        try:
            # Find narrow TipTap editor in chat popup
            editor_pos = await self.page.evaluate("""(sel) => {
                const editors = document.querySelectorAll(sel.tiptap);
                for (const e of editors) {
                    const rect = e.getBoundingClientRect();
                    if (rect.width > 100 && rect.width < 350 && rect.height > 0) {
                        return {found: true, x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2), w: Math.round(rect.width)};
                    }
                }
                const divs = document.querySelectorAll(sel.fallback);
                for (const d of divs) {
                    const rect = d.getBoundingClientRect();
                    if (rect.width > 100 && rect.width < 350 && rect.height > 0) {
                        return {found: true, x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2), w: Math.round(rect.width)};
                    }
                }
                return {found: false};
            }""", {"tiptap": TIPTAP_EDITOR, "fallback": CONTENTEDITABLE_FALLBACK})

            if not editor_pos.get("found"):
                logger.error("Chat popup editor not found")
                return False

            logger.info(f"Chat editor at ({editor_pos['x']}, {editor_pos['y']}), w={editor_pos['w']}")

            await self.page.mouse.click(editor_pos["x"], editor_pos["y"])
            await asyncio.sleep(0.5)
            await _human_type(self.page, message)
            await asyncio.sleep(1)

            sent = await self._click_send_button()
            if not sent:
                await self.page.keyboard.press("Enter")

            await asyncio.sleep(2)
            logger.info(f"Chat reply sent ({len(message)} chars)")
            return True

        except Exception as e:
            logger.error(f"Error replying in chat: {e}")
            return False

    async def _click_send_button(self) -> bool:
        """Click the paper-plane-top send button (shared by chat and modal)."""
        return await self.page.evaluate(f"""() => {{
            const buttons = [...document.querySelectorAll('button')];
            for (const btn of buttons) {{
                const svg = btn.querySelector('{SEND_ICON}');
                if (!svg) continue;
                const rect = btn.getBoundingClientRect();
                if (!btn.disabled && rect.width > 0) {{
                    btn.click();
                    return true;
                }}
            }}
            return false;
        }}""")

    async def _find_editor(self, wide_first: bool = True) -> dict | None:
        """Find a TipTap editor on the page. Retries up to 5 times.
        If wide_first=True, prefer wide modal editor; otherwise any editor."""
        for attempt in range(5):
            editor_pos = await self.page.evaluate("""(sel) => {
                const editors = document.querySelectorAll(sel.tiptap);
                // Wide modal editor
                for (const e of editors) {
                    const rect = e.getBoundingClientRect();
                    if (rect.width > 400 && rect.x < 700 && rect.x > 200 && rect.height > 0) {
                        return {found: true, x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2), w: Math.round(rect.width)};
                    }
                }
                // Chat popup editor (narrow)
                for (const e of editors) {
                    const rect = e.getBoundingClientRect();
                    if (rect.width > 100 && rect.width < 350 && rect.height > 0) {
                        return {found: true, x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2), w: Math.round(rect.width)};
                    }
                }
                // Fallback: any contenteditable
                const divs = document.querySelectorAll(sel.fallback);
                for (const div of divs) {
                    const rect = div.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 0) {
                        return {found: true, x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2), w: Math.round(rect.width)};
                    }
                }
                return {found: false};
            }""", {"tiptap": TIPTAP_EDITOR, "fallback": CONTENTEDITABLE_FALLBACK})

            if editor_pos.get("found"):
                return editor_pos

            logger.info(f"Editor not found (attempt {attempt + 1}/5), waiting...")
            await self._dismiss_popups()
            await asyncio.sleep(2)

        return None
