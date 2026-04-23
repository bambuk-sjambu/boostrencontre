"""Tests for the Tinder platform package, stealth layer, scoring, and action dispatch."""

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import aiosqlite
import pytest

import src.database as db_mod


# ---------------------------------------------------------------------------
# Package + class structure
# ---------------------------------------------------------------------------

def test_tinder_package_imports():
    from src.platforms.tinder import TinderPlatform
    assert TinderPlatform is not None


def test_tinder_platform_is_package():
    import src.platforms.tinder as pkg
    assert hasattr(pkg, "__path__"), "src.platforms.tinder should be a package"


def test_tinder_submodules_exist():
    # Every named module should import
    from src.platforms.tinder import (  # noqa: F401
        platform, profile, swipe, messaging, stealth, selectors,
    )


def test_tinder_inherits_mixins_in_mro():
    from src.platforms.tinder import TinderPlatform
    from src.platforms.tinder.profile import TinderProfileMixin
    from src.platforms.tinder.swipe import TinderSwipeMixin
    from src.platforms.tinder.messaging import TinderMessagingMixin
    mro_names = [c.__name__ for c in TinderPlatform.__mro__]
    assert "TinderProfileMixin" in mro_names
    assert "TinderSwipeMixin" in mro_names
    assert "TinderMessagingMixin" in mro_names


def test_tinder_core_methods_present():
    from src.platforms.tinder import TinderPlatform
    for m in [
        "login_url", "open", "is_logged_in",
        "like_profiles", "send_message", "get_matches", "get_profile_info",
        "navigate_to_profile", "send_message_from_profile",
        "swipe_right", "swipe_left", "swipe_super",
        "_type_and_send_in_current_chat", "_dwell_on_card", "_mouse_drag_swipe",
    ]:
        assert hasattr(TinderPlatform, m), f"missing method {m}"


def test_tinder_urls():
    from src.platforms.tinder import TinderPlatform
    assert TinderPlatform.LOGIN_URL == "https://tinder.com"
    assert TinderPlatform.RECS_URL == "https://tinder.com/app/recs"
    assert TinderPlatform.MESSAGES_URL == "https://tinder.com/app/messages"


# ---------------------------------------------------------------------------
# Selectors — stable anchors, not empty
# ---------------------------------------------------------------------------

def test_selectors_non_empty():
    from src.platforms.tinder import selectors as sel
    assert sel.LIKE_BUTTON
    assert sel.NOPE_BUTTON
    assert sel.SUPER_LIKE_BUTTON
    assert sel.MATCH_LINK
    assert sel.KEY_LIKE == "ArrowRight"
    assert sel.KEY_NOPE == "ArrowLeft"


def test_selectors_no_placeholder_classes():
    """Selectors should prefer aria-label, href patterns, data-testid over raw classes."""
    from src.platforms.tinder import selectors as sel
    assert "aria-label" in sel.LIKE_BUTTON or "data-testid" in sel.LIKE_BUTTON
    assert "/app/messages/" in sel.MATCH_LINK


def test_selectors_fallback_chains_non_empty():
    from src.platforms.tinder import selectors as sel
    for chain in [
        sel.PROFILE_NAME_FALLBACKS, sel.PROFILE_AGE_FALLBACKS,
        sel.PROFILE_BIO_FALLBACKS, sel.PROFILE_PASSIONS_FALLBACKS,
        sel.PROFILE_DISTANCE_FALLBACKS, sel.MESSAGE_INPUT_FALLBACKS,
        sel.SEND_BUTTON_FALLBACKS, sel.POPUP_DISMISS_FALLBACKS,
    ]:
        assert isinstance(chain, list) and len(chain) > 0


# ---------------------------------------------------------------------------
# Stealth layer
# ---------------------------------------------------------------------------

def test_stealth_version_set():
    from src.platforms.tinder.stealth import STEALTH_VERSION
    assert STEALTH_VERSION
    assert "." in STEALTH_VERSION


def test_stealth_launch_kwargs_france():
    """T1-A (pivot 2026-04-23): France fingerprint via ProtonVPN FR."""
    from src.platforms.tinder.stealth import get_launch_kwargs
    kw = get_launch_kwargs()
    assert kw["locale"] == "fr-FR"
    assert kw["timezone_id"] == "Europe/Paris"
    assert "viewport" in kw


def test_stealth_no_disable_blink_flag():
    """Per security review: this flag is itself fingerprinted; patchright replaces it."""
    from src.platforms.tinder.stealth import get_launch_kwargs
    args = " ".join(get_launch_kwargs()["args"])
    assert "AutomationControlled" not in args


def test_stealth_init_script_non_empty():
    from src.platforms.tinder.stealth import get_init_script
    s = get_init_script()
    assert len(s) > 4000, "init script should cover 2026 fingerprint surfaces"


def test_stealth_init_script_covers_critical_surfaces():
    from src.platforms.tinder.stealth import get_init_script
    s = get_init_script()
    for surface in [
        "webdriver", "plugins", "languages", "hardwareConcurrency",
        "deviceMemory", "colorDepth", "WebGL", "Canvas",
        "AudioContext", "mediaDevices", "speechSynthesis", "permissions",
        "contentWindow",
    ]:
        assert surface.lower() in s.lower(), f"stealth script missing {surface}"


def test_stealth_toString_spoof_present():
    """Critical: hide function.toString() leakage."""
    from src.platforms.tinder.stealth import get_init_script
    s = get_init_script()
    assert "Function.prototype.toString" in s
    assert "[native code]" in s


# ---------------------------------------------------------------------------
# Rate limiter — Tinder sliding window + gender-aware caps
# ---------------------------------------------------------------------------

@pytest.fixture
async def rl_db(tmp_path):
    """Temp DB with both daily_counters and activity_log tables."""
    db_path = str(tmp_path / "test_rl_tinder.db")
    original = db_mod.DB_PATH
    db_mod.DB_PATH = db_path
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE daily_counters (
                date TEXT, platform TEXT, action TEXT, count INTEGER DEFAULT 0,
                PRIMARY KEY (date, platform, action)
            )
        """)
        await db.execute("""
            CREATE TABLE activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT, action TEXT, target_name TEXT,
                message_sent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    yield
    db_mod.DB_PATH = original


def test_sliding_window_limits_registered():
    from src.rate_limiter import SLIDING_WINDOW_LIMITS
    assert "tinder" in SLIDING_WINDOW_LIMITS
    assert "likes" in SLIDING_WINDOW_LIMITS["tinder"]
    cap, window = SLIDING_WINDOW_LIMITS["tinder"]["likes"]
    assert 20 <= cap <= 80, "Tinder swipe cap should be conservative"
    assert window == 12


def test_gender_aware_cap_male_lower():
    """T2-A conservative: male cap must be lower than female."""
    from src.rate_limiter import SLIDING_WINDOW_LIMITS, _TINDER_SWIPE_CAP, _MY_GENDER
    if _MY_GENDER == "male":
        assert _TINDER_SWIPE_CAP <= 50
    else:
        assert _TINDER_SWIPE_CAP >= 60


@pytest.mark.asyncio
async def test_sliding_count_empty(rl_db):
    from src.rate_limiter import get_sliding_count
    count = await get_sliding_count("tinder", "likes")
    assert count == 0


@pytest.mark.asyncio
async def test_sliding_count_includes_recent(rl_db):
    from src.rate_limiter import get_sliding_count
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        for _ in range(3):
            await db.execute(
                "INSERT INTO activity_log (platform, action, target_name) VALUES (?, ?, ?)",
                ("tinder", "likes", "Test"),
            )
        await db.commit()
    assert await get_sliding_count("tinder", "likes") == 3


@pytest.mark.asyncio
async def test_sliding_count_excludes_old(rl_db):
    """Rows older than the window should NOT count."""
    from src.rate_limiter import get_sliding_count
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, created_at) "
            "VALUES (?, ?, ?, datetime('now', '-20 hours'))",
            ("tinder", "likes", "Old"),
        )
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name) VALUES (?, ?, ?)",
            ("tinder", "likes", "Fresh"),
        )
        await db.commit()
    # Window is 12h; only the recent one counts
    assert await get_sliding_count("tinder", "likes") == 1


@pytest.mark.asyncio
async def test_check_daily_limit_dispatches_for_tinder(rl_db):
    from src.rate_limiter import check_daily_limit
    allowed, current, limit = await check_daily_limit("tinder", "likes")
    assert allowed is True
    assert current == 0
    assert 20 <= limit <= 80


@pytest.mark.asyncio
async def test_check_daily_limit_calendar_for_wyylde(rl_db):
    from src.rate_limiter import check_daily_limit
    allowed, current, limit = await check_daily_limit("wyylde", "likes")
    assert allowed is True
    assert current == 0
    assert limit == 100  # Wyylde uses DEFAULT_DAILY_LIMITS


@pytest.mark.asyncio
async def test_daily_stats_has_window_field(rl_db):
    from src.rate_limiter import get_daily_stats
    stats = await get_daily_stats("tinder")
    assert "likes" in stats
    assert "sliding" in stats["likes"]["window"]
    stats_w = await get_daily_stats("wyylde")
    assert stats_w["likes"]["window"] == "calendar-day"


# ---------------------------------------------------------------------------
# Tinder scoring adapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tinder_scoring_high():
    from src.scoring import score_profile
    my = {"interests": ["travel", "hiking"], "age_range": (25, 35)}
    target = {
        "name": "Alex", "age": "28", "bio": "Love travel, hiking, coffee" * 3,
        "distance": "3 km away",
        "passions": ["travel", "hiking", "coffee"], "photo_count": 5,
    }
    r = await score_profile(target, my_profile=my, platform="tinder")
    assert r["total"] >= 75
    assert r["grade"] in ("A", "B")
    assert r["recommendation"] == "message"


@pytest.mark.asyncio
async def test_tinder_scoring_empty_profile_low():
    from src.scoring import score_profile
    r = await score_profile({}, my_profile={}, platform="tinder")
    assert r["total"] <= 30
    assert r["recommendation"] == "skip"


@pytest.mark.asyncio
async def test_tinder_scoring_distance_parsing():
    from src.scoring import score_profile
    close = {"distance": "2 km away", "photo_count": 3, "bio": "Hi"}
    far = {"distance": "50 km away", "photo_count": 3, "bio": "Hi"}
    r_close = await score_profile(close, my_profile={}, platform="tinder")
    r_far = await score_profile(far, my_profile={}, platform="tinder")
    assert r_close["total"] > r_far["total"]


@pytest.mark.asyncio
async def test_tinder_scoring_photos_weighted():
    from src.scoring import score_profile
    few = {"photo_count": 1}
    many = {"photo_count": 5}
    r_few = await score_profile(few, my_profile={}, platform="tinder")
    r_many = await score_profile(many, my_profile={}, platform="tinder")
    assert r_many["total"] - r_few["total"] >= 15


@pytest.mark.asyncio
async def test_tinder_scoring_miles_converted():
    from src.scoring import score_profile
    p = {"distance": "3 miles away", "photo_count": 3}
    r = await score_profile(p, my_profile={}, platform="tinder")
    # 3 miles ≈ 4.8 km → tight bracket → 20 points
    assert r["details"]["distance"]["points"] == 20


@pytest.mark.asyncio
async def test_tinder_scoring_style_aventurier_from_travel():
    from src.scoring import score_profile
    p = {
        "bio": "Digital nomad, love to travel the world", "passions": ["travel"],
        "photo_count": 4, "distance": "5 km away",
    }
    r = await score_profile(p, my_profile={}, platform="tinder")
    assert r["suggested_style"] == "aventurier"


@pytest.mark.asyncio
async def test_wyylde_scoring_unchanged_by_tinder_platform_arg():
    """Wyylde scoring path must still work when platform != tinder."""
    from src.scoring import score_profile
    wyylde_profile = {"bio": "BDSM passionné", "type": "homme", "age": "35"}
    r = await score_profile(wyylde_profile, my_profile={"type": "couple"}, platform="wyylde")
    assert "total" in r
    assert "details" in r


# ---------------------------------------------------------------------------
# Platform methods — mocked page
# ---------------------------------------------------------------------------

def _make_tinder_with_mock_page():
    from src.platforms.tinder import TinderPlatform
    ctx = MagicMock()
    p = TinderPlatform(ctx)
    p.page = MagicMock()
    p.page.url = "https://tinder.com/app/recs"
    p.page.goto = AsyncMock()
    p.page.wait_for_selector = AsyncMock()
    p.page.keyboard = MagicMock()
    p.page.keyboard.press = AsyncMock()
    p.page.mouse = MagicMock()
    p.page.mouse.down = AsyncMock()
    p.page.mouse.up = AsyncMock()
    p.page.mouse.move = AsyncMock()
    p.page.query_selector = AsyncMock(return_value=None)
    p.page.query_selector_all = AsyncMock(return_value=[])
    p.page.evaluate = AsyncMock(return_value="")
    p.page.viewport_size = {"width": 1440, "height": 900}
    return p


@pytest.mark.asyncio
async def test_is_logged_in_true_when_app_in_url():
    p = _make_tinder_with_mock_page()
    p.page.url = "https://tinder.com/app/recs"
    assert await p.is_logged_in() is True


@pytest.mark.asyncio
async def test_is_logged_in_false_on_root():
    p = _make_tinder_with_mock_page()
    p.page.url = "https://tinder.com/"
    p.page.wait_for_selector = AsyncMock(side_effect=Exception("timeout"))
    assert await p.is_logged_in() is False


@pytest.mark.asyncio
async def test_swipe_right_falls_back_to_keyboard():
    """No button found -> keyboard fallback used, still returns True."""
    p = _make_tinder_with_mock_page()
    # Force mouse-drag off by patching random
    with patch("src.platforms.tinder.swipe.random.random", return_value=0.99):
        ok = await p.swipe_right()
    assert ok is True
    p.page.keyboard.press.assert_called()


@pytest.mark.asyncio
async def test_swipe_left_keyboard_fallback_left_arrow():
    p = _make_tinder_with_mock_page()
    with patch("src.platforms.tinder.swipe.random.random", return_value=0.99):
        await p.swipe_left()
    calls = [c.args for c in p.page.keyboard.press.call_args_list]
    assert any("ArrowLeft" in str(c) for c in calls)


@pytest.mark.asyncio
async def test_swipe_right_uses_mouse_drag_when_lucky():
    p = _make_tinder_with_mock_page()
    with patch("src.platforms.tinder.swipe.random.random", return_value=0.01):
        ok = await p.swipe_right()
    assert ok is True
    p.page.mouse.down.assert_called()
    p.page.mouse.up.assert_called()


@pytest.mark.asyncio
async def test_dwell_duration_positive():
    p = _make_tinder_with_mock_page()
    import time
    start = time.monotonic()
    await p._dwell_on_card()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.5  # shortest path lower bound


@pytest.mark.asyncio
async def test_navigate_to_profile_stores_match_id():
    p = _make_tinder_with_mock_page()
    await p.navigate_to_profile("abc123")
    assert p._current_match_id == "abc123"


@pytest.mark.asyncio
async def test_send_message_from_profile_without_navigate_fails():
    p = _make_tinder_with_mock_page()
    assert await p.send_message_from_profile("hi") is False


@pytest.mark.asyncio
async def test_get_matches_parses_hrefs():
    p = _make_tinder_with_mock_page()

    el1 = MagicMock()
    el1.get_attribute = AsyncMock(return_value="/app/messages/match1")
    name_el = MagicMock()
    name_el.inner_text = AsyncMock(return_value="Alice\n25")
    el1.query_selector = AsyncMock(return_value=name_el)

    p.page.query_selector_all = AsyncMock(return_value=[el1])
    matches = await p.get_matches()
    assert matches
    assert matches[0]["id"] == "match1"
    assert matches[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_rate_limit_detection_via_body_text():
    p = _make_tinder_with_mock_page()
    p.page.evaluate = AsyncMock(return_value="Hello! You've seen everyone here.")
    assert await p._is_rate_limited() is True


@pytest.mark.asyncio
async def test_rate_limit_detection_false_on_normal():
    p = _make_tinder_with_mock_page()
    p.page.evaluate = AsyncMock(return_value="Normal Tinder page content")
    assert await p._is_rate_limited() is False


# ---------------------------------------------------------------------------
# Action dispatch guards (ENG review: Wyylde-only actions must reject Tinder)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_message_discussions_rejects_tinder():
    from src.actions.messages import message_discussions
    result = await message_discussions("tinder")
    assert result == []


@pytest.mark.asyncio
async def test_message_from_search_rejects_tinder():
    from src.actions.messages import message_from_search
    result = await message_from_search("tinder")
    assert result == []


@pytest.mark.asyncio
async def test_reply_to_sidebar_rejects_tinder():
    from src.actions.replies_inbox import reply_to_sidebar
    result = await reply_to_sidebar("tinder")
    assert result == []


@pytest.mark.asyncio
async def test_reply_to_inbox_dispatches_to_tinder_flow(monkeypatch):
    """Tinder path must route to reply_to_tinder_matches (Wyylde-coupled flow avoided)."""
    from src.actions import replies_inbox

    called = {"tinder": False}

    async def fake_tinder_replies(platform_name: str, style="auto"):
        called["tinder"] = platform_name == "tinder"
        return []

    monkeypatch.setattr(
        "src.actions.replies_tinder.reply_to_tinder_matches", fake_tinder_replies
    )
    await replies_inbox.reply_to_inbox("tinder")
    assert called["tinder"] is True


@pytest.mark.asyncio
async def test_check_and_reply_unread_dispatches_to_tinder(monkeypatch):
    from src.actions import replies_unread

    called = {"tinder": False}

    async def fake_tinder_replies(platform_name: str, style="auto"):
        called["tinder"] = True
        return []

    monkeypatch.setattr(
        "src.actions.replies_tinder.reply_to_tinder_matches", fake_tinder_replies
    )
    await replies_unread.check_and_reply_unread("tinder")
    assert called["tinder"] is True


@pytest.mark.asyncio
async def test_reply_to_unread_sidebar_dispatches_to_tinder(monkeypatch):
    from src.actions import replies_unread

    called = {"tinder": False}

    async def fake_tinder_replies(platform_name: str, style="auto"):
        called["tinder"] = True
        return []

    monkeypatch.setattr(
        "src.actions.replies_tinder.reply_to_tinder_matches", fake_tinder_replies
    )
    await replies_unread.reply_to_unread_sidebar("tinder")
    assert called["tinder"] is True


# ---------------------------------------------------------------------------
# Stealth audit endpoint (registered + validates platform)
# ---------------------------------------------------------------------------

def test_stealth_audit_endpoint_registered():
    from src.app import app
    paths = [getattr(r, "path", "") for r in app.routes]
    assert any("stealth-audit" in p for p in paths)


def test_platform_detail_route_registered():
    """Per-platform detail page must be routable for tinder/wyylde/meetic."""
    from src.app import app
    paths = [getattr(r, "path", "") for r in app.routes]
    assert "/platform/{name}" in paths


@pytest.mark.asyncio
async def test_platform_detail_renders_tinder(tmp_path, monkeypatch):
    """Platform detail page must render without errors for tinder."""
    from fastapi.testclient import TestClient
    from src.app import app
    import src.database as db_mod

    # Use temp DB so route has valid tables
    db_path = str(tmp_path / "test_platform_detail.db")
    original = db_mod.DB_PATH
    db_mod.DB_PATH = db_path

    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE activity_log (id INTEGER PRIMARY KEY, platform TEXT, action TEXT, target_name TEXT, message_sent TEXT, style TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        await db.execute("CREATE TABLE profile_scores (platform TEXT, target_name TEXT, score INTEGER, grade TEXT, PRIMARY KEY (platform, target_name))")
        await db.execute("CREATE TABLE daily_counters (date TEXT, platform TEXT, action TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (date, platform, action))")
        await db.commit()

    try:
        with TestClient(app) as client:
            resp = client.get("/platform/tinder")
            assert resp.status_code == 200
            assert "Tinder" in resp.text
            assert "Version stealth" in resp.text
            assert "Audit fingerprint" in resp.text
    finally:
        db_mod.DB_PATH = original


@pytest.mark.asyncio
async def test_platform_detail_404_on_unknown(tmp_path):
    """Unknown platform name should 404."""
    from fastapi.testclient import TestClient
    from src.app import app
    import src.database as db_mod

    db_path = str(tmp_path / "test_pd_404.db")
    original = db_mod.DB_PATH
    db_mod.DB_PATH = db_path

    try:
        with TestClient(app) as client:
            resp = client.get("/platform/bumble")
            assert resp.status_code == 404
    finally:
        db_mod.DB_PATH = original


# ---------------------------------------------------------------------------
# Session manager — Tinder uses patchright, others unchanged
# ---------------------------------------------------------------------------

def test_session_manager_imports_patchright():
    import src.session_manager as sm
    assert sm.async_patchright is not None
    assert sm.async_playwright is not None


def test_session_manager_has_tinder_launcher():
    import src.session_manager as sm
    assert callable(sm._launch_tinder_context)
    assert callable(sm._launch_legacy_context)


# ---------------------------------------------------------------------------
# BasePlatform signature fix (ENG [high] introspection hack removed)
# ---------------------------------------------------------------------------

def test_base_platform_like_profiles_accepts_profile_filter():
    from src.platforms.base import BasePlatform
    import inspect
    sig = inspect.signature(BasePlatform.like_profiles)
    assert "profile_filter" in sig.parameters


def test_meetic_like_profiles_accepts_profile_filter():
    from src.platforms.meetic import MeeticPlatform
    import inspect
    sig = inspect.signature(MeeticPlatform.like_profiles)
    assert "profile_filter" in sig.parameters


def test_tinder_like_profiles_accepts_profile_filter():
    from src.platforms.tinder import TinderPlatform
    import inspect
    sig = inspect.signature(TinderPlatform.like_profiles)
    assert "profile_filter" in sig.parameters
