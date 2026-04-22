import logging
import random

from ..session_manager import browser_sessions
from ..database import get_db, dict_factory
from ..rate_limiter import check_daily_limit, increment_daily_count
from ..conversation_utils import _human_delay_with_pauses
from ..scoring import score_profile, save_score

logger = logging.getLogger(__name__)


async def run_likes(platform_name: str, profile_filter: str = "") -> list:
    session = browser_sessions.get(platform_name)
    if not session:
        return []

    # Check daily limit before starting
    allowed, current, limit = await check_daily_limit(platform_name, "likes")
    if not allowed:
        logger.warning(f"Daily like limit reached ({current}/{limit}) for {platform_name}, aborting")
        return []

    remaining = limit - current

    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute("SELECT * FROM settings WHERE id = 1")
        settings = await cursor.fetchone()

    likes_count = settings["likes_per_session"] if settings else 50
    delay_min = settings["delay_min"] if settings else 3
    delay_max = settings["delay_max"] if settings else 8

    # Cap to remaining daily quota
    likes_count = min(likes_count, remaining)

    platform = session["platform"]
    liked = await platform.like_profiles(
        likes_count, (delay_min, delay_max), profile_filter=profile_filter
    )

    async with await get_db() as db:
        for profile in liked:
            await db.execute(
                "INSERT INTO activity_log (platform, action, target_name) VALUES (?, ?, ?)",
                (platform_name, "like", profile.get("name", "Unknown"))
            )
        await db.commit()

    # Score liked profiles for analytics and future prioritization
    for profile in liked:
        try:
            score_result = await score_profile(profile, platform=platform_name)
            await save_score(platform_name, profile.get("name", "Unknown"),
                             score_result, target_type=profile.get("type", ""))
            profile["score"] = score_result["total"]
            logger.info(f"Scored {profile.get('name')}: {score_result['total']}/100 ({score_result['grade']})")
        except Exception as e:
            logger.debug(f"Could not score {profile.get('name')}: {e}")

    # Increment daily counters for each action performed
    for profile in liked:
        await increment_daily_count(platform_name, "likes")
        if profile.get("followed"):
            await increment_daily_count(platform_name, "follows")
        if profile.get("crushed"):
            await increment_daily_count(platform_name, "crushes")

    return liked
