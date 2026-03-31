"""Bot action routes: likes, messages, replies, search, auto-reply, job status."""

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import bot_engine
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


async def _run_likes_task(platform: str, profile_filter: str = ""):
    try:
        liked = await bot_engine.run_likes(platform, profile_filter=profile_filter)
        job_results[f"likes_{platform}"] = {"liked": liked, "count": len(liked), "status": "done"}
    except Exception as e:
        job_results[f"likes_{platform}"] = {"error": str(e), "status": "error"}
    finally:
        running_jobs.pop(f"likes_{platform}", None)


async def _run_messages_task(platform: str, style: str = "auto"):
    try:
        sent = await bot_engine.run_messages(platform, style=style)
        job_results[f"messages_{platform}"] = {"sent": sent, "count": len(sent), "status": "done"}
    except Exception as e:
        job_results[f"messages_{platform}"] = {"error": str(e), "status": "error"}
    finally:
        running_jobs.pop(f"messages_{platform}", None)


async def _run_replies_task(platform: str, style: str = "auto"):
    try:
        replied = await bot_engine.reply_to_unread_sidebar(platform, style=style)
        job_results[f"replies_{platform}"] = {"replied": replied, "count": len(replied), "status": "done"}
    except Exception as e:
        job_results[f"replies_{platform}"] = {"error": str(e), "status": "error"}
    finally:
        running_jobs.pop(f"replies_{platform}", None)


async def _run_discussion_messages_task(platform: str, count: int = 5, style: str = "auto"):
    try:
        sent = await bot_engine.message_discussions(platform, count=count, style=style)
        job_results[f"discussion_msg_{platform}"] = {"sent": sent, "count": len(sent), "status": "done"}
    except Exception as e:
        job_results[f"discussion_msg_{platform}"] = {"error": str(e), "status": "error"}
    finally:
        running_jobs.pop(f"discussion_msg_{platform}", None)


@router.post("/likes/{platform}")
async def run_likes(platform: str, request: Request):
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if platform not in bot_engine.browser_sessions:
        return JSONResponse(status_code=400, content={"error": "not_connected", "message": f"{platform} n'est pas connecte. Ouvre le navigateur d'abord."})
    logged_in = await bot_engine.check_login(platform)
    if not logged_in:
        return {"error": "not_logged_in", "message": f"Tu n'es pas connecte sur {platform}. Connecte-toi dans le navigateur ouvert."}
    profile_filter = ""
    try:
        body = await request.json()
        profile_filter = body.get("profile_filter", "")
    except Exception:
        pass
    job_key = f"likes_{platform}"
    if job_key in running_jobs:
        return {"status": "running", "message": f"Likes en cours sur {platform}..."}
    job_results.pop(job_key, None)
    task = asyncio.create_task(_run_likes_task(platform, profile_filter=profile_filter))
    running_jobs[job_key] = task
    return {"status": "started", "message": f"Likes lances sur {platform} ! Regarde le navigateur."}


@router.post("/messages/{platform}")
async def run_messages(platform: str, request: Request):
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if platform not in bot_engine.browser_sessions:
        return JSONResponse(status_code=400, content={"error": "not_connected", "message": f"{platform} n'est pas connecte. Ouvre le navigateur d'abord."})
    logged_in = await bot_engine.check_login(platform)
    if not logged_in:
        return {"error": "not_logged_in", "message": f"Tu n'es pas connecte sur {platform}. Connecte-toi dans le navigateur ouvert."}
    style = "auto"
    try:
        body = await request.json()
        style = body.get("style", "auto")
    except Exception:
        pass
    job_key = f"messages_{platform}"
    if job_key in running_jobs:
        return {"status": "running", "message": f"Messages en cours sur {platform}..."}
    job_results.pop(job_key, None)
    task = asyncio.create_task(_run_messages_task(platform, style=style))
    running_jobs[job_key] = task
    return {"status": "started", "message": f"Messages lances sur {platform} (style: {style}) ! Regarde le navigateur."}


@router.post("/replies/{platform}")
async def run_replies(platform: str, request: Request):
    """Reply to unread discussions in the right sidebar."""
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if platform not in bot_engine.browser_sessions:
        return JSONResponse(status_code=400, content={"error": "not_connected", "message": f"{platform} n'est pas connecte."})
    logged_in = await bot_engine.check_login(platform)
    if not logged_in:
        return {"error": "not_logged_in", "message": f"Non connecte sur {platform}."}
    style = "auto"
    try:
        body = await request.json()
        style = body.get("style", "auto")
    except Exception:
        pass
    job_key = f"replies_{platform}"
    if job_key in running_jobs:
        return {"status": "running", "message": f"Reponses en cours sur {platform}..."}
    job_results.pop(job_key, None)
    task = asyncio.create_task(_run_replies_task(platform, style=style))
    running_jobs[job_key] = task
    return {"status": "started", "message": f"Reponses aux non-lus sidebar lancees sur {platform} !"}


@router.post("/message-discussions/{platform}")
async def message_discussions(platform: str, request: Request):
    """Send personalized messages to sidebar discussions."""
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if platform not in bot_engine.browser_sessions:
        return JSONResponse(status_code=400, content={"error": "not_connected", "message": f"{platform} n'est pas connecte."})
    logged_in = await bot_engine.check_login(platform)
    if not logged_in:
        return {"error": "not_logged_in", "message": f"Non connecte sur {platform}."}
    count = 5
    style = "auto"
    try:
        body = await request.json()
        count = body.get("count", 5)
        style = body.get("style", "auto")
    except Exception:
        pass
    job_key = f"discussion_msg_{platform}"
    if job_key in running_jobs:
        return {"status": "running", "message": f"Messages discussions en cours sur {platform}..."}
    job_results.pop(job_key, None)
    task = asyncio.create_task(_run_discussion_messages_task(platform, count=count, style=style))
    running_jobs[job_key] = task
    return {"status": "started", "message": f"Envoi de messages aux {count} premieres discussions sur {platform} !"}


@router.post("/message-search/{platform}")
async def message_search(platform: str, request: Request):
    """Send personalized messages to profiles from search results."""
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if platform not in bot_engine.browser_sessions:
        return JSONResponse(status_code=400, content={"error": "not_connected", "message": f"{platform} n'est pas connecte."})
    logged_in = await bot_engine.check_login(platform)
    if not logged_in:
        return {"error": "not_logged_in", "message": f"Non connecte sur {platform}."}
    count = 5
    style = "auto"
    profile_type = ""
    desires = []
    approach_template = ""
    try:
        body = await request.json()
        count = body.get("count", 5)
        style = body.get("style", "auto")
        profile_type = body.get("profile_type", "")
        desires = body.get("desires", [])
        approach_template = body.get("approach_template", "")
    except Exception:
        pass

    async def _run_search_messages_task(plat, cnt, stl):
        try:
            result = await bot_engine.message_from_search(plat, count=cnt, style=stl,
                                                          profile_type=profile_type, desires=desires,
                                                          approach_template=approach_template)
            job_results[f"search_msg_{plat}"] = {"status": "done", "sent": result, "count": len(result)}
        except Exception as e:
            job_results[f"search_msg_{plat}"] = {"status": "error", "error": str(e)}
        finally:
            running_jobs.pop(f"search_msg_{plat}", None)

    job_key = f"search_msg_{platform}"
    if job_key in running_jobs:
        return {"status": "running", "message": "Recherche deja en cours."}
    job_results.pop(job_key, None)
    task = asyncio.create_task(_run_search_messages_task(platform, count, style))
    running_jobs[job_key] = task
    return {"status": "started", "message": f"Envoi de messages aux {count} premiers profils de recherche sur {platform} !"}


@router.post("/check-replies/{platform}")
async def check_replies_now(platform: str):
    """Manually trigger unread sidebar reply."""
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if platform not in bot_engine.browser_sessions:
        return JSONResponse(status_code=400, content={"error": "not_connected"})
    replied = await bot_engine.reply_to_unread_sidebar(platform)
    return {"status": "done", "replied": replied, "count": len(replied)}


@router.post("/auto-reply/{platform}")
async def auto_reply_toggle(platform: str, request: Request):
    """Start or stop auto-reply monitoring."""
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})
    if platform not in bot_engine.browser_sessions:
        return JSONResponse(status_code=400, content={"error": "not_connected"})
    action = "start"
    interval = 60
    style = "auto"
    try:
        body = await request.json()
        action = body.get("action", "start")
        interval = body.get("interval", 60)
        style = body.get("style", "auto")
    except Exception:
        pass
    if action == "stop":
        bot_engine.stop_auto_reply(platform)
        return {"status": "stopped"}
    else:
        bot_engine.start_auto_reply(platform, style=style, interval=interval)
        return {"status": "started", "interval": interval}


@router.get("/job-status/{job_type}/{platform}")
async def job_status(job_type: str, platform: str):
    job_key = f"{job_type}_{platform}"
    if job_key in running_jobs:
        return {"status": "running"}
    if job_key in job_results:
        result = job_results.pop(job_key)
        return result
    return {"status": "idle"}


@router.get("/daily-stats/{platform}")
async def get_daily_stats_endpoint(platform: str):
    """Return daily action counters and limits for the given platform."""
    from ..rate_limiter import get_daily_stats
    stats = await get_daily_stats(platform)
    return {"stats": stats, "date": str(date.today())}


@router.get("/profile-score/{platform}/{name}")
async def get_profile_score(platform: str, name: str):
    """Return the stored score for a specific profile."""
    from ..database import get_db, dict_factory
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT * FROM profile_scores WHERE platform = ? AND target_name = ?",
            (platform, name),
        )
        row = await cursor.fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "score_not_found"})
    return row


@router.get("/scoring-stats/{platform}")
async def get_scoring_stats(platform: str):
    """Return scoring statistics: distribution, averages, top profiles."""
    from ..database import get_db, dict_factory
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})

    async with await get_db() as db:
        db.row_factory = dict_factory

        # Grade distribution
        cursor = await db.execute(
            "SELECT grade, COUNT(*) as count FROM profile_scores "
            "WHERE platform = ? GROUP BY grade ORDER BY grade",
            (platform,),
        )
        distribution = await cursor.fetchall()

        # Average score by target type
        cursor = await db.execute(
            "SELECT target_type, ROUND(AVG(score), 1) as avg_score, COUNT(*) as count "
            "FROM profile_scores WHERE platform = ? AND target_type != '' "
            "GROUP BY target_type ORDER BY avg_score DESC",
            (platform,),
        )
        by_type = await cursor.fetchall()

        # Top 10 recent profiles
        cursor = await db.execute(
            "SELECT target_name, target_type, score, grade, recommendation, "
            "suggested_style, scored_at "
            "FROM profile_scores WHERE platform = ? "
            "ORDER BY score DESC LIMIT 10",
            (platform,),
        )
        top_profiles = await cursor.fetchall()

        # Overall stats
        cursor = await db.execute(
            "SELECT COUNT(*) as total, ROUND(AVG(score), 1) as avg_score, "
            "MAX(score) as max_score, MIN(score) as min_score "
            "FROM profile_scores WHERE platform = ?",
            (platform,),
        )
        overall = await cursor.fetchone()

    return {
        "distribution": distribution,
        "by_type": by_type,
        "top_profiles": top_profiles,
        "overall": overall or {"total": 0, "avg_score": 0, "max_score": 0, "min_score": 0},
    }
