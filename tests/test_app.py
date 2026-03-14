import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from src.app import app
from src.database import init_db
from src import bot_engine
import os


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Use a temp DB for each test. Disable auth middleware for tests."""
    # Ensure no auth token is set during tests (dev mode)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    import src.database as db_mod
    db_mod.DB_PATH = str(tmp_path / "test.db")
    await init_db()
    yield
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Homepage ---

@pytest.mark.asyncio
async def test_homepage_returns_200(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "BoostRencontre" in r.text


@pytest.mark.asyncio
async def test_homepage_has_all_platforms(client):
    r = await client.get("/")
    assert "Tinder" in r.text
    assert "Meetic" in r.text
    assert "Wyylde" in r.text


@pytest.mark.asyncio
async def test_homepage_has_instructions(client):
    r = await client.get("/")
    assert "Clique sur une plateforme" in r.text


@pytest.mark.asyncio
async def test_homepage_has_style_selector(client):
    r = await client.get("/")
    assert "message-style" in r.text
    assert "romantique" in r.text
    assert "humoristique" in r.text


@pytest.mark.asyncio
async def test_homepage_has_reply_button(client):
    r = await client.get("/")
    assert "Repondre Non-Lus Sidebar" in r.text


@pytest.mark.asyncio
async def test_homepage_has_profile_link(client):
    r = await client.get("/")
    assert "/profile" in r.text
    assert "Mon Profil IA" in r.text


# --- Profile Page ---

@pytest.mark.asyncio
async def test_profile_page_returns_200(client):
    r = await client.get("/profile")
    assert r.status_code == 200
    assert "Mon Profil IA" in r.text


# --- API: Login ---

@pytest.mark.asyncio
async def test_check_login_returns_false_when_no_session(client):
    for platform in ["tinder", "meetic", "wyylde"]:
        r = await client.get(f"/api/check-login/{platform}")
        assert r.status_code == 200
        assert r.json() == {"logged_in": False}


# --- API: Likes ---

@pytest.mark.asyncio
async def test_likes_returns_error_when_not_connected(client):
    for platform in ["tinder", "meetic", "wyylde"]:
        r = await client.post(f"/api/likes/{platform}")
        assert r.status_code == 200
        data = r.json()
        assert data["error"] == "not_connected"
        assert platform in data["message"]


# --- API: Messages ---

@pytest.mark.asyncio
async def test_messages_returns_error_when_not_connected(client):
    for platform in ["tinder", "meetic", "wyylde"]:
        r = await client.post(f"/api/messages/{platform}")
        assert r.status_code == 200
        data = r.json()
        assert data["error"] == "not_connected"
        assert platform in data["message"]


# --- API: Replies ---

@pytest.mark.asyncio
async def test_replies_returns_error_when_not_connected(client):
    r = await client.post("/api/replies/wyylde")
    assert r.status_code == 200
    data = r.json()
    assert data["error"] == "not_connected"


# --- API: Settings ---

@pytest.mark.asyncio
async def test_save_settings(client):
    r = await client.post("/api/settings", json={
        "likes_per_session": 25,
        "messages_per_session": 5,
        "delay_min": 2,
        "delay_max": 10,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "saved"

    r2 = await client.get("/")
    assert 'value="25"' in r2.text
    assert 'value="5"' in r2.text


# --- API: User Profile ---

@pytest.mark.asyncio
async def test_get_user_profile(client):
    r = await client.get("/api/user-profile")
    assert r.status_code == 200
    data = r.json()
    assert "profile" in data
    assert "pseudo" in data["profile"]
    assert "description" in data["profile"]


@pytest.mark.asyncio
async def test_save_user_profile(client):
    r = await client.post("/api/user-profile", json={
        "pseudo": "test_user",
        "description": "Je suis un testeur",
        "age": "30 ans",
        "type": "Homme Bi",
        "location": "Lyon"
    })
    assert r.status_code == 200
    assert r.json()["status"] == "saved"
    assert r.json()["profile"]["pseudo"] == "test_user"

    # Verify it persisted
    r2 = await client.get("/api/user-profile")
    assert r2.json()["profile"]["pseudo"] == "test_user"


# --- API: Close ---

@pytest.mark.asyncio
async def test_close_browser_when_not_open(client):
    r = await client.post("/api/close/tinder")
    assert r.status_code == 200
    assert r.json()["status"] == "closed"


# --- API: Job Status ---

@pytest.mark.asyncio
async def test_job_status_idle(client):
    r = await client.get("/api/job-status/likes/wyylde")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


# --- Registry ---

@pytest.mark.asyncio
async def test_platforms_registry():
    assert "tinder" in bot_engine.PLATFORMS
    assert "meetic" in bot_engine.PLATFORMS
    assert "wyylde" in bot_engine.PLATFORMS


@pytest.mark.asyncio
async def test_activity_log_empty_on_start(client):
    r = await client.get("/")
    assert "Aucune activite pour le moment" in r.text


# --- API: Check Replies (unread sidebar) ---

@pytest.mark.asyncio
async def test_check_replies_returns_error_when_not_connected(client):
    r = await client.post("/api/check-replies/wyylde")
    assert r.status_code == 200
    data = r.json()
    assert data["error"] == "not_connected"


# --- API: User Profile Enrich ---

@pytest.mark.asyncio
async def test_enrich_profile_endpoint_exists(client):
    r = await client.post("/api/user-profile/enrich")
    # May fail without OpenAI key, but endpoint should exist (not 404)
    assert r.status_code != 404


# --- API: Templates CRUD ---

@pytest.mark.asyncio
async def test_get_templates_returns_defaults(client):
    r = await client.get("/api/templates")
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data
    assert len(data["templates"]) > 0


@pytest.mark.asyncio
async def test_get_templates_filter_by_desire(client):
    r = await client.get("/api/templates?desire=Gang bang")
    assert r.status_code == 200
    data = r.json()
    for t in data["templates"]:
        assert t["desire"] == "Gang bang"


@pytest.mark.asyncio
async def test_create_template(client):
    r = await client.post("/api/templates", json={
        "desire": "Test Desire",
        "label": "Test Label",
        "content": "Test content for template",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r2 = await client.get("/api/templates?desire=Test Desire")
    templates = r2.json()["templates"]
    assert any(t["label"] == "Test Label" for t in templates)


@pytest.mark.asyncio
async def test_create_template_missing_fields(client):
    r = await client.post("/api/templates", json={
        "desire": "Test",
        "label": "",
        "content": "Something",
    })
    assert r.status_code == 200
    assert r.json()["error"] == "missing_fields"


@pytest.mark.asyncio
async def test_update_template(client):
    # Create one first
    await client.post("/api/templates", json={
        "desire": "UpdateTest",
        "label": "Original",
        "content": "Original content",
    })
    r = await client.get("/api/templates?desire=UpdateTest")
    tid = r.json()["templates"][0]["id"]

    # Update it
    r2 = await client.post("/api/templates", json={
        "id": tid,
        "desire": "UpdateTest",
        "label": "Updated",
        "content": "Updated content",
    })
    assert r2.json()["status"] == "ok"

    r3 = await client.get("/api/templates?desire=UpdateTest")
    assert r3.json()["templates"][0]["label"] == "Updated"


@pytest.mark.asyncio
async def test_delete_template(client):
    await client.post("/api/templates", json={
        "desire": "DelTest",
        "label": "ToDelete",
        "content": "Will be deleted",
    })
    r = await client.get("/api/templates?desire=DelTest")
    tid = r.json()["templates"][0]["id"]

    r2 = await client.delete(f"/api/templates/{tid}")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ok"

    r3 = await client.get("/api/templates?desire=DelTest")
    assert len(r3.json()["templates"]) == 0


# --- API: Debug/Screenshot endpoints (not connected) ---

@pytest.mark.asyncio
async def test_debug_endpoint_not_connected(client):
    r = await client.get("/api/debug/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


@pytest.mark.asyncio
async def test_screenshot_not_connected(client):
    r = await client.get("/api/screenshot/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


@pytest.mark.asyncio
async def test_debug_sidebar_not_connected(client):
    r = await client.get("/api/debug-sidebar/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


@pytest.mark.asyncio
async def test_debug_chat_not_connected(client):
    r = await client.get("/api/debug-chat/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


@pytest.mark.asyncio
async def test_debug_unread_sidebar_not_connected(client):
    r = await client.get("/api/debug-unread-sidebar/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


@pytest.mark.asyncio
async def test_debug_profile_not_connected(client):
    r = await client.get("/api/debug-profile/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


@pytest.mark.asyncio
async def test_debug_mailbox_not_connected(client):
    r = await client.get("/api/debug-mailbox/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


# --- API: Message discussions / search (not connected) ---

@pytest.mark.asyncio
async def test_message_discussions_not_connected(client):
    r = await client.post("/api/message-discussions/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


@pytest.mark.asyncio
async def test_message_search_not_connected(client):
    r = await client.post("/api/message-search/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


# --- API: Explore (not connected) ---

@pytest.mark.asyncio
async def test_explore_not_connected(client):
    r = await client.post("/api/explore/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


# --- API: Auto-reply (not connected) ---

@pytest.mark.asyncio
async def test_auto_reply_not_connected(client):
    r = await client.post("/api/auto-reply/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


# --- API: My profile (not connected) ---

@pytest.mark.asyncio
async def test_my_profile_not_connected(client):
    r = await client.get("/api/my-profile/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


# --- API: Test message flow (not connected) ---

@pytest.mark.asyncio
async def test_test_message_not_connected(client):
    r = await client.post("/api/test-message/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


# --- API: Test sidebar buttons (not connected) ---

@pytest.mark.asyncio
async def test_test_sidebar_buttons_not_connected(client):
    r = await client.get("/api/test-sidebar-buttons/wyylde")
    assert r.status_code == 200
    assert r.json()["error"] == "not_connected"


# --- API: User Profile with categories ---

@pytest.mark.asyncio
async def test_save_user_profile_with_categories(client):
    r = await client.post("/api/user-profile", json={
        "pseudo": "cat_user",
        "description": "Test",
        "age": "28",
        "type": "Femme",
        "location": "Marseille",
        "categories": {
            "passions": "Cuisine, Voyage",
            "personnalite": "Curieuse",
        }
    })
    assert r.status_code == 200
    assert r.json()["profile"]["categories"]["passions"] == "Cuisine, Voyage"


# --- API: Enrich profile with mocked OpenAI ---

@pytest.mark.asyncio
async def test_enrich_profile_with_mocked_openai(client):
    mock_client_instance = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"passions": "Rando, Cinema", "personnalite": "Ouvert"}'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.routes.profile.AsyncOpenAI", return_value=mock_client_instance):
        r = await client.post("/api/user-profile/enrich", json={
            "pseudo": "enriched",
            "description": "Fan de rando",
            "categories": {
                "passions": "",
                "personnalite": "",
            }
        })
    assert r.status_code == 200
    assert r.json()["status"] == "enriched"


# --- API: Reload ---

@pytest.mark.asyncio
async def test_reload_endpoint(client):
    r = await client.post("/api/reload")
    assert r.status_code == 200
    assert r.json()["status"] == "reloaded"


# --- API: Job Status edge cases ---

@pytest.mark.asyncio
async def test_job_status_various_types(client):
    for job_type in ["likes", "messages", "replies"]:
        r = await client.get(f"/api/job-status/{job_type}/wyylde")
        assert r.status_code == 200
        assert r.json()["status"] == "idle"


# --- API: Close for all platforms ---

@pytest.mark.asyncio
async def test_close_all_platforms(client):
    for platform in ["tinder", "meetic", "wyylde"]:
        r = await client.post(f"/api/close/{platform}")
        assert r.status_code == 200
        assert r.json()["status"] == "closed"


# --- Security: Platform whitelist ---

@pytest.mark.asyncio
async def test_invalid_platform_rejected(client):
    r = await client.post("/api/browser/hackme")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


@pytest.mark.asyncio
async def test_invalid_platform_likes(client):
    r = await client.post("/api/likes/badplatform")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_platform"


# --- Security: Auth middleware ---

@pytest.mark.asyncio
async def test_auth_middleware_blocks_without_token(tmp_path, monkeypatch):
    """When DASHBOARD_TOKEN is set, remote requests without token get 401."""
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret123")
    # Patch request.client to simulate a remote IP (not localhost)
    from unittest.mock import patch, PropertyMock
    orig_middleware = app.middleware_stack
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Simulate remote client by temporarily changing the middleware logic
        with patch("src.app.Request.client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = type("Addr", (), {"host": "203.0.113.1"})()
            r = await c.get("/api/user-profile")
            assert r.status_code == 401


@pytest.mark.asyncio
async def test_auth_middleware_allows_with_token(tmp_path, monkeypatch):
    """When DASHBOARD_TOKEN is set, remote requests with correct token pass."""
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret123")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/user-profile", headers={"Authorization": "Bearer secret123"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_auth_middleware_allows_localhost(tmp_path, monkeypatch):
    """Localhost requests should bypass token auth."""
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret123")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # ASGI test client connects as 127.0.0.1 by default
        r = await c.get("/api/user-profile")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_auth_middleware_skips_non_api_routes(tmp_path, monkeypatch):
    """Auth middleware only applies to /api/* routes."""
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret123")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/")
        assert r.status_code == 200


# --- Security: Headers ---

@pytest.mark.asyncio
async def test_security_headers_present(client):
    r = await client.get("/")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


# --- Security: Settings validation ---

@pytest.mark.asyncio
async def test_settings_validation_rejects_bad_values(client):
    r = await client.post("/api/settings", json={
        "likes_per_session": 9999,
        "messages_per_session": 5,
        "delay_min": 2,
        "delay_max": 10,
    })
    assert r.status_code == 400


# --- Security: Profile validation ---

@pytest.mark.asyncio
async def test_profile_rejects_too_long_pseudo(client):
    r = await client.post("/api/user-profile", json={
        "pseudo": "x" * 200,
        "description": "test",
    })
    assert r.status_code == 400
