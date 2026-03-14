import asyncio
import logging
from ..session_manager import browser_sessions
from .replies import reply_to_unread_sidebar

logger = logging.getLogger(__name__)

_monitoring_tasks = {}


async def _auto_reply_loop(platform_name: str, style: str = "auto", interval: int = 60):
    logger.info(f"Auto-reply started for {platform_name} (every {interval}s)")
    while platform_name in browser_sessions:
        try:
            replied = await reply_to_unread_sidebar(platform_name, style=style)
            if replied:
                logger.info(f"Auto-reply: {len(replied)} replies sent")
        except Exception as e:
            logger.error(f"Auto-reply error: {e}")
        await asyncio.sleep(interval)
    logger.info(f"Auto-reply stopped for {platform_name}")


def start_auto_reply(platform_name: str, style: str = "auto", interval: int = 60):
    if platform_name in _monitoring_tasks:
        logger.info(f"Auto-reply already running for {platform_name}")
        return
    task = asyncio.create_task(_auto_reply_loop(platform_name, style, interval))
    _monitoring_tasks[platform_name] = task
    logger.info(f"Auto-reply scheduled for {platform_name}")


def stop_auto_reply(platform_name: str):
    task = _monitoring_tasks.pop(platform_name, None)
    if task:
        task.cancel()
        logger.info(f"Auto-reply stopped for {platform_name}")
