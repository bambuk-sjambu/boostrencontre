import json
import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
from openai import AsyncOpenAI

from . import bot_engine
from .database import init_db, get_db, dict_factory
from .routes import browser as browser_routes
from .routes import actions as actions_routes
from .routes import profile as profile_routes
from .routes import templates as templates_routes
from .routes import stats as stats_routes
from .routes import campaigns as campaigns_routes
from .routes import conversations as conversations_routes
from .routes import email_summary as email_summary_routes
from .routes.deps import init_platforms

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Security: Allowed platforms whitelist ---
ALLOWED_PLATFORMS = {"tinder", "meetic", "wyylde"}

# --- Security: Max body size for POST requests ---
MAX_BODY_SIZE = 10_000  # 10 KB

# Track running jobs
running_jobs = {}
job_results = {}

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# --- Security: Auto-generate DASHBOARD_TOKEN if not set ---
_dashboard_token = os.getenv("DASHBOARD_TOKEN")
if not _dashboard_token:
    _dashboard_token = secrets.token_urlsafe(32)
    os.environ["DASHBOARD_TOKEN"] = _dashboard_token
    token_path = Path.home() / ".boostrencontre" / ".dashboard_token"
    token_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    token_path.write_text(_dashboard_token)
    token_path.chmod(0o600)
    logger.warning(
        "DASHBOARD_TOKEN not set in env. Generated random token for this session. "
        f"Written to {token_path} — set DASHBOARD_TOKEN env var for persistence."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    await init_db()
    # Load saved user profile into AI messaging module
    try:
        from .messaging import ai_messages
        async with await get_db() as db:
            cursor = await db.execute("SELECT data FROM user_profile WHERE id = 1")
            row = await cursor.fetchone()
            if row:
                saved = json.loads(row[0])
                ai_messages.MY_PROFILE.update(saved)
                logger.info("User profile loaded from database")
    except Exception as e:
        logger.warning(f"Could not load user profile from database: {e}")
    # Start email summary scheduler if enabled
    try:
        from .email_summary import get_email_settings, start_scheduler
        email_settings = await get_email_settings()
        if email_settings.get("email_enabled"):
            start_scheduler()
            logger.info("Email summary scheduler started")
    except Exception as e:
        logger.warning(f"Could not start email scheduler: {e}")
    yield


app = FastAPI(title="BoostRencontre", lifespan=lifespan)

# --- Security: CORS restrictif (localhost seulement) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8888", "http://localhost:8888"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# --- Security: Headers de securite + Auth middleware ---
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Token auth for /api/* routes (skip for localhost requests from the dashboard)
    dashboard_token = os.getenv("DASHBOARD_TOKEN")
    if dashboard_token and request.url.path.startswith("/api/"):
        client_host = request.client.host if request.client else ""
        is_local = client_host in ("127.0.0.1", "::1", "localhost")
        if not is_local:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {dashboard_token}":
                return JSONResponse(status_code=401, content={"error": "unauthorized"})

    # Body size limit for POST/PUT/PATCH
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_SIZE:
                    return JSONResponse(status_code=413, content={"error": "body_too_large"})
            except (ValueError, TypeError):
                return JSONResponse(status_code=400, content={"error": "invalid_content_length"})

    response: Response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )
    return response


# --- Initialize shared platforms + router state ---
init_platforms(ALLOWED_PLATFORMS)
browser_routes.init(running_jobs, job_results)
actions_routes.init(running_jobs, job_results)

# --- Include routers ---
app.include_router(browser_routes.router, prefix="/api")
app.include_router(actions_routes.router, prefix="/api")
app.include_router(profile_routes.router)
app.include_router(templates_routes.router, prefix="/api")
app.include_router(stats_routes.router, prefix="/api")
app.include_router(campaigns_routes.router, prefix="/api")
app.include_router(conversations_routes.router, prefix="/api")
app.include_router(email_summary_routes.router, prefix="/api")

# --- Debug routes: only if DEBUG=true ---
if os.getenv("DEBUG", "false").lower() == "true":
    from .routes import debug as debug_routes
    app.include_router(debug_routes.router, prefix="/api")
    logger.info("Debug routes enabled (DEBUG=true)")


# --- Static files ---
if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# --- HTML page routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT a.*, ps.score as score_value, ps.grade as score_grade "
            "FROM activity_log a "
            "LEFT JOIN profile_scores ps ON a.platform = ps.platform AND a.target_name = ps.target_name "
            "ORDER BY a.created_at DESC LIMIT 50"
        )
        logs = await cursor.fetchall()

        cursor = await db.execute("SELECT * FROM settings WHERE id = 1")
        settings_row = await cursor.fetchone()

    settings = settings_row or {
        "likes_per_session": 50,
        "messages_per_session": 3,
        "delay_min": 3,
        "delay_max": 8,
    }

    return templates.TemplateResponse(request, "index.html", {
        "logs": logs,
        "settings": settings,
    })


@app.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse(request, "home.html")


@app.get("/bmc", response_class=HTMLResponse)
async def bmc_page(request: Request):
    return templates.TemplateResponse(request, "bmc.html")


# --- Settings endpoint ---

@app.post("/api/settings")
async def save_settings(request: Request):
    data = await request.json()
    try:
        likes = int(data["likes_per_session"])
        messages = int(data["messages_per_session"])
        delay_min = int(data["delay_min"])
        delay_max = int(data["delay_max"])
    except (KeyError, ValueError, TypeError):
        return JSONResponse(status_code=400, content={"error": "invalid_settings"})
    if not (1 <= likes <= 500 and 1 <= messages <= 50 and 0 <= delay_min <= 60 and 1 <= delay_max <= 120):
        return JSONResponse(status_code=400, content={"error": "settings_out_of_range"})
    async with await get_db() as db:
        await db.execute(
            """UPDATE settings SET
                likes_per_session = ?,
                messages_per_session = ?,
                delay_min = ?,
                delay_max = ?
            WHERE id = 1""",
            (likes, messages, delay_min, delay_max)
        )
        await db.commit()
    return {"status": "saved"}
