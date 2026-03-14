import pytest
from unittest.mock import MagicMock, AsyncMock
from abc import ABC
from src.platforms.tinder import TinderPlatform
from src.platforms.meetic import MeeticPlatform
from src.platforms.wyylde import WyyldePlatform
from src.platforms.base import BasePlatform


# --- Inheritance ---

def test_tinder_inherits_base():
    assert issubclass(TinderPlatform, BasePlatform)


def test_meetic_inherits_base():
    assert issubclass(MeeticPlatform, BasePlatform)


def test_wyylde_inherits_base():
    assert issubclass(WyyldePlatform, BasePlatform)


def test_base_is_abstract():
    assert issubclass(BasePlatform, ABC)


# --- LOGIN_URL ---

def test_tinder_login_url():
    assert TinderPlatform.LOGIN_URL == "https://tinder.com"


def test_meetic_login_url():
    assert MeeticPlatform.LOGIN_URL == "https://www.meetic.fr"


def test_wyylde_login_url():
    assert WyyldePlatform.LOGIN_URL == "https://app.wyylde.com/fr-fr"


# --- Required methods on all platforms ---

def test_all_platforms_have_required_methods():
    for cls in [TinderPlatform, MeeticPlatform, WyyldePlatform]:
        for method in ["login_url", "is_logged_in", "like_profiles", "send_message", "get_matches", "get_profile_info"]:
            assert hasattr(cls, method), f"{cls.__name__} missing {method}"


def test_all_platforms_have_open_method():
    for cls in [TinderPlatform, MeeticPlatform, WyyldePlatform]:
        assert hasattr(cls, "open"), f"{cls.__name__} missing open()"


# --- Wyylde-specific methods ---

def test_wyylde_has_mailbox_methods():
    """Wyylde has mailbox inbox and chat sidebar reply methods."""
    for method in ["get_inbox_conversations", "open_chat_and_read", "reply_in_chat",
                    "get_sidebar_conversations", "open_sidebar_chat", "reply_in_sidebar_chat"]:
        assert hasattr(WyyldePlatform, method), f"WyyldePlatform missing {method}"


def test_wyylde_has_mailbox_url():
    assert hasattr(WyyldePlatform, "MAILBOX_URL")
    assert "mailbox" in WyyldePlatform.MAILBOX_URL


def test_wyylde_has_search_methods():
    """Wyylde should have search-related methods."""
    for method in ["apply_search_filters", "get_search_results", "click_search_result"]:
        assert hasattr(WyyldePlatform, method), f"WyyldePlatform missing {method}"


def test_wyylde_has_profile_navigation():
    """Wyylde should have navigate_to_profile and send_message_from_profile."""
    for method in ["navigate_to_profile", "send_message_from_profile", "go_to_next_profile", "read_full_profile"]:
        assert hasattr(WyyldePlatform, method), f"WyyldePlatform missing {method}"


def test_wyylde_has_follow_crush_methods():
    """Wyylde should have follow and crush button methods."""
    for method in ["_click_follow", "_click_crush"]:
        assert hasattr(WyyldePlatform, method), f"WyyldePlatform missing {method}"


# --- Constructor ---

def test_base_constructor_stores_context():
    mock_ctx = MagicMock()
    platform = TinderPlatform(mock_ctx)
    assert platform.context is mock_ctx
    assert platform.page is None


def test_all_platforms_accept_context():
    mock_ctx = MagicMock()
    for cls in [TinderPlatform, MeeticPlatform, WyyldePlatform]:
        instance = cls(mock_ctx)
        assert instance.context is mock_ctx


# --- Abstract methods cannot be instantiated directly ---

def test_base_platform_cannot_be_instantiated():
    """BasePlatform is abstract and should not be instantiable."""
    with pytest.raises(TypeError):
        BasePlatform(MagicMock())


# --- Wyylde profile_filter parameter ---

def test_wyylde_like_profiles_accepts_profile_filter():
    """Wyylde like_profiles should accept a profile_filter parameter."""
    import inspect
    sig = inspect.signature(WyyldePlatform.like_profiles)
    params = list(sig.parameters.keys())
    assert "profile_filter" in params, "WyyldePlatform.like_profiles should accept profile_filter"


# --- Method signatures ---

def test_login_url_is_async():
    import asyncio
    for cls in [TinderPlatform, MeeticPlatform, WyyldePlatform]:
        assert asyncio.iscoroutinefunction(cls.login_url), f"{cls.__name__}.login_url should be async"


def test_is_logged_in_is_async():
    import asyncio
    for cls in [TinderPlatform, MeeticPlatform, WyyldePlatform]:
        assert asyncio.iscoroutinefunction(cls.is_logged_in), f"{cls.__name__}.is_logged_in should be async"


def test_like_profiles_is_async():
    import asyncio
    for cls in [TinderPlatform, MeeticPlatform, WyyldePlatform]:
        assert asyncio.iscoroutinefunction(cls.like_profiles), f"{cls.__name__}.like_profiles should be async"
