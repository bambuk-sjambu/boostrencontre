import asyncio
import logging
from ..session_manager import browser_sessions
from ..database import get_db
from ..browser_utils import (
    _safe_goto, find_tiptap_editor, type_in_editor, click_send_button,
    read_chat_content, explore_profile_in_new_tab, debug_editors,
)
from ..conversation_utils import (
    _human_delay, _human_delay_with_pauses, check_rejection, filter_ui_text, detect_our_last_message,
)
from ..rate_limiter import check_daily_limit, increment_daily_count
from ..messaging.ai_messages import generate_reply_message, MY_PROFILE
from ..messaging.conversation_manager import record_message as record_conv_message
from ..chat_utils import detect_last_sender
from .replies_helpers import (
    _log_rejection, _is_rejected, _replied_recently,
    _get_last_sent_message, _log_reply, _send_reply_in_editor,
    _close_sidebar_discussion,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# check_and_reply_unread: mailbox + sidebar full scan
# ──────────────────────────────────────────────────────────────

async def check_and_reply_unread(platform_name: str, style: str = "auto") -> list:
    session = browser_sessions.get(platform_name)
    if not session:
        return []

    allowed, current, limit = await check_daily_limit(platform_name, "replies")
    if not allowed:
        logger.warning(f"Daily reply limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []

    platform = session["platform"]
    my_pseudo = MY_PROFILE.get("pseudo", "ilvousenprie").lower()
    replied = []
    stats = {"mailbox_checked": 0, "mailbox_replied": 0, "sidebar_total": 0,
             "sidebar_replied": 0, "sidebar_waiting": 0, "sidebar_closed": 0,
             "sidebar_blocked": 0, "sidebar_skipped": 0, "editor_found": 0, "editor_not_found": 0}

    # ---- Part 1: Mailbox inbox ----
    try:
        logger.info("=" * 60)
        logger.info("PART 1: Checking mailbox inbox...")
        await _safe_goto(platform.page, platform.MAILBOX_URL)

        await platform.page.evaluate("""() => {
            const btn = document.querySelector('#inbox');
            if (btn) btn.click();
        }""")
        await asyncio.sleep(2)

        inbox_convs = await platform.page.evaluate("""() => {
            const results = [];
            const links = document.querySelectorAll('a[href*="/mailbox/inbox/"]');
            for (const link of links) {
                const rect = link.getBoundingClientRect();
                if (rect.width < 50 || rect.height < 20) continue;
                const text = (link.innerText || '').trim();
                if (text.length < 3) continue;
                const name = text.split('\\n')[0].trim();
                results.push({name, href: link.href, text: text.substring(0, 200)});
            }
            return results;
        }""")

        await platform.page.evaluate("""() => {
            const btn = document.querySelector('#sent');
            if (btn) btn.click();
        }""")
        await asyncio.sleep(2)

        sent_convs = await platform.page.evaluate("""() => {
            const results = [];
            const links = document.querySelectorAll('a[href*="/mailbox/"]');
            for (const link of links) {
                const rect = link.getBoundingClientRect();
                if (rect.width < 50 || rect.height < 20) continue;
                if (rect.x < 300 || rect.x > 600) continue;
                const text = (link.innerText || '').trim();
                if (text.length < 3) continue;
                const name = text.split('\\n')[0].trim();
                if (!link.href.includes('/mailbox/')) continue;
                results.push({name, href: link.href, text: text.substring(0, 200)});
            }
            return results;
        }""")

        seen_names = {c["name"] for c in inbox_convs}
        for sc in sent_convs:
            if sc["name"] not in seen_names:
                inbox_convs.append(sc)
                seen_names.add(sc["name"])

        logger.info(f"Mailbox: {len(inbox_convs)} conversations (recus + envoyes)")

        for conv in inbox_convs[:20]:
            name = conv["name"]
            stats["mailbox_checked"] += 1
            if name.lower() == my_pseudo:
                continue

            if await _is_rejected(platform_name, name):
                logger.info(f"  [{name}] Previously REJECTED, skipping forever")
                continue

            if await _replied_recently(platform_name, name, minutes=120):
                logger.info(f"  [{name}] Already replied <2h ago, skipping")
                continue

            try:
                href = conv.get("href", "")
                if not href:
                    continue

                clicked_conv = await platform.page.evaluate("""(targetHref) => {
                    const links = document.querySelectorAll('a[href*="/mailbox/inbox/"]');
                    for (const a of links) {
                        if (a.href === targetHref || a.href.includes(targetHref.split('/').pop())) {
                            a.click(); return true;
                        }
                    }
                    return false;
                }""", href)

                if not clicked_conv:
                    await platform.page.goto(href, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(4)

                conv_data = await platform.page.evaluate("""() => {
                    const result = {fullText: '', hasMessages: false};
                    const allDivs = document.querySelectorAll('div');
                    let bestText = '';
                    for (const el of allDivs) {
                        const rect = el.getBoundingClientRect();
                        if (rect.x >= 580 && rect.x <= 650 && rect.width > 280 && rect.width < 400 && rect.y > 60) {
                            const text = (el.innerText || '').trim();
                            if (text.length > bestText.length) bestText = text;
                        }
                    }
                    result.fullText = bestText.trim().substring(0, 3000);
                    result.hasMessages = result.fullText.length > 20;
                    return result;
                }""")

                full_text = conv_data.get("fullText", "")
                if not full_text or len(full_text) < 10:
                    continue

                if check_rejection(full_text):
                    logger.info(f"  [{name}] REJECTION detected -> STOP forever")
                    await _log_rejection(platform_name, name)
                    continue

                last_sent = await _get_last_sent_message(platform_name, name)
                if last_sent:
                    detection = detect_our_last_message(full_text, last_sent)
                    if detection["found"]:
                        if not detection["has_new_content"]:
                            logger.info(f"  [{name}] Our last msg found, nothing new ({detection['new_content_len']} chars) -> SKIP")
                            continue
                        logger.info(f"  [{name}] New content after our msg ({detection['new_content_len']} chars): {detection['new_content'][:80]}...")
                    else:
                        logger.info(f"  [{name}] Cannot find our last msg -> SKIP (safety)")
                        continue

                editor_pos = await find_tiptap_editor(platform.page, min_width=50)
                if not editor_pos.get("found"):
                    logger.warning(f"  [{name}] EDITOR NOT FOUND")
                    stats["editor_not_found"] += 1
                    continue
                stats["editor_found"] += 1

                # Record received message in conversation history
                try:
                    await record_conv_message(platform_name, name, "received", full_text[:500])
                except Exception as e:
                    logger.warning(f"Failed to record received message: {e}")

                reply = await generate_reply_message(
                    sender_name=name, conversation_text=full_text,
                    style=style, platform=platform_name
                )
                if not reply:
                    continue

                await type_in_editor(platform.page, editor_pos, reply)
                await click_send_button(platform.page)
                await asyncio.sleep(2)

                await _log_reply(platform_name, name, reply, action="auto_reply", style=style)
                await increment_daily_count(platform_name, "replies")
                replied.append({"name": name, "reply": reply, "source": "mailbox"})
                stats["mailbox_replied"] += 1
                logger.info(f"  [{name}] REPLIED: {reply[:60]}...")

            except Exception as e:
                logger.error(f"  [{name}] Error: {e}")

    except Exception as e:
        logger.error(f"Part 1 error: {e}")

    # ---- Part 2: ALL sidebar discussions ----
    try:
        logger.info("=" * 60)
        logger.info("PART 2: Checking ALL sidebar discussions...")
        await _safe_goto(platform.page, platform.LOGIN_URL)
        await platform.page.evaluate("""(url) => {
            if (!window.location.href.includes('/dashboard') && !window.location.href.endsWith('/fr-fr')) {
                window.location.href = url;
            }
        }""", platform.LOGIN_URL)
        await asyncio.sleep(5)

        await platform.page.mouse.click(1006, 760)
        await asyncio.sleep(2)

        await platform.page.mouse.move(1100, 400)
        for _ in range(15):
            await platform.page.mouse.wheel(0, 500)
            await asyncio.sleep(0.4)
        await asyncio.sleep(2)
        for _ in range(15):
            await platform.page.mouse.wheel(0, -500)
            await asyncio.sleep(0.2)
        await asyncio.sleep(1)

        all_discussions = await platform.page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const allEls = document.querySelectorAll('button, div');
            for (const el of allEls) {
                const rect = el.getBoundingClientRect();
                if (rect.x < 990 || rect.x > 1160) continue;
                if (rect.width < 150 || rect.width > 250) continue;
                if (rect.height < 10 || rect.height > 100) continue;
                const text = (el.innerText || '').trim().split('\\n')[0].trim();
                if (text.length < 2 || text.length > 45) continue;
                if (text.match(/^(Homme|Femme|Couple|Travesti|Discussion|contact|Pr.s|Chat|Recherche|LIVE|Mes contacts|Discussions en cours|\\d+\\s*(Discussions|ans)|#LCS|New|Envoy|Re.u)/i)) continue;
                if (text.match(/^(Bi|h.t.ro|Gay|F Bi|\\d+\\/\\d+\\s*ans)/)) continue;
                if (seen.has(text)) continue;
                seen.add(text);
                results.push({name: text, x: Math.round(rect.x), y: Math.round(rect.y),
                    w: Math.round(rect.width), h: Math.round(rect.height), tag: el.tagName});
            }
            return results;
        }""")

        stats["sidebar_total"] = len(all_discussions)
        logger.info(f"  Sidebar: {len(all_discussions)} discussions found")

        for disc_idx, disc_data in enumerate(all_discussions):
            disc_name = disc_data["name"]
            if disc_name.lower() == my_pseudo:
                continue

            if await _is_rejected(platform_name, disc_name):
                continue
            if await _replied_recently(platform_name, disc_name, minutes=60):
                stats["sidebar_skipped"] += 1
                continue

            try:
                # Scroll to and click
                await platform.page.evaluate("""(targetName) => {
                    const allEls = document.querySelectorAll('button, div');
                    for (const el of allEls) {
                        const text = (el.innerText || '').trim().split('\\n')[0].trim();
                        if (text !== targetName) continue;
                        const rect = el.getBoundingClientRect();
                        if (rect.x > 990 && rect.x < 1160 && rect.width > 150) {
                            el.scrollIntoView({block: 'center'}); return;
                        }
                    }
                }""", disc_name)
                await asyncio.sleep(0.5)

                await platform.page.evaluate("""(targetName) => {
                    const allEls = document.querySelectorAll('button, div');
                    for (const el of allEls) {
                        const text = (el.innerText || '').trim().split('\\n')[0].trim();
                        if (text !== targetName) continue;
                        const rect = el.getBoundingClientRect();
                        if (rect.x > 990 && rect.x < 1160 && rect.width > 150 && rect.y > 0 && rect.y < 800) {
                            el.click(); return;
                        }
                    }
                }""", disc_name)
                await asyncio.sleep(2)

                chat_data = await platform.page.evaluate("""(targetName) => {
                    const result = {text: '', blocked: false, popupFound: false};
                    if ((document.body.innerText || '').includes('filtres des messages')) result.blocked = true;
                    const candidates = [];
                    for (const div of document.querySelectorAll('div')) {
                        const rect = div.getBoundingClientRect();
                        if (rect.width < 150 || rect.width > 450) continue;
                        if (rect.height < 80) continue;
                        if (rect.x < 500 || rect.x > 850) continue;
                        const text = (div.innerText || '').trim();
                        if (text.length < 5) continue;
                        candidates.push({text: text.substring(0, 2500), len: text.length});
                    }
                    candidates.sort((a, b) => b.len - a.len);
                    if (candidates.length > 0) { result.text = candidates[0].text; result.popupFound = true; }
                    return result;
                }""", disc_name)

                if chat_data.get("blocked"):
                    stats["sidebar_blocked"] += 1
                    await _close_sidebar_discussion(platform.page, disc_name)
                    continue

                chat_content = chat_data.get("text", "")
                if not chat_content or len(chat_content) < 10:
                    stats["sidebar_closed"] += 1
                    await _close_sidebar_discussion(platform.page, disc_name)
                    continue

                if check_rejection(chat_content):
                    await _log_rejection(platform_name, disc_name)
                    await platform.page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)
                    continue

                last_sent = await _get_last_sent_message(platform_name, disc_name)
                has_their_msg = False
                if last_sent:
                    detection = detect_our_last_message(chat_content, last_sent)
                    if detection["found"]:
                        if not detection["has_new_content"]:
                            stats["sidebar_waiting"] += 1
                            await platform.page.keyboard.press("Escape")
                            await asyncio.sleep(0.3)
                            continue
                        has_their_msg = True
                    else:
                        await platform.page.keyboard.press("Escape")
                        await asyncio.sleep(0.3)
                        continue
                else:
                    has_their_msg = len(chat_content) > 15

                if not has_their_msg:
                    stats["sidebar_waiting"] += 1
                    await platform.page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)
                    continue

                editor_pos = await find_tiptap_editor(platform.page, min_width=80)
                if not editor_pos.get("found"):
                    stats["editor_not_found"] += 1
                    await platform.page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)
                    continue
                stats["editor_found"] += 1

                # Record received message in conversation history
                try:
                    await record_conv_message(platform_name, disc_name, "received", chat_content[:500])
                except Exception as e:
                    logger.warning(f"Failed to record received message: {e}")

                reply = await generate_reply_message(
                    sender_name=disc_name, conversation_text=chat_content,
                    style=style, platform=platform_name
                )
                if not reply:
                    await platform.page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)
                    continue

                await type_in_editor(platform.page, editor_pos, reply)
                await click_send_button(platform.page)
                await asyncio.sleep(2)

                await _log_reply(platform_name, disc_name, reply, action="auto_reply", style=style)
                await increment_daily_count(platform_name, "replies")
                replied.append({"name": disc_name, "reply": reply, "source": "sidebar"})
                stats["sidebar_replied"] += 1

                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"    -> ERROR: {e}")
                try:
                    await platform.page.keyboard.press("Escape")
                except Exception:
                    pass
            await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Part 2 error: {e}")

    logger.info("=" * 60)
    logger.info("REPLY SESSION COMPLETE -- STATS:")
    logger.info(f"  Mailbox: {stats['mailbox_checked']} checked, {stats['mailbox_replied']} replied")
    logger.info(f"  Sidebar: {stats['sidebar_total']} total")
    logger.info(f"    - Replied: {stats['sidebar_replied']}, Waiting: {stats['sidebar_waiting']}")
    logger.info(f"    - Closed: {stats['sidebar_closed']}, Blocked: {stats['sidebar_blocked']}")
    logger.info(f"    - Skipped: {stats['sidebar_skipped']}")
    logger.info(f"  Editors: {stats['editor_found']} found, {stats['editor_not_found']} NOT found")
    logger.info(f"  Total replies: {len(replied)}")
    logger.info("=" * 60)

    return replied


# ──────────────────────────────────────────────────────────────
# reply_to_unread_sidebar: the full unread sidebar handler
# ──────────────────────────────────────────────────────────────

async def reply_to_unread_sidebar(platform_name: str, style: str = "auto") -> list:
    session = browser_sessions.get(platform_name)
    if not session:
        return []

    # Check daily rate limit before starting
    allowed, current, limit = await check_daily_limit(platform_name, "replies")
    if not allowed:
        logger.warning(f"Daily reply limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []

    platform = session["platform"]
    my_pseudo = MY_PROFILE.get("pseudo", "ilvousenprie").lower()
    replied = []

    await _safe_goto(platform.page, platform.LOGIN_URL)
    await asyncio.sleep(3)

    await platform.page.evaluate("""() => {
        const btn = document.querySelector('#headerOpenedTalks');
        if (btn) btn.click();
    }""")
    await asyncio.sleep(2)

    await platform.page.mouse.move(1100, 400)
    for scroll_try in range(15):
        found_header = await platform.page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                const text = (btn.innerText || '').trim();
                if (!text.includes('Discussion')) continue;
                const rect = btn.getBoundingClientRect();
                if (rect.x < 990 || rect.x > 1070) continue;
                if (rect.y > 0 && rect.y < 800) return text;
            }
            return null;
        }""")
        if found_header:
            logger.info(f"Found header '{found_header}' after {scroll_try} scrolls")
            break
        await platform.page.mouse.wheel(0, 500)
        await asyncio.sleep(0.3)
    await asyncio.sleep(1)

    # Collect discussions
    discussions_to_check = await platform.page.evaluate("""(myPseudo) => {
        const results = [];
        const seen = new Set();
        const allBtns = document.querySelectorAll('button');
        let nonLuesY = null, enCoursY = null;
        for (const btn of allBtns) {
            const text = (btn.innerText || '').trim();
            const rect = btn.getBoundingClientRect();
            if (rect.x < 990 || rect.x > 1060) continue;
            const style = window.getComputedStyle(btn);
            if (text.includes('Discussion') && text.includes('non lu'))
                if (style.backgroundColor.includes('236') || (rect.w > 200))
                    nonLuesY = rect.y;
            if (text.includes('Discussion') && text.includes('en cours'))
                if (rect.x > 990 && rect.x < 1060)
                    enCoursY = rect.y;
        }
        if (nonLuesY !== null) {
            const bottomY = enCoursY !== null ? enCoursY : 9999;
            const isCollapsed = enCoursY !== null && (enCoursY - nonLuesY) < 60;
            if (!isCollapsed) {
                for (const btn of allBtns) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.x < 990 || rect.x > 1070) continue;
                    if (rect.width < 50 || rect.width > 250) continue;
                    if (rect.height < 8 || rect.height > 45) continue;
                    if (rect.y < nonLuesY + 30 || rect.y > bottomY - 10) continue;
                    const name = (btn.innerText || '').trim();
                    if (name.length < 2 || name.length > 50) continue;
                    if (name.match(/^(\\d+\\s*Discussion|NOUVEAU|Homme|Femme|Couple)/i)) continue;
                    if (name.toLowerCase() === myPseudo) continue;
                    if (seen.has(name)) continue;
                    seen.add(name);
                    results.push({name, section: 'non_lues', btnType: 'small'});
                }
            }
        }
        if (enCoursY !== null) {
            for (const btn of allBtns) {
                const rect = btn.getBoundingClientRect();
                if (rect.x < 1000 || rect.x > 1020) continue;
                if (rect.width < 230 || rect.width > 260) continue;
                if (rect.height < 70 || rect.height > 100) continue;
                if (rect.y < enCoursY + 10) continue;
                const fullText = (btn.innerText || '').trim();
                const name = fullText.split('\\n')[0].trim();
                if (name.length < 2 || name.length > 50) continue;
                if (name.toLowerCase() === myPseudo) continue;
                if (seen.has(name)) continue;
                seen.add(name);
                const typeInfo = fullText.split('\\n').slice(1).join(' ').trim();
                results.push({name, section: 'en_cours', btnType: 'big', typeInfo});
            }
        }
        let frNonLuesY = null, frEnCoursY = null;
        const allEls = document.querySelectorAll('button, div, span, p');
        for (const el of allEls) {
            const rect = el.getBoundingClientRect();
            if (rect.x < 1200) continue;
            const text = (el.innerText || '').trim();
            if (text.includes('Discussion') && text.includes('non lu') && !frNonLuesY) frNonLuesY = rect.y;
            if (text.includes('Discussion') && text.includes('en cours') && !frEnCoursY) frEnCoursY = rect.y;
        }
        if (frNonLuesY !== null || frEnCoursY !== null) {
            for (const btn of allBtns) {
                const rect = btn.getBoundingClientRect();
                if (rect.x < 1200) continue;
                if (rect.width < 20 || rect.height < 8) continue;
                if (rect.y < 0 || rect.y > 1200) continue;
                const fullText = (btn.innerText || '').trim();
                const name = fullText.split('\\n')[0].trim();
                if (name.length < 2 || name.length > 50) continue;
                if (name.match(/^(\\d+\\s*Discussion|NOUVEAU|Mes contacts)/i)) continue;
                if (name.toLowerCase() === myPseudo) continue;
                if (seen.has(name)) continue;
                let farSection = 'far_right_en_cours';
                if (frNonLuesY !== null && frEnCoursY !== null) {
                    if (rect.y > frNonLuesY && rect.y < frEnCoursY) farSection = 'far_right_non_lues';
                } else if (frNonLuesY !== null && rect.y > frNonLuesY) {
                    farSection = 'far_right_non_lues';
                }
                seen.add(name);
                const btnType = rect.height > 50 ? 'big' : 'small';
                const typeInfo = fullText.split('\\n').slice(1).join(' ').trim();
                results.push({name, section: farSection, btnType, typeInfo: typeInfo || ''});
            }
        }
        return {results, nonLuesY, enCoursY, frNonLuesY, frEnCoursY,
                nonLuesCollapsed: nonLuesY !== null && enCoursY !== null && (enCoursY - nonLuesY) < 60};
    }""", my_pseudo)

    non_lues_collapsed = discussions_to_check.get("nonLuesCollapsed", False)
    disc_list = discussions_to_check.get("results", [])

    if non_lues_collapsed and discussions_to_check.get("nonLuesY") is not None:
        logger.info("Non-lues section collapsed -- clicking to expand")
        nly = discussions_to_check["nonLuesY"]
        await platform.page.mouse.click(1135, nly + 20)
        await asyncio.sleep(2)
        disc_list2 = await platform.page.evaluate("""(myPseudo) => {
            const results = [];
            const seen = new Set();
            const allBtns = document.querySelectorAll('button');
            let nonLuesY = null, enCoursY = null;
            for (const btn of allBtns) {
                const text = (btn.innerText || '').trim();
                const rect = btn.getBoundingClientRect();
                if (rect.x < 990 || rect.x > 1060) continue;
                const style = window.getComputedStyle(btn);
                if (text.includes('Discussion') && text.includes('non lu') && style.backgroundColor.includes('236'))
                    nonLuesY = rect.y;
                if (text.includes('Discussion') && text.includes('en cours'))
                    enCoursY = rect.y;
            }
            if (nonLuesY !== null) {
                const bottomY = enCoursY !== null ? enCoursY : 9999;
                for (const btn of allBtns) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.x < 990 || rect.x > 1070) continue;
                    if (rect.width < 50 || rect.width > 250) continue;
                    if (rect.height < 8 || rect.height > 45) continue;
                    if (rect.y < nonLuesY + 30 || rect.y > bottomY - 10) continue;
                    const name = (btn.innerText || '').trim();
                    if (name.length < 2 || name.length > 50) continue;
                    if (name.match(/^(\\d+\\s*Discussion|NOUVEAU|Homme|Femme|Couple)/i)) continue;
                    if (name.toLowerCase() === myPseudo) continue;
                    if (seen.has(name)) continue;
                    seen.add(name);
                    results.push({name, section: 'non_lues', btnType: 'small'});
                }
            }
            return results;
        }""", my_pseudo)
        en_cours = [d for d in disc_list if d["section"] == "en_cours"]
        disc_list = disc_list2 + en_cours

    # Scroll to collect all en-cours discussions
    seen_names = {d["name"] for d in disc_list}
    for scroll_pass in range(20):
        await platform.page.mouse.move(1100, 600)
        for _ in range(5):
            await platform.page.mouse.wheel(0, 600)
            await asyncio.sleep(0.15)
        await asyncio.sleep(0.5)
        more = await platform.page.evaluate("""(myPseudo) => {
            const results = [];
            const allBtns = document.querySelectorAll('button');
            for (const btn of allBtns) {
                const rect = btn.getBoundingClientRect();
                if (rect.x < 1000 || rect.x > 1020) continue;
                if (rect.width < 230 || rect.width > 260) continue;
                if (rect.height < 70 || rect.height > 100) continue;
                if (rect.y < 0 || rect.y > 1200) continue;
                const fullText = (btn.innerText || '').trim();
                const name = fullText.split('\\n')[0].trim();
                if (name.length < 2 || name.length > 50) continue;
                if (name.toLowerCase() === myPseudo) continue;
                const typeInfo = fullText.split('\\n').slice(1).join(' ').trim();
                results.push({name, section: 'en_cours', btnType: 'big', typeInfo});
            }
            return results;
        }""", my_pseudo)
        new_count = 0
        for d in more:
            if d["name"] not in seen_names:
                seen_names.add(d["name"])
                disc_list.append(d)
                new_count += 1
        if new_count == 0 and scroll_pass >= 2:
            break
        if new_count > 0:
            logger.info(f"Scroll pass {scroll_pass+1}: found {new_count} more discussions")

    non_lues = [d for d in disc_list if d["section"] == "non_lues"]
    en_cours = [d for d in disc_list if d["section"] == "en_cours"]
    far_right = [d for d in disc_list if d["section"].startswith("far_right")]
    logger.info(f"Found {len(non_lues)} non-lues + {len(en_cours)} en-cours + {len(far_right)} far-right discussions")

    # Process each discussion
    for idx, disc in enumerate(disc_list):
        name = disc["name"]
        section = disc["section"]
        logger.info(f"--- [{idx+1}/{len(disc_list)}] {section}: {name} ---")

        if await _replied_recently(platform_name, name, minutes=3):
            logger.info(f"  [{name}] Replied < 3min ago, skipping")
            continue

        try:
            is_far_right = section.startswith("far_right")
            if disc["btnType"] == "small":
                clicked = await platform.page.evaluate("""(args) => {
                    const [targetName, isFarRight] = args;
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const rect = btn.getBoundingClientRect();
                        if (isFarRight) { if (rect.x < 1200) continue; }
                        else { if (rect.x < 990 || rect.x > 1070) continue; }
                        if (rect.width < 20 || rect.width > 250) continue;
                        if (rect.height < 8 || rect.height > 45) continue;
                        const text = (btn.innerText || '').split('\\n')[0].trim();
                        if (text === targetName) { btn.scrollIntoView({block: 'center'}); btn.click(); return true; }
                    }
                    return false;
                }""", [name, is_far_right])
            else:
                clicked = await platform.page.evaluate("""(args) => {
                    const [targetName, isFarRight] = args;
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const rect = btn.getBoundingClientRect();
                        if (isFarRight) { if (rect.x < 1200) continue; }
                        else {
                            if (rect.x < 1000 || rect.x > 1020) continue;
                            if (rect.width < 230 || rect.width > 260) continue;
                            if (rect.height < 70 || rect.height > 100) continue;
                        }
                        const text = (btn.innerText || '').split('\\n')[0].trim();
                        if (text === targetName) { btn.scrollIntoView({block: 'center'}); btn.click(); return true; }
                    }
                    return false;
                }""", [name, is_far_right])

            if not clicked:
                scroll_x = 1250 if is_far_right else 1100
                await platform.page.mouse.move(scroll_x, 600)
                for _ in range(3):
                    await platform.page.mouse.wheel(0, 300)
                    await asyncio.sleep(0.3)
                await asyncio.sleep(0.5)
                clicked = await platform.page.evaluate("""(args) => {
                    const [targetName, isFarRight] = args;
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const rect = btn.getBoundingClientRect();
                        if (isFarRight) { if (rect.x < 1200) continue; }
                        else { if (rect.x < 990 || rect.x > 1070) continue; }
                        if (rect.width < 20 || rect.height < 8) continue;
                        const text = (btn.innerText || '').split('\\n')[0].trim();
                        if (text === targetName) { btn.scrollIntoView({block: 'center'}); btn.click(); return true; }
                    }
                    return false;
                }""", [name, is_far_right])
                if not clicked:
                    logger.info(f"  [{name}] Button not found even after scroll, skipping")
                    continue

            await asyncio.sleep(3)

            is_blocked = await platform.page.evaluate("""() => {
                const body = document.body.innerText || '';
                return body.includes('filtres des messages') || body.includes('filtre de message');
            }""")
            if is_blocked:
                logger.info(f"  [{name}] Blocked by message filters, skipping")
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                continue

            chat_data = await read_chat_content(platform.page, x_min=200, x_max=850, min_width=80, max_width=600)
            if not chat_data or len(chat_data.get("text", "")) < 30:
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                continue

            chat_content = chat_data["text"]

            last_sender = detect_last_sender(chat_content, my_pseudo, name)
            if last_sender == "me":
                logger.info(f"  [{name}] Last message is OURS, skipping")
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                continue
            if last_sender == "unknown":
                logger.warning(f"  [{name}] Could not determine last sender, skipping")
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                continue

            # Check rejection and rate limits before generating reply
            if await _is_rejected(platform_name, name):
                logger.info(f"  [{name}] Previously rejected, skipping")
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                continue

            if check_rejection(chat_content):
                logger.info(f"  [{name}] Rejection detected in chat, logging and skipping")
                await _log_rejection(platform_name, name)
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                continue

            if await _replied_recently(platform_name, name):
                logger.info(f"  [{name}] Already replied recently, skipping")
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                continue

            # Re-check daily limit mid-loop
            allowed, _, _ = await check_daily_limit(platform_name, "replies")
            if not allowed:
                logger.warning("Daily reply limit reached, stopping")
                break

            # Explore profile in new tab
            profile_info = {}
            if disc.get("typeInfo"):
                type_text = disc["typeInfo"]
                for prefix in ("Couple", "Homme", "Femme"):
                    if prefix in type_text:
                        profile_info["type"] = type_text.split("\n")[0].strip()
                        break

            profile_info.update(await explore_profile_in_new_tab(session["context"], platform.page, name))

            # Record received message in conversation history
            try:
                await record_conv_message(platform_name, name, "received", chat_content[:500])
            except Exception as e:
                logger.warning(f"Failed to record received message: {e}")

            editor_pos = await find_tiptap_editor(platform.page, min_width=80)
            if not editor_pos.get("found"):
                logger.warning(f"  [{name}] Editor not found")
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                continue

            reply = await generate_reply_message(
                sender_name=name, conversation_text=chat_content,
                style=style, profile_info=profile_info if profile_info else None,
                platform=platform_name
            )
            if not reply:
                await platform.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                continue

            await type_in_editor(platform.page, editor_pos, reply)
            await click_send_button(platform.page)
            await asyncio.sleep(2)

            await _log_reply(platform_name, name, reply, action="sidebar_reply", style=style)
            await increment_daily_count(platform_name, "replies")
            replied.append({"name": name, "reply": reply})
            logger.info(f"  [{name}] REPLIED: {reply[:60]}...")

            await platform.page.keyboard.press("Escape")
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"  [{name}] Error: {e}")
            try:
                await platform.page.keyboard.press("Escape")
            except Exception:
                pass

    # Step 3: Mailbox inbox
    logger.info("Checking mailbox inbox for unread messages...")
    try:
        await _safe_goto(platform.page, "https://app.wyylde.com/fr-fr/mailbox/inbox")
        await asyncio.sleep(3)

        inbox_convos = await platform.page.evaluate("""() => {
            const results = [];
            const links = document.querySelectorAll('a[href*="/mailbox/inbox/"]');
            for (const a of links) {
                const text = (a.innerText || '').trim();
                if (text.length < 3) continue;
                const name = text.split('\\n')[0].trim();
                if (name.length < 2 || name.length > 50) continue;
                results.push({name, href: a.href, preview: text.substring(0, 100)});
            }
            return results;
        }""")

        for conv in inbox_convos:
            iname = conv["name"]
            if iname.lower() == my_pseudo:
                continue
            if await _is_rejected(platform_name, iname):
                continue
            if await _replied_recently(platform_name, iname, minutes=3):
                continue
            # Re-check rate limit
            allowed, _, _ = await check_daily_limit(platform_name, "replies")
            if not allowed:
                logger.warning("Daily reply limit reached, stopping inbox scan")
                break

            try:
                await platform.page.evaluate("""(targetName) => {
                    const links = document.querySelectorAll('a[href*="/mailbox/inbox/"]');
                    for (const a of links) {
                        if ((a.innerText || '').trim().startsWith(targetName)) { a.click(); return true; }
                    }
                    return false;
                }""", iname)
                await asyncio.sleep(3)

                chat_data = await read_chat_content(platform.page, x_min=300, x_max=800, min_width=200, max_width=700)
                if not chat_data or len(chat_data.get("text", "")) < 30:
                    await platform.page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=10000)
                    await asyncio.sleep(1)
                    continue

                chat_content = chat_data["text"]

                last_sender = detect_last_sender(chat_content, my_pseudo, iname)
                if last_sender == "me":
                    logger.info(f"  [{iname}] Last message is OURS in inbox, skipping")
                    await platform.page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=10000)
                    await asyncio.sleep(1)
                    continue
                if last_sender == "unknown":
                    logger.warning(f"  [{iname}] Could not determine last sender in inbox, skipping")
                    await platform.page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=10000)
                    await asyncio.sleep(1)
                    continue

                if check_rejection(chat_content):
                    logger.info(f"  [{iname}] Rejection detected in inbox chat, skipping")
                    await _log_rejection(platform_name, iname)
                    await platform.page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=10000)
                    await asyncio.sleep(1)
                    continue

                profile_info = await explore_profile_in_new_tab(session["context"], platform.page, iname)

                # Record received message in conversation history
                try:
                    await record_conv_message(platform_name, iname, "received", chat_content[:500])
                except Exception as e:
                    logger.warning(f"Failed to record received message: {e}")

                editor_pos = await find_tiptap_editor(platform.page, min_width=100)
                if not editor_pos.get("found"):
                    logger.warning(f"  [{iname}] No editor in inbox conversation")
                    await platform.page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=10000)
                    await asyncio.sleep(1)
                    continue

                reply = await generate_reply_message(
                    sender_name=iname, conversation_text=chat_content,
                    style=style, profile_info=profile_info if profile_info else None,
                    platform=platform_name
                )
                if not reply:
                    continue

                await type_in_editor(platform.page, editor_pos, reply)
                await click_send_button(platform.page)
                await asyncio.sleep(2)

                await _log_reply(platform_name, iname, reply, action="sidebar_reply", style=style)
                await increment_daily_count(platform_name, "replies")
                replied.append({"name": iname, "reply": reply, "source": "inbox"})
                logger.info(f"  [{iname}] INBOX REPLIED: {reply[:60]}...")

                await platform.page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=10000)
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"  [{iname}] Inbox error: {e}")
                try:
                    await platform.page.goto("https://app.wyylde.com/fr-fr/mailbox/inbox", timeout=10000)
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Inbox check failed: {e}")

    logger.info(f"=== Reply done: {len(replied)} total replies sent ===")
    return replied
