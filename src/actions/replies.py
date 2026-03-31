"""Reply actions — re-exports for backward compatibility."""
from .replies_helpers import (
    _log_rejection, _is_rejected, _replied_recently,
    _get_last_sent_message, _log_reply, _send_reply_in_editor,
    _close_sidebar_discussion,
)
from .replies_inbox import reply_to_inbox, reply_to_sidebar
from .replies_unread import check_and_reply_unread, reply_to_unread_sidebar

__all__ = [
    "reply_to_inbox", "reply_to_sidebar",
    "check_and_reply_unread", "reply_to_unread_sidebar",
    "_close_sidebar_discussion", "_send_reply_in_editor",
    "_log_rejection", "_is_rejected", "_replied_recently",
    "_get_last_sent_message", "_log_reply",
]
