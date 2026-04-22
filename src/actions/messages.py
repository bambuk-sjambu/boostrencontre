import asyncio
import logging
from ..session_manager import browser_sessions
from ..database import get_db
from ..conversation_utils import _human_delay_with_pauses
from ..rate_limiter import check_daily_limit, increment_daily_count
from ..messaging.ai_messages import generate_first_message, MY_PROFILE
from ..scoring import score_profile, save_score

logger = logging.getLogger(__name__)

# Minimum score thresholds for message actions
MIN_SCORE_MESSAGE = 40  # Grade D profiles are skipped

ALL_MESSAGE_ACTIONS = ('message', 'sidebar_msg', 'search_msg')


async def _was_already_messaged(platform_name: str, name: str) -> bool:
    """Check if we already sent any type of message to this contact."""
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM activity_log WHERE platform = ? "
            "AND action IN ('message', 'sidebar_msg', 'search_msg') AND target_name = ?",
            (platform_name, name)
        )
        return bool(await cursor.fetchone())


async def run_messages(platform_name: str, style: str = "auto") -> list:
    session = browser_sessions.get(platform_name)
    if not session:
        return []

    allowed, current, limit = await check_daily_limit(platform_name, "messages")
    if not allowed:
        logger.warning(f"Daily message limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []

    async with await get_db() as db:
        cursor = await db.execute("SELECT * FROM settings WHERE id = 1")
        settings = await cursor.fetchone()

    max_messages = settings[2] if settings else 3
    max_messages = min(max_messages, limit - current)
    platform = session["platform"]
    matches = await platform.get_matches()

    sent = []
    my_pseudo = MY_PROFILE.get("pseudo", "").lower()

    for match in matches:
        if len(sent) >= max_messages:
            break
        try:
            if match["name"].lower() in (my_pseudo, my_pseudo[:2]):
                continue

            if await _was_already_messaged(platform_name, match["name"]):
                logger.info(f"Already messaged {match['name']}, skipping")
                continue

            profile_info = await platform.navigate_to_profile(match["id"])
            if not profile_info:
                continue
            if not profile_info.get("name"):
                profile_info["name"] = match["name"]

            # Score the profile before messaging
            score_result = await score_profile(profile_info, platform=platform_name)
            await save_score(platform_name, match["name"], score_result,
                             target_type=profile_info.get("type", ""))
            logger.info(f"Score {match['name']}: {score_result['total']}/100 "
                        f"(grade={score_result['grade']}, rec={score_result['recommendation']})")

            if score_result["total"] < MIN_SCORE_MESSAGE:
                logger.info(f"Skipping {match['name']}: score {score_result['total']} < {MIN_SCORE_MESSAGE}")
                continue

            # Use suggested style unless user explicitly chose one
            effective_style = style if style != "auto" else score_result["suggested_style"]

            message = await generate_first_message(profile_info, style=effective_style)
            success = await platform.send_message_from_profile(message)

            if success:
                async with await get_db() as db:
                    await db.execute(
                        "INSERT INTO activity_log (platform, action, target_name, message_sent, style) VALUES (?, ?, ?, ?, ?)",
                        (platform_name, "message", match["name"], message, effective_style)
                    )
                    await db.commit()
                await increment_daily_count(platform_name, "messages")
                sent.append({"name": match["name"], "message": message, "score": score_result["total"]})
                logger.info(f"Message sent to {match['name']}: {message[:50]}...")

            await _human_delay_with_pauses(2.0, 5.0)

        except Exception as e:
            logger.error(f"Error messaging {match.get('name')}: {e}")

    return sent


async def message_discussions(platform_name: str, count: int = 5, style: str = "auto") -> list:
    if platform_name != "wyylde":
        logger.warning(
            f"message_discussions uses the Wyylde chat sidebar — not applicable to {platform_name}. "
            f"Use run_messages for match-based platforms."
        )
        return []

    session = browser_sessions.get(platform_name)
    if not session:
        return []

    allowed, current, limit = await check_daily_limit(platform_name, "messages")
    if not allowed:
        logger.warning(f"Daily message limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []
    count = min(count, limit - current)

    platform = session["platform"]
    my_pseudo = MY_PROFILE.get("pseudo", "ilvousenprie").lower()
    sent = []
    attempts = 0

    while len(sent) < count and attempts < count * 3:
        attempts += 1

        await platform._ensure_chat_sidebar_visible()
        await platform._open_discussions_list()
        await asyncio.sleep(1)

        visible_conv = await platform.page.evaluate("""(skipNames) => {
            const seen = new Set();
            const allEls = document.querySelectorAll('button, div, span');
            for (const el of allEls) {
                const rect = el.getBoundingClientRect();
                const text = (el.innerText || '').trim();
                if (rect.x < 1020 || rect.x > 1150) continue;
                if (rect.y < 0 || rect.y > 1080) continue;
                if (rect.height > 45 || rect.height < 8 || rect.width < 30) continue;
                if (text.length < 3 || text.length > 40) continue;
                if (text.match(/(Homme|Femme|Couple|Travesti|Gay|Transgenre|Discussion|contact|Près|Chat|Recherche|LIVE|voyeur|\\d+\\s*ans|#LCS|New)/i)) continue;
                if (seen.has(text) || skipNames.includes(text)) continue;
                seen.add(text);
                el.click();
                return {name: text, x: Math.round(rect.x), y: Math.round(rect.y), clicked: true};
            }
            return {clicked: false};
        }""", [c["name"] for c in sent] + [my_pseudo])

        if not visible_conv.get("clicked"):
            logger.info("No more visible discussions to click")
            await platform.page.evaluate("""() => {
                const ctn = document.getElementById('ctn');
                if (ctn) ctn.scrollTop += 300;
            }""")
            await asyncio.sleep(1)
            continue

        name = visible_conv["name"]
        logger.info(f"Clicked discussion: {name}")

        if await _was_already_messaged(platform_name, name):
            logger.info(f"Already messaged {name}, skipping")
            continue

        try:
            await asyncio.sleep(3)
            for _ in range(10):
                if "/member/" in platform.page.url:
                    break
                await asyncio.sleep(1)

            if "/member/" not in platform.page.url:
                logger.info(f"Not on profile page for {name} (url={platform.page.url}), skipping")
                continue

            profile_info = await platform._get_current_profile()
            if not profile_info.get("name"):
                profile_info["name"] = name
            logger.info(f"Profile: {profile_info['name']} | {profile_info.get('type')} | bio={profile_info.get('bio', '')[:60]}...")

            # Score the profile before messaging
            score_result = await score_profile(profile_info)
            await save_score(platform_name, name, score_result,
                             target_type=profile_info.get("type", ""))
            logger.info(f"Score {name}: {score_result['total']}/100 "
                        f"(grade={score_result['grade']}, rec={score_result['recommendation']})")

            if score_result["total"] < MIN_SCORE_MESSAGE:
                logger.info(f"Skipping {name}: score {score_result['total']} < {MIN_SCORE_MESSAGE}")
                continue

            # Use suggested style unless user explicitly chose one
            effective_style = style if style != "auto" else score_result["suggested_style"]

            message = await generate_first_message(profile_info, style=effective_style)
            success = await platform.send_message_from_profile(message)

            if success:
                async with await get_db() as db:
                    await db.execute(
                        "INSERT INTO activity_log (platform, action, target_name, message_sent, style) VALUES (?, ?, ?, ?, ?)",
                        (platform_name, "sidebar_msg", name, message, effective_style)
                    )
                    await db.commit()
                await increment_daily_count(platform_name, "messages")
                sent.append({"name": name, "message": message, "score": score_result["total"]})
                logger.info(f"Message sent to {name}: {message[:50]}...")

            await _human_delay_with_pauses(2.0, 5.0)

        except Exception as e:
            logger.error(f"Error messaging {name}: {e}")

    return sent


async def message_from_search(platform_name: str, count: int = 5, style: str = "auto",
                              profile_type: str = "", desires: list = None,
                              approach_template: str = "") -> list:
    if platform_name != "wyylde":
        logger.warning(
            f"message_from_search uses the Wyylde search page — not applicable to {platform_name}."
        )
        return []

    session = browser_sessions.get(platform_name)
    if not session:
        return []

    allowed, current, limit = await check_daily_limit(platform_name, "messages")
    if not allowed:
        logger.warning(f"Daily message limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []
    count = min(count, limit - current)

    platform = session["platform"]
    my_pseudo = MY_PROFILE.get("pseudo", "ilvousenprie").lower()

    if profile_type or desires:
        await platform.apply_search_filters(profile_type=profile_type, desires=desires or [])

    results = await platform.get_search_results()
    if not results:
        logger.error("No search results found")
        return []

    sent = []
    skipped = 0

    for result in results:
        if len(sent) >= count:
            break
        if skipped > count * 3:
            break

        href = result["href"]
        try:
            await platform.page.goto(href, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(5)

            for _ in range(10):
                loading = await platform.page.evaluate("""() => {
                    return document.body.innerText.includes('Chargement en cours');
                }""")
                if not loading:
                    break
                await asyncio.sleep(1)

            if "/member/" not in platform.page.url:
                skipped += 1
                continue

            profile_info = await platform.read_full_profile()
            name = profile_info.get("name", "")

            if not name or name.lower() == my_pseudo:
                skipped += 1
                continue

            if profile_type:
                actual_type = profile_info.get("type", "").lower()
                if profile_type.lower() not in actual_type:
                    logger.info(f"Skipping {name}: type '{actual_type}' doesn't match filter '{profile_type}'")
                    skipped += 1
                    continue

            if await _was_already_messaged(platform_name, name):
                logger.info(f"Already messaged {name}, skipping")
                skipped += 1
                continue

            logger.info(f"Profile: {name} | {profile_info.get('type')} | "
                       f"bio={profile_info.get('bio', '')[:60]}... | "
                       f"prefs={profile_info.get('preferences', '')[:60]}...")

            # Score the profile before messaging
            score_result = await score_profile(profile_info)
            await save_score(platform_name, name, score_result,
                             target_type=profile_info.get("type", ""))
            logger.info(f"Score {name}: {score_result['total']}/100 "
                        f"(grade={score_result['grade']}, rec={score_result['recommendation']})")

            if score_result["total"] < MIN_SCORE_MESSAGE:
                logger.info(f"Skipping {name}: score {score_result['total']} < {MIN_SCORE_MESSAGE}")
                skipped += 1
                continue

            effective_style = style if style != "auto" else score_result["suggested_style"]

            message = await generate_first_message(profile_info, style=effective_style,
                                                   approach_template=approach_template)
            success = await platform.send_message_from_profile(message, stay_on_profile=True)

            if success:
                async with await get_db() as db:
                    await db.execute(
                        "INSERT INTO activity_log (platform, action, target_name, message_sent, style) VALUES (?, ?, ?, ?, ?)",
                        (platform_name, "search_msg", name, message, effective_style)
                    )
                    await db.commit()
                await increment_daily_count(platform_name, "messages")
                sent.append({"name": name, "message": message, "score": score_result["total"]})
                logger.info(f"Message sent to {name}: {message[:50]}...")
            else:
                logger.info(f"Failed to send to {name}, skipping")
                skipped += 1

            await _human_delay_with_pauses(2.0, 5.0)

        except Exception as e:
            logger.error(f"Error messaging from search: {e}")
            skipped += 1

    return sent
