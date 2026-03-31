import asyncio
import logging
import random

logger = logging.getLogger(__name__)


async def _human_type(page, message: str):
    """Type message with human-like variable delays between keystrokes."""
    for i, char in enumerate(message):
        await page.keyboard.press(char if len(char) == 1 else char)
        # Base delay 20-70ms with occasional micro-pauses at word boundaries
        delay = random.uniform(0.020, 0.070)
        if char == " " and random.random() < 0.3:
            delay += random.uniform(0.05, 0.20)  # word boundary pause
        elif char in ".,!?" and random.random() < 0.5:
            delay += random.uniform(0.10, 0.30)  # punctuation pause
        await asyncio.sleep(delay)


async def _safe_goto(page, url, timeout=30000):
    """Navigate safely -- SPA may abort but page still loads via React router."""
    try:
        await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
    except Exception:
        pass
    await asyncio.sleep(3)
    if url.rstrip("/") not in page.url and "/dashboard" not in page.url:
        try:
            await page.evaluate("(u) => { window.location.href = u; }", url)
            await asyncio.sleep(4)
        except Exception:
            pass
    if url.rstrip("/") not in page.url and "/dashboard" not in page.url:
        try:
            await page.evaluate("(u) => { window.location.replace(u); }", url)
            await asyncio.sleep(5)
        except Exception:
            pass


async def find_tiptap_editor(page, min_width=80):
    """Find a visible TipTap/contenteditable editor and return its center position.
    Returns dict with {found, x, y, w, h} or {found: False}."""
    return await page.evaluate("""(minWidth) => {
        const tiptaps = document.querySelectorAll('div.tiptap.ProseMirror[contenteditable="true"]');
        for (const e of tiptaps) {
            const rect = e.getBoundingClientRect();
            if (rect.width > minWidth && rect.height > 0 && rect.y > 0) {
                return {found: true, x: Math.round(rect.x + rect.width/2),
                        y: Math.round(rect.y + rect.height/2),
                        w: Math.round(rect.width), h: Math.round(rect.height)};
            }
        }
        const divs = document.querySelectorAll('div[contenteditable="true"]');
        for (const d of divs) {
            const rect = d.getBoundingClientRect();
            if (rect.width > minWidth && rect.height > 0 && rect.y > 0) {
                return {found: true, x: Math.round(rect.x + rect.width/2),
                        y: Math.round(rect.y + rect.height/2),
                        w: Math.round(rect.width), h: Math.round(rect.height)};
            }
        }
        return {found: false};
    }""", min_width)


async def click_send_button(page):
    """Click the paper-plane-top send button. Returns True if clicked, else tries Enter."""
    sent = await page.evaluate("""() => {
        const buttons = [...document.querySelectorAll('button')];
        for (const btn of buttons) {
            const svg = btn.querySelector('svg[data-icon="paper-plane-top"]');
            if (svg && !btn.disabled && btn.getBoundingClientRect().width > 0) {
                btn.click(); return true;
            }
        }
        return false;
    }""")
    if not sent:
        await page.keyboard.press("Enter")
    return sent


async def type_in_editor(page, editor_pos, message):
    """Click on editor at given position and type message."""
    await page.mouse.click(editor_pos["x"], editor_pos["y"])
    await asyncio.sleep(0.5)
    await _human_type(page, message)
    await asyncio.sleep(1)


async def send_message_in_editor(page, message, min_width=80):
    """Find editor, type message, click send. Returns True on success."""
    editor_pos = await find_tiptap_editor(page, min_width=min_width)
    if not editor_pos.get("found"):
        return False
    await type_in_editor(page, editor_pos, message)
    await click_send_button(page)
    await asyncio.sleep(2)
    return True


async def read_chat_content(page, x_min=200, x_max=850, min_width=80, max_width=600):
    """Read the largest text block from a chat area. Returns dict or None."""
    return await page.evaluate("""(args) => {
        const [xMin, xMax, minW, maxW] = args;
        const candidates = [];
        const allDivs = document.querySelectorAll('div');
        for (const div of allDivs) {
            const rect = div.getBoundingClientRect();
            if (rect.width < minW || rect.width > maxW) continue;
            if (rect.height < 30) continue;
            if (rect.x < xMin || rect.x > xMax) continue;
            const text = (div.innerText || '').trim();
            if (text.length < 5) continue;
            candidates.push({text: text.substring(0, 3500), len: text.length,
                x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height)});
        }
        candidates.sort((a, b) => b.len - a.len);
        return candidates.length > 0 ? candidates[0] : null;
    }""", [x_min, x_max, min_width, max_width])


async def explore_profile_in_new_tab(context, page, target_name):
    """Open a member's profile in a new tab, extract info, close tab. Returns dict."""
    member_url = await page.evaluate("""(targetName) => {
        const links = document.querySelectorAll('a[href*="/member/"]');
        for (const a of links) {
            if ((a.innerText || '').trim().includes(targetName)) return a.href;
        }
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            const text = (btn.innerText || '').trim();
            if (!text.includes(targetName)) continue;
            const parent = btn.closest('a[href*="/member/"]');
            if (parent) return parent.href;
        }
        return null;
    }""", target_name)

    if not member_url:
        return {}

    logger.info(f"  [{target_name}] Exploring profile: {member_url}")
    profile_page = None
    try:
        profile_page = await context.new_page()
        await profile_page.goto(member_url, timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        profile_info = await profile_page.evaluate("""() => {
            const info = {};
            const body = document.body.innerText || '';
            const typeMatch = body.match(/(Couple[^\\n]{0,30}|Homme[^\\n]{0,30}|Femme[^\\n]{0,30})\\n/);
            if (typeMatch) info.type = typeMatch[1].trim();
            const ageMatch = body.match(/(\\d+(?:\\/\\d+)?\\s*ans)/);
            if (ageMatch) info.age = ageMatch[1];
            const locMatch = body.match(/kilomètres? - ([^\\n]+)/);
            if (locMatch) info.location = locMatch[1].trim();
            const allDivs = document.querySelectorAll('div, p, span');
            let bestBio = '';
            for (const el of allDivs) {
                const rect = el.getBoundingClientRect();
                if (rect.x < 300 || rect.x > 800) continue;
                if (rect.y < 300 || rect.y > 900) continue;
                if (rect.width < 200) continue;
                const text = (el.innerText || '').trim();
                if (text.length > 50 && text.length < 2000 && text.length > bestBio.length) {
                    if (!text.includes('Adhésion') && !text.includes('Adepte')) {
                        bestBio = text;
                    }
                }
            }
            if (bestBio) info.bio = bestBio.substring(0, 800);
            return info;
        }""")
        await profile_page.close()
        logger.info(f"  [{target_name}] Profile: type={profile_info.get('type', '?')} "
                    f"age={profile_info.get('age', '?')} bio={len(profile_info.get('bio', ''))}chars")
        return profile_info
    except Exception as e:
        logger.warning(f"  [{target_name}] Profile exploration failed: {e}")
        if profile_page:
            try:
                await profile_page.close()
            except Exception:
                pass
        return {}


async def debug_editors(page, name=""):
    """Log all editors on page for debugging. Returns the list."""
    editor_debug = await page.evaluate("""() => {
        const results = [];
        const allEditors = document.querySelectorAll(
            'div.tiptap.ProseMirror[contenteditable="true"], div[contenteditable="true"], [role="textbox"]'
        );
        for (const e of allEditors) {
            const rect = e.getBoundingClientRect();
            results.push({
                tag: e.tagName, classes: (e.className || '').substring(0, 120),
                x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                placeholder: e.getAttribute('data-placeholder') || '',
                visible: rect.width > 0 && rect.height > 0,
                isTiptap: e.classList.contains('tiptap') || e.classList.contains('ProseMirror')
            });
        }
        return results;
    }""")
    prefix = f"  [{name}] " if name else ""
    logger.info(f"{prefix}DEBUG EDITORS ({len(editor_debug)} found):")
    for ed in editor_debug:
        logger.info(f"  {prefix}{ed['tag']} x={ed['x']} y={ed['y']} {ed['w']}x{ed['h']} "
                     f"visible={ed['visible']} tiptap={ed.get('isTiptap')} "
                     f"placeholder='{ed['placeholder']}' "
                     f"classes='{ed['classes'][:80]}'")
    return editor_debug
