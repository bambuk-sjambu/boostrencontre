import asyncio
import json
import logging
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright
from .platforms.tinder import TinderPlatform
from .platforms.meetic import MeeticPlatform
from .platforms.wyylde import WyyldePlatform
from .database import get_db

logger = logging.getLogger(__name__)

PLATFORMS = {
    "tinder": TinderPlatform,
    "meetic": MeeticPlatform,
    "wyylde": WyyldePlatform,
}

PROFILE_DIR = Path.home() / ".boostrencontre" / "browser_profiles"

browser_sessions = {}


async def launch_browser(platform_name: str) -> dict:
    if platform_name in browser_sessions:
        return {"status": "already_open", "platform": platform_name}

    profile_path = PROFILE_DIR / platform_name
    profile_path.mkdir(parents=True, exist_ok=True, mode=0o700)

    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        headless=False,
        viewport={"width": 1920, "height": 1080},
        locale="fr-FR",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-position=0,1400",
            "--window-size=1280,800",
        ],
        ignore_default_args=["--enable-automation"],
    )
    context = browser

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['fr-FR', 'fr', 'en-US', 'en'],
        });
    """)

    platform_cls = PLATFORMS.get(platform_name)
    if not platform_cls:
        await context.close()
        await pw.stop()
        return {"status": "error", "message": f"Unknown platform: {platform_name}"}

    platform = platform_cls(context)
    await platform.open()

    try:
        await asyncio.sleep(2)
        result = subprocess.run(
            ["wmctrl", "-l"], timeout=5, capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if "Chrome for Testing" in line:
                wid = line.split()[0]
                subprocess.run(["xdotool", "windowminimize", wid], timeout=3, capture_output=True)
                logger.info(f"Minimized window {wid}")
    except Exception as e:
        logger.debug(f"Could not minimize window: {e}")

    browser_sessions[platform_name] = {
        "pw": pw,
        "context": context,
        "platform": platform,
    }

    return {"status": "opened", "platform": platform_name}


async def check_login(platform_name: str) -> bool:
    session = browser_sessions.get(platform_name)
    if not session:
        return False
    return await session["platform"].is_logged_in()


async def save_session(platform_name: str):
    session = browser_sessions.get(platform_name)
    if not session:
        return
    cookies = await session["context"].cookies()
    async with await get_db() as db:
        await db.execute(
            "UPDATE accounts SET session_data = ?, status = 'connected' WHERE platform = ?",
            (json.dumps(cookies), platform_name)
        )
        await db.commit()


async def close_browser(platform_name: str):
    from .actions.auto_reply import stop_auto_reply
    stop_auto_reply(platform_name)
    session = browser_sessions.pop(platform_name, None)
    if session:
        try:
            await session["context"].close()
            await session["pw"].stop()
        except Exception:
            pass
    async with await get_db() as db:
        await db.execute(
            "UPDATE accounts SET status = 'disconnected' WHERE platform = ?",
            (platform_name,)
        )
        await db.commit()
