"""Browser management routes: open, check login, screenshot, close."""

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import bot_engine
from ..database import get_db
from .deps import validate_platform

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared state — injected from app.py at startup
running_jobs: dict = {}
job_results: dict = {}


def init(jobs: dict, results: dict):
    """Initialize shared references from the main app module."""
    global running_jobs, job_results
    running_jobs = jobs
    job_results = results


async def _open_browser_task(platform: str):
    try:
        result = await bot_engine.launch_browser(platform)
        async with await get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM accounts WHERE platform = ?", (platform,)
            )
            if not await cursor.fetchone():
                await db.execute(
                    "INSERT INTO accounts (platform) VALUES (?)", (platform,)
                )
                await db.commit()
        job_results[f"browser_{platform}"] = result
    except Exception as e:
        job_results[f"browser_{platform}"] = {"status": "error", "message": str(e)}
    finally:
        running_jobs.pop(f"browser_{platform}", None)


@router.post("/browser/{platform}")
async def open_browser(platform: str):
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    job_key = f"browser_{platform}"
    if platform in bot_engine.browser_sessions:
        return {"status": "already_open", "platform": platform}
    if job_key in running_jobs:
        return {"status": "opening", "message": f"{platform} est en cours d'ouverture..."}
    task = asyncio.create_task(_open_browser_task(platform))
    running_jobs[job_key] = task
    return {"status": "opening", "message": f"Ouverture de {platform}... Le navigateur va s'ouvrir."}


@router.get("/check-login/{platform}")
async def check_login(platform: str):
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    logged_in = await bot_engine.check_login(platform)
    if logged_in:
        await bot_engine.save_session(platform)
    return {"logged_in": logged_in}


@router.get("/screenshot/{platform}")
async def screenshot(platform: str):
    """Take a screenshot of the current page."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return JSONResponse(status_code=400, content={"error": "not_connected"})
    page = session["platform"].page
    path = f"/tmp/{platform}_screenshot.png"
    await page.screenshot(path=path, full_page=False)
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="image/png")


@router.post("/close/{platform}")
async def close_browser(platform: str):
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    await bot_engine.close_browser(platform)
    return {"status": "closed"}
