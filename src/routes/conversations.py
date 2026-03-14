"""Conversation history routes: list, detail, stats."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..messaging.conversation_manager import (
    list_conversations,
    get_full_conversation,
    get_conversation_stats,
    get_conversation_stage,
)

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_PLATFORMS = {"tinder", "meetic", "wyylde"}


@router.get("/conversations/{platform}")
async def api_list_conversations(platform: str):
    """List all conversations with stage, last message, number of turns."""
    if platform not in ALLOWED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    try:
        convs = await list_conversations(platform)
        return {"conversations": convs, "count": len(convs)}
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/conversations/{platform}/{contact_name}")
async def api_get_conversation(platform: str, contact_name: str):
    """Full message history for a specific conversation."""
    if platform not in ALLOWED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    try:
        messages = await get_full_conversation(platform, contact_name)
        stage_data = await get_conversation_stage(platform, contact_name)
        return {
            "contact_name": contact_name,
            "messages": messages,
            "stage": stage_data["stage"],
            "stage_info": {
                "description": stage_data["stage_info"]["description"],
                "prompt_addon": stage_data["stage_info"]["prompt_addon"],
            },
            "sent_count": stage_data["sent_count"],
            "received_count": stage_data["received_count"],
            "total_turns": stage_data["total_turns"],
        }
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/conversation-stats/{platform}")
async def api_conversation_stats(platform: str):
    """Conversation statistics: count by stage, progression rates, etc."""
    if platform not in ALLOWED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    try:
        stats = await get_conversation_stats(platform)
        return stats
    except Exception as e:
        logger.error(f"Error getting conversation stats: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
