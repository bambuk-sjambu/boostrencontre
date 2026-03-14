"""Bot engine -- thin re-export module for backward compatibility.

All logic has been refactored into:
  - src/session_manager.py (browser sessions, launch, close)
  - src/browser_utils.py (TipTap editor, send button, navigation)
  - src/conversation_utils.py (rejection, UI filtering, delay)
  - src/actions/likes.py
  - src/actions/messages.py
  - src/actions/replies.py
  - src/actions/auto_reply.py
"""

from .session_manager import (
    PLATFORMS,
    PROFILE_DIR,
    browser_sessions,
    launch_browser,
    check_login,
    save_session,
    close_browser,
)
from .browser_utils import _safe_goto
from .conversation_utils import _human_delay
from .actions.likes import run_likes
from .actions.messages import run_messages, message_discussions, message_from_search
from .actions.replies import (
    reply_to_inbox,
    reply_to_sidebar,
    check_and_reply_unread,
    reply_to_unread_sidebar,
    _close_sidebar_discussion,
)
from .actions.auto_reply import (
    _monitoring_tasks,
    _auto_reply_loop,
    start_auto_reply,
    stop_auto_reply,
)

__all__ = [
    "PLATFORMS",
    "PROFILE_DIR",
    "browser_sessions",
    "launch_browser",
    "check_login",
    "save_session",
    "close_browser",
    "run_likes",
    "run_messages",
    "message_discussions",
    "message_from_search",
    "reply_to_inbox",
    "reply_to_sidebar",
    "check_and_reply_unread",
    "reply_to_unread_sidebar",
    "start_auto_reply",
    "stop_auto_reply",
    "_safe_goto",
    "_human_delay",
    "_monitoring_tasks",
    "_auto_reply_loop",
    "_close_sidebar_discussion",
]
