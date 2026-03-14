"""Routes for email summary configuration and manual trigger."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..email_summary import (
    get_email_settings,
    save_email_settings,
    generate_summary,
    send_summary_email,
    start_scheduler,
    stop_scheduler,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/email-settings")
async def get_settings():
    """Get current email summary settings."""
    settings = await get_email_settings()
    # Never expose password in API response
    safe = {k: v for k, v in settings.items() if k != "smtp_password"}
    safe["smtp_password_set"] = bool(settings.get("smtp_password"))
    return safe


@router.post("/email-settings")
async def update_settings(request: Request):
    """Update email summary settings."""
    data = await request.json()

    current = await get_email_settings()

    allowed_keys = {
        "email_enabled", "email_recipient", "email_time",
        "smtp_host", "smtp_port", "smtp_user", "smtp_password",
    }
    for key in allowed_keys:
        if key in data:
            # Don't overwrite password with empty string if not provided
            if key == "smtp_password" and not data[key]:
                continue
            current[key] = data[key]

    # Validate email_time format
    email_time = current.get("email_time", "22:00")
    try:
        h, m = map(int, email_time.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        return JSONResponse(status_code=400, content={"error": "invalid_time_format"})

    await save_email_settings(current)

    # Start/stop scheduler based on enabled state
    if current.get("email_enabled"):
        start_scheduler()
    else:
        stop_scheduler()

    return {"status": "saved"}


@router.post("/email-send-now")
async def send_now():
    """Manually trigger the daily summary email."""
    result = await send_summary_email()
    if result["status"] == "error":
        return JSONResponse(status_code=500, content=result)
    return result


@router.get("/email-preview")
async def preview_email():
    """Preview today's email summary as HTML (without sending)."""
    summary = await generate_summary()
    return HTMLResponse(content=summary["html"])
