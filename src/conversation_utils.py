import asyncio
import random
import re
from .constants import REJECTION_PATTERNS, UI_PATTERNS, TIMESTAMP_CLEANUP_REGEX


async def _human_delay(min_s: float = 1.5, max_s: float = 4.0):
    """Delay with a gaussian distribution centered between min and max."""
    mean = (min_s + max_s) / 2
    std = (max_s - min_s) / 4  # 95% of values fall within [min, max]
    delay = max(min_s, min(max_s, random.gauss(mean, std)))
    await asyncio.sleep(delay)


_action_counters: dict = {}


async def _human_delay_with_pauses(min_s: float = 2.0, max_s: float = 5.0, platform: str = "default"):
    """Natural delay with random long pauses every 5-10 actions.

    Counters are tracked per platform to prevent cross-platform interference.
    """
    _action_counters[platform] = _action_counters.get(platform, 0) + 1
    _action_counter = _action_counters[platform]

    # Long pause every 5-10 actions (simulates a human looking at something else)
    if _action_counter % random.randint(5, 10) == 0:
        long_pause = random.gauss(20, 8)
        long_pause = max(8, min(45, long_pause))
        await asyncio.sleep(long_pause)
        return

    await _human_delay(min_s, max_s)


def check_rejection(text: str) -> bool:
    """Check if text (last 500 chars) contains rejection patterns."""
    tail = text[-500:] if len(text) > 500 else text
    for pat in REJECTION_PATTERNS:
        if re.search(pat, tail):
            return True
    return False


def filter_ui_text(text: str, sender_name: str = "") -> list:
    """Remove UI artifacts from chat text, return meaningful lines (len > 10)."""
    clean = text
    for pattern in UI_PATTERNS:
        clean = clean.replace(pattern, "")
    if sender_name:
        clean = clean.replace(sender_name, "").replace("Couple", "")
    clean = clean.strip()
    return [l.strip() for l in clean.split("\n") if len(l.strip()) > 10]


def detect_our_last_message(chat_text: str, last_sent_msg: str) -> dict:
    """Check if our last sent message is the most recent in the chat.
    Returns {found: bool, has_new_content: bool, new_content_len: int, new_content: str}."""
    result = {"found": False, "has_new_content": False, "new_content_len": 0, "new_content": ""}

    if not last_sent_msg:
        return result

    found_our_msg = False
    our_msg_end_idx = -1
    for slen in [60, 40, 25, 15]:
        snippet = last_sent_msg[:slen]
        idx = chat_text.rfind(snippet)
        if idx >= 0:
            found_our_msg = True
            our_msg_end_idx = min(idx + len(last_sent_msg), len(chat_text))
            break

    if not found_our_msg:
        return result

    result["found"] = True
    after_our_msg = chat_text[our_msg_end_idx:].strip()
    clean_after = re.sub(TIMESTAMP_CLEANUP_REGEX, '', after_our_msg).strip()
    result["new_content_len"] = len(clean_after)
    result["new_content"] = clean_after[:120]
    result["has_new_content"] = len(clean_after) >= 15

    return result
