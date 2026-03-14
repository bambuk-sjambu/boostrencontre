from abc import ABC, abstractmethod


class BasePlatform(ABC):
    """Base class for dating platform automation."""

    def __init__(self, browser_context):
        self.context = browser_context
        self.page = None

    @abstractmethod
    async def open(self):
        """Open the platform in a new browser page."""
        pass

    @abstractmethod
    async def login_url(self) -> str:
        """Return the login URL for the platform."""
        pass

    @abstractmethod
    async def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        pass

    @abstractmethod
    async def like_profiles(self, count: int, delay_range: tuple) -> list:
        """Like profiles and return list of liked profile info."""
        pass

    @abstractmethod
    async def send_message(self, match_id: str, message: str) -> bool:
        """Send a message to a match."""
        pass

    @abstractmethod
    async def get_matches(self) -> list:
        """Get list of current matches."""
        pass

    @abstractmethod
    async def get_profile_info(self, profile_element) -> dict:
        """Extract profile information from a profile element."""
        pass

    # ─── Optional methods (override in subclasses as needed) ───

    async def navigate_to_profile(self, match_id: str) -> dict:
        """Navigate to a member's profile page and return profile info.
        Returns profile dict or None on failure."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement navigate_to_profile")

    async def read_full_profile(self) -> dict:
        """Read the full profile of the currently displayed member.
        Expands bio, reads preferences/desires, etc."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement read_full_profile")

    async def get_inbox_conversations(self) -> list:
        """Get conversations from the platform's inbox/mailbox.
        Returns list of conversation dicts with at least 'text' and 'href' keys."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement get_inbox_conversations")

    async def open_chat_and_read(self, conv) -> str:
        """Open a conversation and read its messages.
        Returns conversation data dict with 'fullText', 'hasMessages', etc."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement open_chat_and_read")

    async def reply_in_chat(self, message: str) -> bool:
        """Reply in the currently open conversation.
        Returns True if message was sent successfully."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement reply_in_chat")
