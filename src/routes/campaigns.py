"""Campaign management routes."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import campaign_manager

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_PLATFORMS = {"tinder", "meetic", "wyylde"}


@router.post("/campaigns")
async def create_campaign_endpoint(request: Request):
    """Create a new campaign."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    name = data.get("name", "").strip()
    platform = data.get("platform", "").strip()

    if not name:
        return JSONResponse(status_code=400, content={"error": "missing_name"})
    if platform not in ALLOWED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})

    filters = {
        "target_type": data.get("target_type"),
        "age_min": data.get("age_min"),
        "age_max": data.get("age_max"),
        "location": data.get("location"),
        "desires": data.get("desires"),
        "style": data.get("style", "auto"),
        "max_contacts": data.get("max_contacts", 20),
    }

    campaign_id = await campaign_manager.create_campaign(name, platform, filters)
    return {"status": "created", "campaign_id": campaign_id}


@router.get("/campaigns/{platform}")
async def list_campaigns_endpoint(platform: str):
    """List all campaigns for a platform."""
    if platform not in ALLOWED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    campaigns = await campaign_manager.list_campaigns(platform)
    return {"campaigns": campaigns}


@router.get("/campaigns/detail/{campaign_id}")
async def get_campaign_endpoint(campaign_id: int):
    """Get campaign details with contacts and stats."""
    campaign = await campaign_manager.get_campaign(campaign_id)
    if not campaign:
        return JSONResponse(status_code=404, content={"error": "campaign_not_found"})
    stats = await campaign_manager.get_campaign_stats(campaign_id)
    return {"campaign": campaign, "stats": stats}


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign_endpoint(campaign_id: int):
    """Start or resume a campaign."""
    result = await campaign_manager.start_campaign(campaign_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign_endpoint(campaign_id: int):
    """Pause a campaign."""
    result = await campaign_manager.pause_campaign(campaign_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/campaigns/{campaign_id}/complete")
async def complete_campaign_endpoint(campaign_id: int):
    """Mark a campaign as completed."""
    result = await campaign_manager.complete_campaign(campaign_id)
    return result


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign_endpoint(campaign_id: int):
    """Delete a campaign and its contacts."""
    result = await campaign_manager.delete_campaign(campaign_id)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


@router.post("/campaigns/{campaign_id}/contacts")
async def add_contact_endpoint(campaign_id: int, request: Request):
    """Add a contact to a campaign."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    contact_name = data.get("contact_name", "").strip()
    if not contact_name:
        return JSONResponse(status_code=400, content={"error": "missing_contact_name"})

    result = await campaign_manager.add_contact_to_campaign(
        campaign_id,
        contact_name,
        contact_type=data.get("contact_type"),
        contact_age=data.get("contact_age"),
        score=data.get("score"),
    )
    return result


@router.put("/campaigns/contacts/{contact_id}/status")
async def update_contact_endpoint(contact_id: int, request: Request):
    """Update a contact's status."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    status = data.get("status", "").strip()
    if not status:
        return JSONResponse(status_code=400, content={"error": "missing_status"})

    kwargs = {}
    if "message_sent" in data:
        kwargs["message_sent"] = data["message_sent"]
    if "notes" in data:
        kwargs["notes"] = data["notes"]

    result = await campaign_manager.update_contact_status_by_id(
        contact_id, status, **kwargs
    )
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result
