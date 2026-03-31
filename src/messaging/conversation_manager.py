"""
Multi-turn conversation manager.

Tracks conversation history, determines conversation stage, and provides
stage-aware prompt addons for AI message generation.
"""

import logging
from ..database import get_db, dict_factory

logger = logging.getLogger(__name__)

# Conversation stages with progression rules
STAGES = {
    "accroche": {
        "description": "Premier contact, briser la glace",
        "max_turns": 1,
        "next": "interet",
        "prompt_addon": "C'est ton premier message. Sois accrocheur et original.",
    },
    "interet": {
        "description": "Creer de l'interet mutuel, explorer les affinites",
        "max_turns": 3,
        "next": "approfondissement",
        "prompt_addon": (
            "Vous avez deja echange. Approfondis la connexion, pose des questions "
            "sur ses envies, rebondis sur ce qu'elle/il dit. Montre un vrai interet."
        ),
    },
    "approfondissement": {
        "description": "Approfondir la relation, creer de la complicite",
        "max_turns": 4,
        "next": "proposition",
        "prompt_addon": (
            "La conversation avance bien. Cree de la complicite, partage des "
            "anecdotes, sois plus personnel. Laisse transparaitre tes desirs subtilement."
        ),
    },
    "proposition": {
        "description": "Proposer une rencontre ou un echange plus intime",
        "max_turns": 2,
        "next": "cloture",
        "prompt_addon": (
            "Le moment est venu de proposer quelque chose de concret : une rencontre, "
            "un verre, un echange plus intime. Sois naturel, pas pressant."
        ),
    },
    "cloture": {
        "description": "Conversation terminee — proposition faite, attendre une reponse",
        "max_turns": 0,
        "next": None,
        "prompt_addon": (
            "Tu as deja propose une rencontre. Ne relance pas. "
            "Si la personne repond, sois naturel et confirme les details."
        ),
    },
}

# Ordered list for stage progression
_STAGE_ORDER = ["accroche", "interet", "approfondissement", "proposition", "cloture"]

# Keywords that indicate strong interest (used for stage transition)
_INTEREST_SIGNALS = [
    "envie", "on pourrait", "on se voit", "rencontre", "retrouver",
    "quand", "ou ca", "chez", "hotel", "adresse", "numero", "telephone",
    "whatsapp", "snap", "insta", "discord", "venir", "rejoindre",
    "excite", "hate", "impatient", "curieu", "tentant", "tente",
]

# Keywords that indicate disinterest
_DISINTEREST_SIGNALS = [
    "sais pas", "peut-etre", "on verra", "pas sur", "pas le moment",
    "occupe", "busy", "plus tard", "relance",
]


def _determine_stage_by_turns(sent_count: int) -> str:
    """Determine stage based on the number of messages we have sent."""
    cumulative = 0
    for stage_name in _STAGE_ORDER:
        cumulative += STAGES[stage_name]["max_turns"]
        if sent_count <= cumulative:
            return stage_name
    return "cloture"


async def get_conversation_stage(platform: str, contact_name: str) -> dict:
    """Return the current stage and conversation metadata.

    Returns:
        dict with keys: stage, stage_info, sent_count, received_count,
        total_turns, history (list of recent messages).
    """
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT direction, message_text, stage, turn_number, style_used, created_at "
            "FROM conversation_history "
            "WHERE platform = ? AND contact_name = ? "
            "ORDER BY created_at ASC",
            (platform, contact_name),
        )
        rows = await cursor.fetchall()

    sent_count = sum(1 for r in rows if r["direction"] == "sent")
    received_count = sum(1 for r in rows if r["direction"] == "received")
    total_turns = len(rows)

    if total_turns == 0:
        stage = "accroche"
    else:
        # Use the stage of the last recorded message, or compute from turns
        last_stage = rows[-1].get("stage")
        if last_stage and last_stage in STAGES:
            stage = last_stage
        else:
            stage = _determine_stage_by_turns(sent_count)

    return {
        "stage": stage,
        "stage_info": STAGES[stage],
        "sent_count": sent_count,
        "received_count": received_count,
        "total_turns": total_turns,
        "history": rows,
    }


async def record_message(
    platform: str,
    contact_name: str,
    direction: str,
    message_text: str,
    style: str = None,
):
    """Record a sent or received message in conversation_history."""
    conv = await get_conversation_stage(platform, contact_name)
    stage = conv["stage"]
    turn_number = conv["total_turns"] + 1

    async with await get_db() as db:
        await db.execute(
            "INSERT INTO conversation_history "
            "(platform, contact_name, direction, message_text, stage, turn_number, style_used) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (platform, contact_name, direction, message_text, stage, turn_number, style),
        )
        await db.commit()

    logger.info(
        f"Recorded {direction} message for {contact_name} "
        f"(stage={stage}, turn={turn_number})"
    )


async def get_conversation_summary(platform: str, contact_name: str) -> str:
    """Return a formatted summary of the last N messages for prompt injection."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT direction, message_text, created_at "
            "FROM conversation_history "
            "WHERE platform = ? AND contact_name = ? "
            "ORDER BY created_at DESC LIMIT 10",
            (platform, contact_name),
        )
        rows = await cursor.fetchall()

    if not rows:
        return ""

    # Reverse to chronological order
    rows = list(reversed(rows))
    lines = []
    for r in rows:
        who = "Moi" if r["direction"] == "sent" else contact_name
        text = (r["message_text"] or "")[:200]
        lines.append(f"{who}: {text}")

    return "\n".join(lines)


async def detect_stage_transition(
    platform: str, contact_name: str, latest_reply: str
) -> str:
    """Detect if we should advance (or stay) in the conversation stage.

    Analyses the latest received reply for interest signals and decides
    whether to transition to the next stage.

    Returns:
        The new stage name (may be the same as current).
    """
    conv = await get_conversation_stage(platform, contact_name)
    current_stage = conv["stage"]
    sent_count = conv["sent_count"]
    stage_info = STAGES[current_stage]

    # Check cumulative turns for this stage
    stage_idx = _STAGE_ORDER.index(current_stage)
    cumulative_before = sum(
        STAGES[s]["max_turns"] for s in _STAGE_ORDER[:stage_idx]
    )
    turns_in_stage = sent_count - cumulative_before

    lower_reply = (latest_reply or "").lower()

    # Count interest and disinterest signals
    interest_hits = sum(1 for s in _INTEREST_SIGNALS if s in lower_reply)
    disinterest_hits = sum(1 for s in _DISINTEREST_SIGNALS if s in lower_reply)

    new_stage = current_stage

    if interest_hits >= 2 and stage_info["next"]:
        # Strong interest: advance immediately
        new_stage = stage_info["next"]
        logger.info(
            f"Stage transition for {contact_name}: {current_stage} -> {new_stage} "
            f"(strong interest: {interest_hits} signals)"
        )
    elif turns_in_stage >= stage_info["max_turns"] and stage_info["next"]:
        if disinterest_hits == 0:
            # Max turns reached with no disinterest: advance
            new_stage = stage_info["next"]
            logger.info(
                f"Stage transition for {contact_name}: {current_stage} -> {new_stage} "
                f"(max turns reached)"
            )
        else:
            logger.info(
                f"Staying at stage {current_stage} for {contact_name} "
                f"(disinterest signals detected)"
            )

    # Update the stage on existing records if changed
    if new_stage != current_stage:
        async with await get_db() as db:
            await db.execute(
                "UPDATE conversation_history SET stage = ? "
                "WHERE platform = ? AND contact_name = ? "
                "AND id = (SELECT MAX(id) FROM conversation_history "
                "WHERE platform = ? AND contact_name = ?)",
                (new_stage, platform, contact_name, platform, contact_name),
            )
            await db.commit()

    return new_stage


async def get_conversation_stats(platform: str) -> dict:
    """Return conversation statistics for the given platform.

    Returns dict with:
        - total_conversations: int
        - by_stage: dict of stage -> count
        - avg_turns: float
        - stage_progression: dict of stage -> count that advanced to next stage
    """
    async with await get_db() as db:
        db.row_factory = dict_factory

        # Count distinct conversations
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT contact_name) as cnt "
            "FROM conversation_history WHERE platform = ?",
            (platform,),
        )
        row = await cursor.fetchone()
        total = row["cnt"] if row else 0

        # Count by current stage (latest stage per contact)
        cursor = await db.execute(
            "SELECT stage, COUNT(*) as cnt FROM ("
            "  SELECT contact_name, stage FROM conversation_history "
            "  WHERE platform = ? AND id IN ("
            "    SELECT MAX(id) FROM conversation_history "
            "    WHERE platform = ? GROUP BY contact_name"
            "  )"
            ") GROUP BY stage",
            (platform, platform),
        )
        stage_rows = await cursor.fetchall()
        by_stage = {s: 0 for s in _STAGE_ORDER}
        for r in stage_rows:
            if r["stage"] in by_stage:
                by_stage[r["stage"]] = r["cnt"]

        # Average turns per conversation
        cursor = await db.execute(
            "SELECT AVG(turn_count) as avg_t FROM ("
            "  SELECT COUNT(*) as turn_count FROM conversation_history "
            "  WHERE platform = ? GROUP BY contact_name"
            ")",
            (platform,),
        )
        avg_row = await cursor.fetchone()
        avg_turns = round(avg_row["avg_t"], 1) if avg_row and avg_row["avg_t"] else 0.0

        # Stage progression: contacts that have gone beyond each stage
        progression = {}
        for i, stage_name in enumerate(_STAGE_ORDER[:-1]):
            next_stages = _STAGE_ORDER[i + 1:]
            placeholders = ",".join("?" * len(next_stages))
            cursor = await db.execute(
                f"SELECT COUNT(DISTINCT contact_name) as cnt "
                f"FROM conversation_history "
                f"WHERE platform = ? AND stage IN ({placeholders})",
                (platform, *next_stages),
            )
            prog_row = await cursor.fetchone()
            progression[stage_name] = prog_row["cnt"] if prog_row else 0

    return {
        "total_conversations": total,
        "by_stage": by_stage,
        "avg_turns": avg_turns,
        "stage_progression": progression,
    }


async def list_conversations(platform: str) -> list:
    """Return a list of all conversations with metadata for the dashboard."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT contact_name, "
            "  MAX(id) as last_id, "
            "  COUNT(*) as turn_count, "
            "  SUM(CASE WHEN direction='sent' THEN 1 ELSE 0 END) as sent_count, "
            "  SUM(CASE WHEN direction='received' THEN 1 ELSE 0 END) as received_count "
            "FROM conversation_history "
            "WHERE platform = ? "
            "GROUP BY contact_name "
            "ORDER BY last_id DESC",
            (platform,),
        )
        convs = await cursor.fetchall()

        # Fetch last message and stage for each conversation
        result = []
        for c in convs:
            cursor2 = await db.execute(
                "SELECT message_text, direction, stage, created_at "
                "FROM conversation_history WHERE id = ?",
                (c["last_id"],),
            )
            last_msg = await cursor2.fetchone()
            result.append({
                "contact_name": c["contact_name"],
                "turn_count": c["turn_count"],
                "sent_count": c["sent_count"],
                "received_count": c["received_count"],
                "stage": last_msg["stage"] if last_msg else "accroche",
                "last_message": (last_msg["message_text"] or "")[:100] if last_msg else "",
                "last_direction": last_msg["direction"] if last_msg else "",
                "last_at": last_msg["created_at"] if last_msg else "",
            })

    return result


async def get_full_conversation(platform: str, contact_name: str) -> list:
    """Return the full message history for a specific conversation."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT direction, message_text, stage, turn_number, style_used, created_at "
            "FROM conversation_history "
            "WHERE platform = ? AND contact_name = ? "
            "ORDER BY created_at ASC",
            (platform, contact_name),
        )
        return await cursor.fetchall()
