"""
Site Explorer — Maps all pages, selectors, inputs, buttons for any dating platform.
Outputs a structured reference document for the coding agent.
Usage: await explore_site("wyylde", page)
"""
import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "docs"

# Platform-specific pages to explore
PLATFORM_PAGES = {
    "wyylde": [
        ("Dashboard", "https://app.wyylde.com/fr-fr"),
        ("Search", "https://app.wyylde.com/fr-fr/search/user"),
        ("Mailbox Inbox", "https://app.wyylde.com/fr-fr/mailbox/inbox"),
        ("Chat/Messages", "https://app.wyylde.com/fr-fr/messages"),
    ],
    "tinder": [
        ("Home/Recs", "https://tinder.com/app/recs"),
        ("Matches", "https://tinder.com/app/matches"),
        ("Messages", "https://tinder.com/app/messages"),
        ("Profile", "https://tinder.com/app/profile"),
    ],
    "meetic": [
        ("Home", "https://www.meetic.fr/app"),
        ("Shuffle", "https://www.meetic.fr/app/shuffle"),
        ("Search", "https://www.meetic.fr/app/search"),
        ("Matches", "https://www.meetic.fr/app/matches"),
        ("Messages", "https://www.meetic.fr/app/conversations"),
    ],
}

# Platform-specific interactive flows to explore
PLATFORM_FLOWS = {
    "wyylde": [
        "chat_sidebar_profile",  # Click a chat profile → member page
        "lui_ecrire",            # Click "Lui écrire" from profile — explore modal in detail
        "profile_tabs",          # Explore all tabs on a profile (Infos, Médias, etc.)
        "mailbox_conversation",  # Open a conversation from mailbox
        "my_sent_messages",      # Read all manually sent messages for style learning
        "sidebar_chat_discussion",  # Open a sidebar discussion and map chat panel DOM
    ],
    "tinder": [
        "profile_card",          # Explore the current profile card
        "match_conversation",    # Open a match conversation
    ],
    "meetic": [
        "shuffle_card",          # Explore the shuffle profile card
        "match_conversation",    # Open a match conversation
    ],
}


EXTRACT_JS = """() => {
    const data = {};

    // All visible buttons
    data.buttons = [...document.querySelectorAll('button')].map(btn => {
        const rect = btn.getBoundingClientRect();
        const svg = btn.querySelector('svg[data-icon]');
        return {
            text: btn.innerText.trim().substring(0, 100),
            svg_icon: svg ? svg.getAttribute('data-icon') : null,
            classes: btn.className.substring(0, 150),
            type: btn.type || '',
            disabled: btn.disabled,
            pos: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
            visible: rect.width > 0 && rect.height > 0,
            selector: _buildSelector(btn)
        };
    }).filter(b => b.visible);

    // All input fields
    data.inputs = [...document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]')].map(el => {
        const rect = el.getBoundingClientRect();
        return {
            tag: el.tagName,
            type: el.type || '',
            name: el.name || '',
            placeholder: el.placeholder || '',
            contentEditable: el.contentEditable,
            classes: el.className.substring(0, 150),
            role: el.getAttribute('role') || '',
            pos: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
            visible: rect.width > 0 && rect.height > 0,
            selector: _buildSelector(el)
        };
    }).filter(i => i.visible);

    // All links
    data.links = [...document.querySelectorAll('a[href]')].map(a => {
        const rect = a.getBoundingClientRect();
        return {
            href: a.href,
            text: a.innerText.trim().substring(0, 80),
            classes: a.className.substring(0, 100),
            pos: {x: Math.round(rect.x), y: Math.round(rect.y)},
            visible: rect.width > 0 && rect.height > 0
        };
    }).filter(l => l.visible);

    // SVG icons (unique)
    data.icons = [...new Set([...document.querySelectorAll('svg[data-icon]')].map(s => s.getAttribute('data-icon')))];

    // Forms
    data.forms = [...document.querySelectorAll('form')].map(form => ({
        action: form.action,
        method: form.method,
        classes: form.className.substring(0, 100),
        fields: [...form.querySelectorAll('input, textarea, select')].map(i => ({
            tag: i.tagName, type: i.type || '', name: i.name || '', placeholder: i.placeholder || ''
        }))
    }));

    // Modals/dialogs
    data.modals = [...document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="overlay"]')].map(el => ({
        classes: el.className.substring(0, 150),
        visible: el.getBoundingClientRect().width > 0,
        text_preview: el.innerText.trim().substring(0, 200)
    })).filter(m => m.visible);

    // Helper to build a usable CSS selector
    function _buildSelector(el) {
        if (el.id) return '#' + el.id;
        let sel = el.tagName.toLowerCase();
        if (el.type) sel += '[type="' + el.type + '"]';
        if (el.name) sel += '[name="' + el.name + '"]';
        if (el.placeholder) sel += '[placeholder*="' + el.placeholder.substring(0, 20) + '"]';
        if (el.getAttribute('role')) sel += '[role="' + el.getAttribute('role') + '"]';
        const svg = el.querySelector('svg[data-icon]');
        if (svg) sel = 'button:has(svg[data-icon="' + svg.getAttribute('data-icon') + '"])';
        return sel;
    }

    return data;
}"""


async def _navigate(page, url: str):
    """Navigate to a URL, trying SPA-friendly methods first."""
    path = url.replace("https://app.wyylde.com", "").replace("https://tinder.com", "").replace("https://www.meetic.fr", "")
    # Try SPA link click first
    clicked = await page.evaluate(f"""() => {{
        const link = document.querySelector('a[href*="{path}"]');
        if (link) {{ link.click(); return true; }}
        return false;
    }}""")
    if clicked:
        await asyncio.sleep(4)
        return

    try:
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
    except Exception:
        # Fallback: JS navigation
        await page.evaluate(f"() => window.location.href = '{url}'")
    await asyncio.sleep(4)


async def _explore_flow_wyylde(page, flow_name: str) -> dict:
    """Execute Wyylde-specific interactive flows."""
    result = {"flow": flow_name}

    if flow_name == "chat_sidebar_profile":
        # Go to dashboard, explore multiple profiles from chat sidebar
        await _navigate(page, "https://app.wyylde.com/fr-fr")
        await asyncio.sleep(5)

        # Get all chat sidebar profiles
        all_profiles = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('button[class*="bg-neutral-lowest"][class*="cursor-pointer"]');
            return [...buttons].map((b, idx) => ({
                text: b.innerText.trim().substring(0, 80),
                index: idx
            })).filter(p => p.text.length > 3);
        }""")
        result["chat_profiles_total"] = len(all_profiles)
        result["profiles_explored"] = []

        # Explore up to 3 different profiles to find all button variants
        for profile_idx in range(min(3, len(all_profiles))):
            profile_data = {"index": profile_idx, "name": all_profiles[profile_idx]["text"].split("\n")[0]}
            logger.info(f"  Exploring profile {profile_idx}: {profile_data['name']}")

            # Click the chat profile
            await page.evaluate(f"""() => {{
                const buttons = document.querySelectorAll('button[class*="bg-neutral-lowest"][class*="cursor-pointer"]');
                if (buttons[{profile_idx}]) buttons[{profile_idx}].click();
            }}""")
            await asyncio.sleep(2)

            # Find and click member link
            member_link = await page.evaluate("""() => {
                const links = [...document.querySelectorAll('a[href*="/member/"]')];
                let best = null, bestX = 0;
                for (const link of links) {
                    const rect = link.getBoundingClientRect();
                    if (rect.x > 500 && rect.width > 0 && rect.x > bestX) { bestX = rect.x; best = link; }
                }
                if (best) { best.click(); return best.href; }
                return null;
            }""")
            profile_data["member_link"] = member_link

            if member_link:
                for _ in range(10):
                    await asyncio.sleep(1)
                    if "/member/" in page.url:
                        break
                await asyncio.sleep(2)
                profile_data["profile_url"] = page.url

                # Extract ALL buttons on this profile page
                profile_buttons = await page.evaluate("""() => {
                    return [...document.querySelectorAll('button')].map(btn => {
                        const rect = btn.getBoundingClientRect();
                        const svg = btn.querySelector('svg[data-icon]');
                        return {
                            text: btn.innerText.trim().substring(0, 60),
                            svg_icon: svg ? svg.getAttribute('data-icon') : null,
                            x: Math.round(rect.x), y: Math.round(rect.y),
                            w: Math.round(rect.width), h: Math.round(rect.height),
                            visible: rect.width > 0 && rect.height > 0
                        };
                    }).filter(b => b.visible && b.x > 300);
                }""")
                profile_data["action_buttons"] = profile_buttons

                # Check for "Lui écrire" specifically
                lui_ecrire = await page.evaluate("""() => {
                    const buttons = [...document.querySelectorAll('button')];
                    for (const btn of buttons) {
                        const text = btn.innerText.trim();
                        const svg = btn.querySelector('svg[data-icon="paper-plane"]');
                        if (text.toLowerCase().includes('crire') || (svg && text.length > 0)) {
                            const rect = btn.getBoundingClientRect();
                            if (rect.x > 300) return {text, icon: svg ? svg.getAttribute('data-icon') : null, x: rect.x, y: rect.y};
                        }
                    }
                    return null;
                }""")
                profile_data["lui_ecrire_button"] = lui_ecrire

                # Check for chat input (contenteditable div)
                chat_input = await page.evaluate("""() => {
                    const divs = document.querySelectorAll('div[contenteditable="true"]');
                    return [...divs].map(d => {
                        const rect = d.getBoundingClientRect();
                        return {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height), visible: rect.width > 0};
                    }).filter(d => d.visible);
                }""")
                profile_data["chat_inputs"] = chat_input

                # Screenshot this profile
                screenshot_name = f"profile_{profile_idx}.png"
                await page.screenshot(path=str(DOCS_DIR / screenshot_name))
                profile_data["screenshot"] = screenshot_name

            result["profiles_explored"].append(profile_data)

            # Go back to dashboard for next profile
            await page.goto("https://app.wyylde.com/fr-fr", timeout=15000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

    elif flow_name == "lui_ecrire":
        # Go to dashboard, click a chat profile, navigate to member page, click "Lui écrire"
        await _navigate(page, "https://app.wyylde.com/fr-fr")
        await asyncio.sleep(5)

        # Click first chat profile
        clicked_name = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('button[class*="bg-neutral-lowest"][class*="cursor-pointer"]');
            if (buttons[0]) { buttons[0].click(); return buttons[0].innerText.trim().split('\\n')[0]; }
            return null;
        }""")
        result["clicked_chat_profile"] = clicked_name
        await asyncio.sleep(2)

        # Navigate to member page
        member_link = await page.evaluate("""() => {
            const links = [...document.querySelectorAll('a[href*="/member/"]')];
            let best = null, bestX = 0;
            for (const link of links) {
                const rect = link.getBoundingClientRect();
                if (rect.x > 500 && rect.width > 0 && rect.x > bestX) { bestX = rect.x; best = link; }
            }
            if (best) { best.click(); return best.href; }
            return null;
        }""")
        result["member_link"] = member_link

        if member_link:
            for _ in range(10):
                await asyncio.sleep(1)
                if "/member/" in page.url:
                    break
            await asyncio.sleep(2)

            result["profile_url"] = page.url
            await page.screenshot(path=str(DOCS_DIR / "lui_ecrire_before_click.png"))

            # Click "Lui écrire"
            lui_ecrire = await page.evaluate("""() => {
                const buttons = [...document.querySelectorAll('button')];
                for (const btn of buttons) {
                    const svg = btn.querySelector('svg[data-icon="paper-plane"]');
                    const text = btn.innerText.trim().toLowerCase();
                    if (svg && (text.includes('crire') || text.includes('écrire'))) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.x > 300 && rect.width > 0) {
                            btn.click();
                            return {text: btn.innerText.trim(), x: rect.x, y: rect.y, classes: btn.className.substring(0, 100)};
                        }
                    }
                }
                return null;
            }""")
            result["lui_ecrire_button"] = lui_ecrire
            await asyncio.sleep(4)

            # NOW: Deeply explore the modal/popup that appeared
            await page.screenshot(path=str(DOCS_DIR / "lui_ecrire_modal.png"))

            # Map the modal in detail
            modal_data = await page.evaluate("""() => {
                const data = {};

                // Find the modal/dialog
                const modals = document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="fixed"][class*="inset"]');
                data.modals = [...modals].map(m => ({
                    classes: m.className.substring(0, 200),
                    text_preview: m.innerText.trim().substring(0, 300),
                    rect: (() => { const r = m.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}; })()
                })).filter(m => m.rect.w > 0);

                // All contenteditable editors (TipTap, ProseMirror, etc.)
                data.editors = [...document.querySelectorAll('div[contenteditable="true"]')].map(e => {
                    const rect = e.getBoundingClientRect();
                    return {
                        classes: e.className.substring(0, 200),
                        isTiptap: e.classList.contains('tiptap'),
                        isProseMirror: e.classList.contains('ProseMirror'),
                        placeholder: e.getAttribute('data-placeholder') || e.querySelector('p[data-placeholder]')?.getAttribute('data-placeholder') || '',
                        rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                        visible: rect.width > 0
                    };
                }).filter(e => e.visible);

                // ALL buttons visible on screen, especially near the editor
                data.all_buttons = [...document.querySelectorAll('button')].map(btn => {
                    const rect = btn.getBoundingClientRect();
                    const svg = btn.querySelector('svg');
                    const svgIcon = svg ? (svg.getAttribute('data-icon') || svg.querySelector('use')?.getAttribute('href') || 'svg-no-icon') : null;
                    return {
                        text: btn.innerText.trim().substring(0, 60),
                        svg_icon: svgIcon,
                        classes: btn.className.substring(0, 150),
                        disabled: btn.disabled,
                        rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                        visible: rect.width > 0 && rect.height > 0,
                        html: btn.innerHTML.substring(0, 200)
                    };
                }).filter(b => b.visible);

                // Specifically look for send-like buttons (near the editor, small, with icon)
                data.send_candidates = data.all_buttons.filter(b =>
                    (b.rect.y > 380 && b.rect.x > 250) ||
                    b.text.toLowerCase().includes('envoyer') ||
                    b.svg_icon === 'paper-plane'
                );

                // Input fields with placeholders
                data.input_fields = [...document.querySelectorAll('input[placeholder], [data-placeholder]')].map(el => ({
                    tag: el.tagName,
                    placeholder: el.placeholder || el.getAttribute('data-placeholder') || '',
                    rect: (() => { const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width)}; })()
                }));

                return data;
            }""")
            result["modal_exploration"] = modal_data

        else:
            result["error"] = "Could not navigate to member page"

    elif flow_name == "my_sent_messages":
        # Navigate to mailbox sent, then open each conversation to read sent messages
        await _navigate(page, "https://app.wyylde.com/fr-fr/mailbox/inbox")
        await asyncio.sleep(4)

        # Click on "Envoyés" tab if available
        await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/mailbox/sent"], button');
            for (const el of links) {
                if (el.innerText.trim().toLowerCase().includes('envoy')) { el.click(); return; }
            }
        }""")
        await asyncio.sleep(3)
        await page.screenshot(path=str(DOCS_DIR / "my_sent_messages_list.png"))

        # Get all conversations/messages visible
        conversations_text = await page.evaluate("""() => {
            const main = document.querySelector('main, [role="main"]');
            return main ? main.innerText.substring(0, 10000) : '';
        }""")
        result["sent_page_text"] = conversations_text

        # Try to find and click individual conversation links
        conv_links = await page.evaluate("""() => {
            return [...document.querySelectorAll('a[href*="/mailbox/"]')]
                .filter(a => a.getBoundingClientRect().width > 0)
                .map(a => ({href: a.href, text: a.innerText.trim().substring(0, 100)}))
                .filter(a => a.text.length > 0);
        }""")
        result["conversation_links"] = conv_links

        # Open each conversation to read messages
        result["conversations"] = []
        for conv in conv_links[:10]:
            if "/inbox/" not in conv["href"] and "/sent/" not in conv["href"]:
                continue
            try:
                await page.goto(conv["href"], timeout=15000, wait_until="domcontentloaded")
                await asyncio.sleep(3)

                # Extract all messages in this conversation
                messages = await page.evaluate("""() => {
                    const data = {url: window.location.href, messages: []};
                    // Look for message bubbles or text blocks
                    const main = document.querySelector('main, [role="main"]');
                    if (main) data.fullText = main.innerText.substring(0, 5000);

                    // Try to find individual message elements
                    const msgElements = document.querySelectorAll('[class*="message"], [class*="bubble"], [class*="chat-"]');
                    for (const el of [...msgElements].slice(0, 30)) {
                        data.messages.push(el.innerText.trim().substring(0, 500));
                    }
                    return data;
                }""")
                result["conversations"].append(messages)
            except Exception as e:
                result["conversations"].append({"error": str(e), "href": conv["href"]})

        # Go back to dashboard
        await _navigate(page, "https://app.wyylde.com/fr-fr")

    elif flow_name == "profile_tabs":
        # Navigate to a profile and explore ALL tabs (Activités, Infos, Médias, Agenda, Communauté)
        await _navigate(page, "https://app.wyylde.com/fr-fr")
        await asyncio.sleep(5)

        # Click first chat profile to get to a member page
        clicked_name = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('button[class*="bg-neutral-lowest"][class*="cursor-pointer"]');
            if (buttons[0]) { buttons[0].click(); return buttons[0].innerText.trim().split('\\n')[0]; }
            return null;
        }""")
        result["clicked_profile"] = clicked_name
        await asyncio.sleep(2)

        # Navigate to member page
        await page.evaluate("""() => {
            const links = [...document.querySelectorAll('a[href*="/member/"]')];
            let best = null, bestX = 0;
            for (const link of links) {
                const rect = link.getBoundingClientRect();
                if (rect.x > 500 && rect.width > 0 && rect.x > bestX) { bestX = rect.x; best = link; }
            }
            if (best) best.click();
        }""")
        for _ in range(10):
            await asyncio.sleep(1)
            if "/member/" in page.url:
                break
        await asyncio.sleep(2)

        result["profile_url"] = page.url
        result["tabs_data"] = {}

        # Click "EN SAVOIR PLUS" first
        await page.evaluate("""() => {
            const els = document.querySelectorAll('button, a, span');
            for (const el of els) {
                if ((el.innerText || '').trim().toUpperCase().includes('EN SAVOIR PLUS')) {
                    el.click(); return;
                }
            }
        }""")
        await asyncio.sleep(1)

        # Read the expanded bio
        bio_text = await page.evaluate("""() => {
            const divs = document.querySelectorAll('div');
            let best = '';
            for (const div of divs) {
                const rect = div.getBoundingClientRect();
                if (rect.x < 280 || rect.width < 300) continue;
                const text = div.innerText.trim();
                if (text.length > 50 && text.length < 2000 && text.split(/\\s+/).length > 10) {
                    if (text.length > best.length) best = text;
                }
            }
            return best.substring(0, 1000);
        }""")
        result["expanded_bio"] = bio_text
        await page.screenshot(path=str(DOCS_DIR / "profile_bio_expanded.png"))

        # Now explore each tab
        tab_names = ["Activités", "Infos", "Médias", "Agenda", "Communauté"]
        for tab_name in tab_names:
            logger.info(f"  Exploring tab: {tab_name}")
            # Click the tab
            tab_clicked = await page.evaluate(f"""() => {{
                const tabs = document.querySelectorAll('button, a');
                for (const tab of tabs) {{
                    const text = (tab.innerText || '').trim();
                    const rect = tab.getBoundingClientRect();
                    if (text === '{tab_name}' && rect.x > 280 && rect.width > 0) {{
                        tab.click();
                        return true;
                    }}
                }}
                return false;
            }}""")

            if not tab_clicked:
                result["tabs_data"][tab_name] = {"error": "tab not found"}
                continue

            await asyncio.sleep(2)

            # Screenshot this tab
            screenshot_name = f"profile_tab_{tab_name.lower()}.png"
            await page.screenshot(path=str(DOCS_DIR / screenshot_name))

            # Extract all text content from the main area
            tab_content = await page.evaluate("""() => {
                const data = {text: '', elements: []};
                const divs = document.querySelectorAll('div, p, span, li');
                for (const el of divs) {
                    const rect = el.getBoundingClientRect();
                    if (rect.x < 280 || rect.width < 200) continue;
                    if (rect.y < 100 || rect.y > 800) continue;
                    const text = (el.innerText || '').trim();
                    if (text.length < 5 || text.length > 2000) continue;
                    // Only leaf-ish elements (not containers with tons of text)
                    if (el.children.length > 5 && text.length > 200) continue;
                    data.elements.push({
                        tag: el.tagName, text: text.substring(0, 200),
                        x: Math.round(rect.x), y: Math.round(rect.y),
                        w: Math.round(rect.width), h: Math.round(rect.height),
                        cls: (el.className || '').toString().substring(0, 80)
                    });
                }
                // Also get the full text from the main content area
                const mainDivs = document.querySelectorAll('div');
                let mainText = '';
                for (const div of mainDivs) {
                    const rect = div.getBoundingClientRect();
                    if (rect.x > 280 && rect.x < 400 && rect.width > 400 && rect.height > 200) {
                        const t = div.innerText.trim();
                        if (t.length > mainText.length) mainText = t;
                    }
                }
                data.text = mainText.substring(0, 3000);
                return data;
            }""")

            result["tabs_data"][tab_name] = {
                "screenshot": screenshot_name,
                "content_preview": tab_content["text"][:500],
                "elements_count": len(tab_content["elements"]),
                "elements_sample": tab_content["elements"][:15]
            }

    elif flow_name == "sidebar_chat_discussion":
        # Explore the sidebar chat: open "Discussions en cours", click one, map the chat panel
        await _navigate(page, "https://app.wyylde.com/fr-fr")
        await asyncio.sleep(5)

        # Step 1: Click "Discussions en cours" to expand
        await page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                const text = (btn.innerText || '').trim();
                const rect = btn.getBoundingClientRect();
                if ((text.includes('Discussions en cours') || text.includes('Discussions non lues')) && rect.x > 900) {
                    btn.click();
                }
            }
        }""")
        await asyncio.sleep(2)

        # Scroll sidebar to reveal discussions
        await page.evaluate("""() => {
            const ctn = document.getElementById('ctn');
            if (ctn) ctn.scrollTop = ctn.scrollHeight;
            const aside = document.querySelector('aside');
            if (aside) aside.scrollTop = aside.scrollHeight;
        }""")
        await asyncio.sleep(2)
        await page.screenshot(path=str(DOCS_DIR / "sidebar_discussions_list.png"))

        # Step 2: Find all discussion names
        discussions = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const allEls = document.querySelectorAll('button, div, span, a');
            for (const el of allEls) {
                const rect = el.getBoundingClientRect();
                const text = (el.innerText || '').trim();
                if (rect.x < 1020 || rect.x > 1150) continue;
                if (rect.height > 45 || rect.height < 8 || rect.width < 30) continue;
                if (text.length < 3 || text.length > 40) continue;
                if (text.match(/(Homme|Femme|Couple|Travesti|Gay|Transgenre|Discussion|contact|Près|Chat|Recherche|LIVE|voyeur|\\d+\\s*ans|#LCS|New)/i)) continue;
                if (seen.has(text)) continue;
                seen.add(text);
                results.push({
                    name: text, tag: el.tagName,
                    x: Math.round(rect.x), y: Math.round(rect.y),
                    w: Math.round(rect.width), h: Math.round(rect.height)
                });
            }
            return results;
        }""")
        result["discussions_found"] = len(discussions)
        result["discussions_sample"] = discussions[:10]

        # Step 3: Click the first visible discussion with positive y
        target = None
        for d in discussions:
            if d["y"] > 0 and d["y"] < 800:
                target = d
                break
        if not target and discussions:
            target = discussions[0]

        if target:
            result["clicked_discussion"] = target["name"]
            # Try clicking via locator (handles scrolling)
            clicked = False
            for sel_type in ['div', 'span', 'button']:
                try:
                    loc = page.locator(f'{sel_type}:text-is("{target["name"]}")')
                    count = await loc.count()
                    for i in range(count):
                        box = await loc.nth(i).bounding_box()
                        if box and box["x"] > 1000 and box["x"] < 1200:
                            await loc.nth(i).scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await loc.nth(i).click()
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception:
                    continue

            if not clicked:
                # Fallback: click at coordinates
                await page.mouse.click(target["x"] + 10, target["y"] + 10)

            await asyncio.sleep(4)
            await page.screenshot(path=str(DOCS_DIR / "sidebar_chat_opened.png"))

            # Step 4: Deep DOM inspection of the opened chat panel
            chat_dom = await page.evaluate("""() => {
                const data = {
                    url: window.location.href,
                    editors: [],
                    contentEditables: [],
                    messageContainers: [],
                    allElements: [],
                    aside: null,
                    tchat: null,
                    paperPlanes: []
                };

                // All contenteditable elements
                const editables = document.querySelectorAll('[contenteditable="true"]');
                for (const e of editables) {
                    const rect = e.getBoundingClientRect();
                    if (rect.width <= 0) continue;
                    data.contentEditables.push({
                        tag: e.tagName,
                        classes: (e.className || '').toString().substring(0, 150),
                        isTiptap: e.classList.contains('tiptap'),
                        isProseMirror: e.classList.contains('ProseMirror'),
                        placeholder: e.getAttribute('data-placeholder') || '',
                        x: Math.round(rect.x), y: Math.round(rect.y),
                        w: Math.round(rect.width), h: Math.round(rect.height)
                    });
                }

                // Paper plane buttons (send)
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    const svg = btn.querySelector('svg[data-icon*="paper-plane"]');
                    if (svg) {
                        const rect = btn.getBoundingClientRect();
                        data.paperPlanes.push({
                            icon: svg.getAttribute('data-icon'),
                            x: Math.round(rect.x), y: Math.round(rect.y),
                            w: Math.round(rect.width), h: Math.round(rect.height),
                            disabled: btn.disabled,
                            visible: rect.width > 0
                        });
                    }
                }

                // Aside element
                const aside = document.querySelector('aside');
                if (aside) {
                    const rect = aside.getBoundingClientRect();
                    data.aside = {
                        x: Math.round(rect.x), y: Math.round(rect.y),
                        w: Math.round(rect.width), h: Math.round(rect.height),
                        children: aside.children.length,
                        textPreview: aside.innerText.substring(0, 500)
                    };
                }

                // Section#tchat
                const tchat = document.getElementById('tchat');
                if (tchat) {
                    const rect = tchat.getBoundingClientRect();
                    data.tchat = {
                        x: Math.round(rect.x), y: Math.round(rect.y),
                        w: Math.round(rect.width), h: Math.round(rect.height),
                        innerHTML: tchat.innerHTML.substring(0, 2000)
                    };
                }

                // All elements in the right area (x > 900) with text content
                const allEls = document.querySelectorAll('div, p, span, section');
                for (const el of allEls) {
                    const rect = el.getBoundingClientRect();
                    if (rect.x < 900 || rect.width < 50) continue;
                    const text = (el.innerText || '').trim();
                    if (text.length < 10 || text.length > 3000) continue;
                    // Check for message-like content (timestamps, conversations)
                    const isMessage = text.match(/(Aujourd|Hier|\\d{2}:\\d{2}|\\d{2}\\/\\d{2}|à \\d)/);
                    const isLong = text.length > 50 && text.includes('\\n');
                    if (isMessage || isLong) {
                        data.messageContainers.push({
                            tag: el.tagName, id: el.id || '',
                            classes: (el.className || '').toString().substring(0, 100),
                            x: Math.round(rect.x), y: Math.round(rect.y),
                            w: Math.round(rect.width), h: Math.round(rect.height),
                            textLen: text.length,
                            textPreview: text.substring(0, 300)
                        });
                    }
                }

                // Also check ALL divs with height > 200 anywhere on page
                for (const el of allEls) {
                    const rect = el.getBoundingClientRect();
                    if (rect.height < 200 || rect.width < 200) continue;
                    const text = (el.innerText || '').trim();
                    if (text.length > 100 && text.match(/(Aujourd|Hier|\\d{2}:\\d{2})/)) {
                        data.allElements.push({
                            tag: el.tagName, id: el.id || '',
                            classes: (el.className || '').toString().substring(0, 100),
                            x: Math.round(rect.x), y: Math.round(rect.y),
                            w: Math.round(rect.width), h: Math.round(rect.height),
                            textLen: text.length,
                            textStart: text.substring(0, 200)
                        });
                    }
                }

                data.messageContainers = data.messageContainers.slice(0, 20);
                data.allElements = data.allElements.slice(0, 15);
                return data;
            }""")
            result["chat_dom"] = chat_dom
        else:
            result["error"] = "No discussions found to click"

    elif flow_name == "mailbox_conversation":
        await _navigate(page, "https://app.wyylde.com/fr-fr/mailbox/inbox")
        await asyncio.sleep(3)

        # Click first conversation
        clicked = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/mailbox/inbox/"]');
            for (const link of links) {
                const rect = link.getBoundingClientRect();
                if (rect.width > 0) { link.click(); return link.href; }
            }
            // Fallback: clickable items in the list
            const items = document.querySelectorAll('[class*="cursor-pointer"]');
            for (const item of items) {
                const rect = item.getBoundingClientRect();
                if (rect.x > 200 && rect.x < 600 && rect.width > 100) {
                    item.click();
                    return 'clicked_item: ' + item.innerText.trim().substring(0, 50);
                }
            }
            return null;
        }""")
        result["conversation_clicked"] = clicked
        await asyncio.sleep(3)

    result["url"] = page.url
    result["elements"] = await page.evaluate(EXTRACT_JS)

    screenshot_name = f"flow_{flow_name}.png"
    await page.screenshot(path=str(DOCS_DIR / screenshot_name))
    result["screenshot"] = screenshot_name

    return result


async def _explore_flow_tinder(page, flow_name: str) -> dict:
    result = {"flow": flow_name, "url": page.url}
    result["elements"] = await page.evaluate(EXTRACT_JS)
    await page.screenshot(path=str(DOCS_DIR / f"flow_{flow_name}.png"))
    result["screenshot"] = f"flow_{flow_name}.png"
    return result


async def _explore_flow_meetic(page, flow_name: str) -> dict:
    result = {"flow": flow_name, "url": page.url}
    result["elements"] = await page.evaluate(EXTRACT_JS)
    await page.screenshot(path=str(DOCS_DIR / f"flow_{flow_name}.png"))
    result["screenshot"] = f"flow_{flow_name}.png"
    return result


FLOW_HANDLERS = {
    "wyylde": _explore_flow_wyylde,
    "tinder": _explore_flow_tinder,
    "meetic": _explore_flow_meetic,
}


def _format_markdown(platform: str, pages_data: dict, flows_data: dict) -> str:
    """Format all exploration results as Markdown reference."""
    lines = [f"# {platform.title()} — Selectors & Navigation Reference\n"]
    lines.append("*Auto-generated by explorer.py — DO NOT EDIT MANUALLY*\n")
    lines.append("Use this document to find the correct CSS selectors for automation.\n")

    # Pages
    lines.append("\n# Pages\n")
    for page_name, data in pages_data.items():
        lines.append(f"\n---\n\n## {page_name}\n")
        lines.append(f"- **URL**: `{data.get('url', 'N/A')}`")
        lines.append(f"- **Screenshot**: `docs/{data.get('screenshot', '')}`\n")

        elements = data.get("elements", {})

        # Buttons — the most important for automation
        buttons = elements.get("buttons", [])
        if buttons:
            lines.append(f"\n### Buttons ({len(buttons)})\n")
            lines.append("| Text | SVG Icon | Selector | x,y |")
            lines.append("|------|----------|----------|-----|")
            for b in buttons:
                text = b["text"].replace("\n", " ").replace("|", "/")[:40]
                icon = b.get("svg_icon") or ""
                sel = b.get("selector", "").replace("|", "/")
                pos = f"{b['pos']['x']},{b['pos']['y']}"
                lines.append(f"| {text} | `{icon}` | `{sel}` | {pos} |")

        # Inputs
        inputs = elements.get("inputs", [])
        if inputs:
            lines.append(f"\n### Inputs ({len(inputs)})\n")
            lines.append("| Tag | Type/Role | Placeholder | Selector | x,y |")
            lines.append("|-----|-----------|-------------|----------|-----|")
            for i in inputs:
                role = i.get("role") or i.get("type", "")
                sel = i.get("selector", "")
                lines.append(f"| {i['tag']} | {role} | {i.get('placeholder','')[:25]} | `{sel}` | {i['pos']['x']},{i['pos']['y']} |")

        # Key navigation links
        links = elements.get("links", [])
        nav_links = [l for l in links if any(k in l["href"] for k in ["/member/", "/mailbox/", "/search/", "/messages/", "/dashboard", "/app/", "/matches", "/shuffle", "/conversation"])]
        if nav_links:
            lines.append(f"\n### Navigation Links ({len(nav_links)})\n")
            for l in nav_links[:15]:
                text = l["text"].replace("\n", " ")[:35]
                lines.append(f"- `{l['href']}` — {text}")

        # Icons summary
        icons = elements.get("icons", [])
        if icons:
            lines.append(f"\n### SVG Icons: `{', '.join(icons)}`\n")

    # Flows
    lines.append("\n\n# Interactive Flows\n")
    for flow_name, data in flows_data.items():
        lines.append(f"\n---\n\n## Flow: {flow_name}\n")
        lines.append(f"- **Final URL**: `{data.get('url', 'N/A')}`")
        lines.append(f"- **Screenshot**: `docs/{data.get('screenshot', '')}`\n")

        # Show flow-specific metadata
        for key, val in data.items():
            if key in ("flow", "url", "elements", "screenshot"):
                continue
            lines.append(f"- **{key}**: `{json.dumps(val, ensure_ascii=False)[:200]}`")

        elements = data.get("elements", {})
        inputs = elements.get("inputs", [])
        if inputs:
            lines.append(f"\n### Inputs available after flow\n")
            for i in inputs:
                sel = i.get("selector", "")
                lines.append(f"- `{sel}` — {i['tag']} type={i.get('type','')} placeholder=\"{i.get('placeholder','')}\" at ({i['pos']['x']},{i['pos']['y']})")

        buttons = elements.get("buttons", [])
        action_buttons = [b for b in buttons if b.get("svg_icon") in ("paper-plane", "send", "check") or any(w in b["text"].lower() for w in ("envoyer", "send", "suivre", "like", "crush", "coeur"))]
        if action_buttons:
            lines.append(f"\n### Action buttons\n")
            for b in action_buttons:
                lines.append(f"- **{b['text'][:40]}** icon=`{b.get('svg_icon','')}` selector=`{b.get('selector','')}` at ({b['pos']['x']},{b['pos']['y']})")

    return "\n".join(lines)


async def explore_site(platform: str, page) -> str:
    """Run full exploration of a platform. Returns path to generated document."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    pages = PLATFORM_PAGES.get(platform, [])
    flows = PLATFORM_FLOWS.get(platform, [])
    flow_handler = FLOW_HANDLERS.get(platform)

    pages_data = {}
    flows_data = {}

    # 1. Explore each page
    for page_name, url in pages:
        logger.info(f"[{platform}] Exploring page: {page_name}")
        try:
            await _navigate(page, url)
            await asyncio.sleep(3)
            elements = await page.evaluate(EXTRACT_JS)
            screenshot_name = f"{platform}_{page_name.lower().replace(' ', '_').replace('/', '_')}.png"
            await page.screenshot(path=str(DOCS_DIR / screenshot_name))
            pages_data[page_name] = {"url": page.url, "elements": elements, "screenshot": screenshot_name}
            logger.info(f"  -> {page.url} | {len(elements.get('buttons',[]))} buttons, {len(elements.get('inputs',[]))} inputs")
        except Exception as e:
            logger.error(f"  Error: {e}")
            pages_data[page_name] = {"url": url, "error": str(e), "elements": {}}

    # 2. Execute interactive flows
    if flow_handler:
        for flow_name in flows:
            logger.info(f"[{platform}] Exploring flow: {flow_name}")
            try:
                flow_data = await flow_handler(page, flow_name)
                flows_data[flow_name] = flow_data
                elements = flow_data.get("elements", {})
                logger.info(f"  -> {flow_data.get('url')} | {len(elements.get('buttons',[]))} buttons, {len(elements.get('inputs',[]))} inputs")
            except Exception as e:
                logger.error(f"  Error: {e}")
                flows_data[flow_name] = {"flow": flow_name, "error": str(e)}

    # 3. Generate Markdown document
    markdown = _format_markdown(platform, pages_data, flows_data)
    doc_path = DOCS_DIR / f"{platform}_selectors.md"
    doc_path.write_text(markdown, encoding="utf-8")

    # 4. Save raw JSON for programmatic access
    raw = {"pages": pages_data, "flows": flows_data}
    json_path = DOCS_DIR / f"{platform}_raw.json"
    json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(f"[{platform}] Reference document saved: {doc_path}")
    return str(doc_path)
