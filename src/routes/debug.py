"""Debug and exploration routes. Only included when DEBUG=true."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import bot_engine
from ..database import get_db
from ..explorer import explore_site
from .deps import validate_platform

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debug/{platform}")
async def debug_page(platform: str):
    """Capture current page info for selector debugging."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    url = page.url

    info = await page.evaluate("""() => {
        const results = {};
        results.links = [...document.querySelectorAll('a[href]')].slice(0, 100).map(a => ({
            href: a.href,
            text: a.innerText.trim().substring(0, 80),
            classes: a.className.substring(0, 120)
        }));
        results.buttons = [...document.querySelectorAll('button')].slice(0, 50).map(b => ({
            text: b.innerText.trim().substring(0, 80),
            classes: b.className.substring(0, 120),
            ariaLabel: b.getAttribute('aria-label') || ''
        }));
        results.images = [...document.querySelectorAll('img')].slice(0, 30).map(img => ({
            alt: img.alt,
            src: img.src.substring(0, 120),
            classes: img.className.substring(0, 80)
        }));
        results.cards = [...document.querySelectorAll('[class*="card"], [class*="profil"], [class*="result"], [class*="item"], [class*="grid"] > div')].slice(0, 30).map(el => ({
            tag: el.tagName,
            classes: el.className.substring(0, 150),
            text: el.innerText.trim().substring(0, 150),
            childLinks: [...el.querySelectorAll('a[href]')].map(a => a.href).slice(0, 3)
        }));
        return results;
    }""")

    return {"url": url, "info": info}


@router.get("/debug-sidebar/{platform}")
async def debug_sidebar(platform: str):
    """Inspect and expand chat sidebar discussions, list all conversation buttons."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    import asyncio as aio

    if "/dashboard" not in page.url:
        await page.goto("https://app.wyylde.com/fr-fr", timeout=30000, wait_until="domcontentloaded")
        await aio.sleep(5)

    await page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            const text = (btn.innerText || '').trim();
            const rect = btn.getBoundingClientRect();
            if (text.includes('Discussions en cours') && rect.x > 900 && rect.x < 1100) {
                const chevDown = btn.querySelector('svg[data-icon="chevron-down"]');
                if (chevDown) btn.click();
                break;
            }
        }
    }""")
    await aio.sleep(2)

    await page.mouse.click(1006, 760)
    await aio.sleep(2)

    await page.mouse.move(1100, 400)
    for _ in range(5):
        await page.mouse.wheel(0, 300)
        await aio.sleep(0.5)

    await aio.sleep(1)
    await page.screenshot(path="/tmp/wyylde_sidebar_scrolled.png")

    sidebar_info = await page.evaluate("""() => {
        const result = {items: [], total: 0};
        const allEls = document.querySelectorAll('button, a, div, span, li');

        for (const el of allEls) {
            const rect = el.getBoundingClientRect();
            const text = (el.innerText || '').trim();

            if (rect.x < 990 || rect.x > 1260) continue;
            if (rect.width < 30 || rect.height < 10 || rect.height > 60) continue;
            if (text.length < 2 || text.length > 50) continue;
            if (text.match(/(Homme|Femme|Couple|Travesti|Gay|Transgenre|Discussions|contacts|Pres|#LCS|Actuellement|Explorer|Adhesions)/)) continue;
            if (text.match(/\\d+\\s*ans/)) continue;

            result.items.push({
                tag: el.tagName, text: text, x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                cls: (el.className || '').toString().substring(0, 60)
            });
        }
        result.total = result.items.length;
        return result;
    }""")

    return sidebar_info


@router.get("/debug-chat/{platform}")
async def debug_chat(platform: str, name: str = ""):
    """Click a sidebar discussion by name, then inspect DOM for messages and editors."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    import asyncio as aio

    if name:
        plat = session["platform"]
        convs = await plat.get_sidebar_conversations()

        conv_match = next((c for c in convs if c.get("name") == name), None)
        if conv_match:
            await page.mouse.click(conv_match["x"] + 10, conv_match["y"] + 10)
            await aio.sleep(4)
        else:
            clicked = await page.evaluate("""(targetName) => {
                const allEls = document.querySelectorAll('button, a, div, span');
                for (const el of allEls) {
                    const rect = el.getBoundingClientRect();
                    const text = (el.innerText || '').trim();
                    if (rect.x < 1000 || rect.x > 1250) continue;
                    if (text === targetName && rect.height < 50) {
                        el.click();
                        return {clicked: true, x: rect.x, y: rect.y};
                    }
                }
                return {clicked: false};
            }""", name)
            if clicked.get("clicked"):
                await aio.sleep(4)
            else:
                return {"error": "not_found", "convs": [c["name"] for c in convs[:10]]}

    await page.screenshot(path="/tmp/wyylde_debug_chat.png")

    data = await page.evaluate("""() => {
        const result = {url: window.location.href, editors: [], messages: [], allBigDivs: []};

        const editables = document.querySelectorAll('[contenteditable="true"]');
        for (const e of editables) {
            const rect = e.getBoundingClientRect();
            result.editors.push({
                tag: e.tagName, x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                cls: (e.className || '').toString().substring(0, 80),
                placeholder: e.getAttribute('data-placeholder') || ''
            });
        }

        const allDivs = document.querySelectorAll('div, p, section, article');
        for (const div of allDivs) {
            const rect = div.getBoundingClientRect();
            if (rect.width < 100 || rect.height < 30) continue;
            const text = (div.innerText || '').trim();
            if (text.length < 30 || text.length > 5000) continue;
            const hasTimestamp = text.match(/(Aujourd|Hier|\\d{2}:\\d{2}|a \\d)/);
            const hasMessages = text.includes('\\n') && text.length > 50;
            if (hasTimestamp || (hasMessages && rect.height > 100)) {
                result.messages.push({
                    tag: div.tagName, x: Math.round(rect.x), y: Math.round(rect.y),
                    w: Math.round(rect.width), h: Math.round(rect.height),
                    textLen: text.length, textPreview: text.substring(0, 200),
                    cls: (div.className || '').toString().substring(0, 80)
                });
            }
        }

        for (const div of allDivs) {
            const rect = div.getBoundingClientRect();
            if (rect.width < 200 || rect.height < 100) continue;
            if (rect.x < 0 || rect.y < 0) continue;
            const text = (div.innerText || '').trim();
            if (text.length < 20) continue;
            result.allBigDivs.push({
                tag: div.tagName, x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                textLen: text.length, textStart: text.substring(0, 100),
                cls: (div.className || '').toString().substring(0, 60)
            });
        }
        result.allBigDivs.sort((a, b) => a.x - b.x || a.y - b.y);
        result.messages = result.messages.slice(0, 20);
        result.allBigDivs = result.allBigDivs.slice(0, 30);

        return result;
    }""")

    return data


@router.get("/debug-mailbox/{platform}")
async def debug_mailbox(platform: str):
    """Navigate to a mailbox conversation and inspect DOM structure."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    import asyncio as aio

    await page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=30000, wait_until="domcontentloaded")
    await aio.sleep(4)

    await page.evaluate("""() => { const btn = document.querySelector('button[name="all"]'); if (btn) btn.click(); }""")
    await aio.sleep(2)

    first_conv = await page.evaluate("""() => {
        const links = document.querySelectorAll('a[href*="/mailbox/inbox/"]');
        for (const link of links) {
            const rect = link.getBoundingClientRect();
            if (rect.width > 50 && rect.height > 20) {
                return {href: link.href, text: (link.innerText || '').trim().substring(0, 100)};
            }
        }
        return null;
    }""")

    if not first_conv:
        return {"error": "no conversations found"}

    await page.goto(first_conv["href"], timeout=30000, wait_until="domcontentloaded")
    await aio.sleep(4)

    dom_info = await page.evaluate("""() => {
        const result = {url: window.location.href, divs: []};

        const allDivs = document.querySelectorAll('div, section, article');
        for (const el of allDivs) {
            const rect = el.getBoundingClientRect();
            if (rect.width < 100 || rect.height < 30) continue;
            if (rect.y > 1000) continue;
            const text = (el.innerText || '').trim();
            if (text.length < 10) continue;

            const cls = (el.className || '').toString().substring(0, 150);

            result.divs.push({
                tag: el.tagName,
                cls: cls,
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                w: Math.round(rect.width),
                h: Math.round(rect.height),
                textLen: text.length,
                textPreview: text.substring(0, 120).replace(/\\n/g, ' | ')
            });
        }

        result.divs.sort((a, b) => a.x - b.x || a.y - b.y);

        const editors = document.querySelectorAll('div.tiptap, div[contenteditable="true"]');
        result.editors = [...editors].map(e => {
            const r = e.getBoundingClientRect();
            return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), cls: (e.className||'').substring(0,100)};
        });

        return result;
    }""")

    await page.screenshot(path="/tmp/wyylde_mailbox_conv.png")

    return {"first_conv": first_conv, "dom": dom_info}


@router.get("/debug-unread-sidebar/{platform}")
async def debug_unread_sidebar(platform: str):
    """Inspect sidebar DOM to find unread discussion indicators."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    import asyncio as aio

    if "/dashboard" not in page.url and "/fr-fr" not in page.url:
        await page.goto("https://app.wyylde.com/fr-fr", timeout=30000, wait_until="domcontentloaded")
        await aio.sleep(5)

    header_text = await page.evaluate("""() => {
        const allEls = document.querySelectorAll('button, div');
        for (const b of allEls) {
            const text = (b.innerText || '').trim();
            if (text.includes('Discussion') && (text.includes('non lu') || text.includes('en cours'))) {
                b.click();
                return text;
            }
        }
        return 'not found';
    }""")
    await aio.sleep(2)

    await page.screenshot(path="/tmp/wyylde_unread_debug.png")

    result = await page.evaluate("""() => {
        const data = {header: null, items: []};
        const allEls = document.querySelectorAll('button, div, span, p, a');

        for (const el of allEls) {
            const text = (el.innerText || '').trim();
            if (text.includes('Discussion') && (text.includes('non lu') || text.includes('en cours'))) {
                const rect = el.getBoundingClientRect();
                data.header = {
                    text, tag: el.tagName, id: el.id,
                    classes: (el.className || '').substring(0, 200),
                    x: Math.round(rect.x), y: Math.round(rect.y),
                    w: Math.round(rect.width), h: Math.round(rect.height)
                };
                break;
            }
        }

        const headerY = data.header ? data.header.y : 700;

        for (const el of allEls) {
            const rect = el.getBoundingClientRect();
            if (rect.x < 950 || rect.x > 1280) continue;
            if (rect.y < headerY - 10) continue;
            if (rect.width < 5 || rect.height < 5) continue;
            if (rect.y > 1200) continue;

            const text = (el.innerText || '').trim();
            if (text.length < 1 || text.length > 200) continue;

            const style = window.getComputedStyle(el);
            data.items.push({
                text: text.substring(0, 80),
                tag: el.tagName, id: el.id || '',
                classes: (el.className || '').substring(0, 150),
                x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                bg: style.backgroundColor, color: style.color,
                fontWeight: style.fontWeight, fontSize: style.fontSize
            });
        }
        data.items.sort((a, b) => a.y - b.y);
        return data;
    }""")

    return result


@router.get("/test-sidebar-buttons/{platform}")
async def test_sidebar_buttons(platform: str):
    """Test exact same JS that check_and_reply uses to find sidebar buttons."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    url = page.url

    all_discussions = await page.evaluate("""() => {
        const results = [];
        const seen = new Set();
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const rect = btn.getBoundingClientRect();
            if (rect.x < 1010 || rect.x > 1040) continue;
            if (rect.width < 180 || rect.width > 230) continue;
            if (rect.height < 15 || rect.height > 30) continue;
            const text = (btn.innerText || '').trim();
            if (text.length < 2 || text.length > 40) continue;
            if (seen.has(text)) continue;
            seen.add(text);
            results.push(text);
        }
        return results;
    }""")

    return {"url": url, "count": len(all_discussions), "first_10": all_discussions[:10]}


@router.get("/debug-profile/{platform}")
async def debug_profile(platform: str):
    """Click a chat profile, navigate to their page, capture buttons and icons."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    import asyncio as aio

    if "/dashboard" not in page.url:
        await page.goto("https://app.wyylde.com/fr-fr", timeout=30000, wait_until="domcontentloaded")
        await aio.sleep(5)

    clicked_name = await page.evaluate("""() => {
        const buttons = document.querySelectorAll('button[class*="bg-neutral-lowest"][class*="cursor-pointer"]');
        if (buttons[0]) {
            const text = buttons[0].innerText.trim();
            buttons[0].click();
            return text;
        }
        return null;
    }""")
    if not clicked_name:
        return {"error": "no_chat_profiles"}

    await aio.sleep(2)

    member_href = await page.evaluate("""() => {
        const links = [...document.querySelectorAll('a[href*="/member/"]')];
        for (const link of links) {
            const rect = link.getBoundingClientRect();
            if (rect.x > 500 && rect.width > 0 && link.className.includes('flex')) {
                link.click();
                return link.href;
            }
        }
        let best = null;
        let bestX = 0;
        for (const link of links) {
            const rect = link.getBoundingClientRect();
            if (rect.x > 500 && rect.width > 0 && rect.x > bestX) {
                bestX = rect.x;
                best = link;
            }
        }
        if (best) { best.click(); return best.href; }
        return null;
    }""")

    for _ in range(10):
        await aio.sleep(1)
        if "/member/" in page.url:
            break
    await aio.sleep(2)

    await page.screenshot(path="/tmp/wyylde_profile_debug.png")

    url = page.url
    info = await page.evaluate("""() => {
        const results = {};
        results.buttons = [...document.querySelectorAll('button')].map(b => ({
            text: b.innerText.trim().substring(0, 100),
            classes: b.className.substring(0, 150),
            ariaLabel: b.getAttribute('aria-label') || '',
            svg: b.querySelector('svg') ? (b.querySelector('svg').getAttribute('data-icon') || b.querySelector('svg').classList.toString()) : ''
        }));
        results.icons = [...document.querySelectorAll('svg')].filter(s => s.getAttribute('data-icon')).map(s => ({
            dataIcon: s.getAttribute('data-icon'),
            parent: s.parentElement ? s.parentElement.tagName + ' ' + s.parentElement.className.substring(0, 100) : ''
        }));
        results.profileName = document.querySelector('h1, h2, [class*="pseudo"], [class*="username"], button.max-w-full.font-poppins')?.innerText || '';
        return results;
    }""")

    return {"url": url, "clicked": clicked_name, "member_href": member_href, "info": info}


@router.post("/test-click/{platform}")
async def test_click(platform: str):
    """Explore search results - close filters, find profile cards, screenshot."""
    import asyncio as aio
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page

    if "/search" not in page.url:
        await page.goto("https://app.wyylde.com/fr-fr/search/user", timeout=30000, wait_until="domcontentloaded")
        await aio.sleep(3)

    await page.keyboard.press("Escape")
    await aio.sleep(1)
    await page.evaluate("""() => {
        const form = document.querySelector('#searchForm, .gauche.search');
        if (form) form.style.display = 'none';
    }""")
    await aio.sleep(1)
    await aio.sleep(5)

    await page.screenshot(path="/tmp/wyylde_search_results.png")

    result = await page.evaluate("""() => {
        const data = {};

        const container = document.querySelector('.container.listx3, [class*="listx3"]');
        if (container) {
            const resultsDiv = container.children[1];
            data.container = {
                classes: container.className,
                childCount: container.children.length,
                rect: container.getBoundingClientRect(),
                innerHTML_preview: resultsDiv ? resultsDiv.innerHTML.substring(0, 1000) : container.innerHTML.substring(0, 500),
                results_child_classes: resultsDiv ? resultsDiv.className : 'none'
            };
            data.result_links = [...container.querySelectorAll('a[href*="/member/"]')].map(a => ({
                href: a.href,
                text: a.innerText.trim().substring(0, 80),
                rect: {x: Math.round(a.getBoundingClientRect().x), y: Math.round(a.getBoundingClientRect().y), w: Math.round(a.getBoundingClientRect().width)}
            }));
            data.result_items = [...container.querySelectorAll('a, button, [role="button"]')].slice(0, 30).map(el => ({
                tag: el.tagName,
                href: el.href || '',
                text: el.innerText.trim().substring(0, 100),
                classes: el.className.substring(0, 150),
                rect: {x: Math.round(el.getBoundingClientRect().x), y: Math.round(el.getBoundingClientRect().y), w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height)}
            }));
        } else {
            data.container = null;
        }

        data.all_member_links = [...document.querySelectorAll('a[href*="/member/"]')].map(a => ({
            href: a.href,
            text: a.innerText.trim().substring(0, 50),
            rect: {x: Math.round(a.getBoundingClientRect().x), y: Math.round(a.getBoundingClientRect().y)}
        }));

        return data;
    }""")

    return {"url": page.url, "data": result}


@router.post("/explore/{platform}")
async def explore_platform(platform: str):
    """Run full exploration of a platform and generate reference document."""
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected", "message": f"{platform} n'est pas connecte."}
    logged_in = await bot_engine.check_login(platform)
    if not logged_in:
        return {"error": "not_logged_in", "message": f"Non connecte sur {platform}."}
    try:
        doc_path = await explore_site(platform, session["platform"].page)
        return {"status": "done", "document": doc_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/test-message/{platform}")
async def test_message_flow(platform: str):
    """Step-by-step test of message sending with screenshots at each step."""
    import asyncio as aio
    import json as json_mod
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return {"error": "not_connected"}
    page = session["platform"].page
    steps = []

    await page.goto("https://app.wyylde.com/fr-fr", timeout=30000, wait_until="domcontentloaded")
    await aio.sleep(5)
    await page.screenshot(path="/tmp/msg_step1_dashboard.png")
    steps.append("1. Dashboard loaded")

    clicked = await page.evaluate("""() => {
        const buttons = document.querySelectorAll('button[class*="bg-neutral-lowest"][class*="cursor-pointer"]');
        if (buttons[0]) { buttons[0].click(); return buttons[0].innerText.trim().split('\\n')[0]; }
        return null;
    }""")
    steps.append(f"2. Clicked chat profile: {clicked}")
    await aio.sleep(2)
    await page.screenshot(path="/tmp/msg_step2_chat_open.png")

    member_href = await page.evaluate("""() => {
        const links = [...document.querySelectorAll('a[href*="/member/"]')];
        let best = null, bestX = 0;
        for (const link of links) {
            const rect = link.getBoundingClientRect();
            if (rect.x > 500 && rect.width > 0 && rect.x > bestX) { bestX = rect.x; best = link; }
        }
        if (best) { best.click(); return best.href; }
        return null;
    }""")
    steps.append(f"3. Clicked member link: {member_href}")

    for _ in range(10):
        await aio.sleep(1)
        if "/member/" in page.url:
            break
    await aio.sleep(2)
    await page.screenshot(path="/tmp/msg_step3_profile.png")
    steps.append(f"3b. On page: {page.url}")

    msg_clicked = await page.evaluate("""() => {
        const buttons = [...document.querySelectorAll('button')];
        for (const btn of buttons) {
            const svg = btn.querySelector('svg[data-icon="paper-plane"]');
            const text = btn.innerText.trim().toLowerCase();
            if (svg && (text.includes('crire') || text.includes('ecrire'))) {
                const rect = btn.getBoundingClientRect();
                if (rect.x > 300 && rect.width > 0) {
                    btn.click();
                    return {clicked: true, text: btn.innerText.trim(), x: rect.x, y: rect.y};
                }
            }
        }
        return {clicked: false, buttons: buttons.slice(0, 30).map(b => ({
            text: b.innerText.trim().substring(0, 80),
            hasSvg: !!b.querySelector('svg'),
            svgIcon: b.querySelector('svg') ? (b.querySelector('svg').getAttribute('data-icon') || '') : '',
            x: Math.round(b.getBoundingClientRect().x),
            y: Math.round(b.getBoundingClientRect().y),
            w: Math.round(b.getBoundingClientRect().width)
        }))};
    }""")
    steps.append(f"4. Lui ecrire: {json_mod.dumps(msg_clicked, ensure_ascii=False)[:500]}")
    await aio.sleep(3)
    await page.screenshot(path="/tmp/msg_step4_lui_ecrire.png")

    editor_info = await page.evaluate("""() => {
        const editors = document.querySelectorAll('div[contenteditable="true"]');
        const results = [];
        for (const e of editors) {
            const rect = e.getBoundingClientRect();
            results.push({
                classes: e.className.substring(0, 150),
                x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                visible: rect.width > 0 && rect.height > 0,
                isTiptap: e.classList.contains('tiptap'),
                isProseMirror: e.classList.contains('ProseMirror')
            });
        }
        return results;
    }""")
    steps.append(f"5. Editors found: {json_mod.dumps(editor_info, ensure_ascii=False)[:500]}")

    if editor_info:
        best_editor = max(editor_info, key=lambda e: e["w"])
        cx = best_editor["x"] + best_editor["w"] // 2
        cy = best_editor["y"] + best_editor["h"] // 2
        steps.append(f"5a. Clicking widest editor at center ({cx}, {cy}), w={best_editor['w']}")

        await page.mouse.click(cx, cy)
        await aio.sleep(0.5)
        test_msg = "Test message debug"
        await page.keyboard.type(test_msg, delay=30)
        await aio.sleep(1)
        await page.screenshot(path="/tmp/msg_step5_typed.png")
        steps.append("5b. Typed test message")

        editor_content = await page.evaluate("""() => {
            const editors = document.querySelectorAll('div[contenteditable="true"]');
            let best = null, bestW = 0;
            for (const e of editors) { const r = e.getBoundingClientRect(); if (r.width > bestW) { bestW = r.width; best = e; } }
            return best ? best.innerText.trim() : '';
        }""")
        steps.append(f"5c. Editor content: '{editor_content}'")

        send_info = await page.evaluate("""() => {
            const buttons = [...document.querySelectorAll('button')];
            const results = [];
            for (const btn of buttons) {
                const rect = btn.getBoundingClientRect();
                const svg = btn.querySelector('svg');
                const icon = svg ? (svg.getAttribute('data-icon') || svg.classList.toString() || 'svg') : '';
                if (rect.y > 380 && rect.x > 250) {
                    results.push({text: btn.innerText.trim().substring(0, 40), icon, x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height), disabled: btn.disabled});
                }
            }
            return results;
        }""")
        steps.append(f"6. Buttons near modal bottom: {json_mod.dumps(send_info, ensure_ascii=False)}")

    await page.goto("https://app.wyylde.com/fr-fr", timeout=15000, wait_until="domcontentloaded")

    return {"steps": steps}


@router.post("/reload")
async def hot_reload():
    """Hot-reload Python modules without restarting the server or closing the browser."""
    import importlib
    import src.bot_engine
    from ..platforms import wyylde as wy_mod
    from ..messaging import ai_messages as ai_mod

    saved_sessions = dict(src.bot_engine.browser_sessions)

    importlib.reload(ai_mod)
    importlib.reload(wy_mod)
    importlib.reload(src.bot_engine)

    src.bot_engine.browser_sessions.update(saved_sessions)

    for name, session in src.bot_engine.browser_sessions.items():
        old_platform = session["platform"]
        new_cls = src.bot_engine.PLATFORMS.get(name)
        if new_cls:
            new_platform = new_cls(old_platform.context)
            new_platform.page = old_platform.page
            session["platform"] = new_platform

    return {"status": "reloaded", "modules": ["bot_engine", "wyylde", "ai_messages"]}
