"""Tests for the database module — init, tables, CRUD operations."""
import pytest
import os
import json
import aiosqlite
import src.database as db_mod
from src.database import init_db, get_db


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp DB for each test."""
    db_mod.DB_PATH = str(tmp_path / "test.db")
    yield
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


# --- init_db creates all tables ---

@pytest.mark.asyncio
async def test_init_db_creates_all_tables():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
    for expected in ("accounts", "activity_log", "settings", "user_profile", "message_templates"):
        assert expected in tables, f"Table '{expected}' not created by init_db()"


@pytest.mark.asyncio
async def test_init_db_is_idempotent():
    """Calling init_db() twice should not fail or duplicate data."""
    await init_db()
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        count = (await cursor.fetchone())[0]
    assert count == 1, "Settings should have exactly 1 row after double init"


# --- Settings defaults ---

@pytest.mark.asyncio
async def test_settings_default_values():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM settings WHERE id = 1")
        row = await cursor.fetchone()
    assert row is not None, "Default settings row should exist"
    # id, likes_per_session, messages_per_session, delay_min, delay_max
    assert row[1] == 50   # likes_per_session
    assert row[2] == 3    # messages_per_session
    assert row[3] == 3    # delay_min
    assert row[4] == 8    # delay_max


@pytest.mark.asyncio
async def test_settings_update():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "UPDATE settings SET likes_per_session = 25, delay_min = 5 WHERE id = 1"
        )
        await db.commit()
        cursor = await db.execute("SELECT likes_per_session, delay_min FROM settings WHERE id = 1")
        row = await cursor.fetchone()
    assert row == (25, 5)


# --- Activity log ---

@pytest.mark.asyncio
async def test_activity_log_insert_and_read():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name, message_sent) VALUES (?, ?, ?, ?)",
            ("wyylde", "message", "Marie", "Salut Marie !")
        )
        await db.commit()
        cursor = await db.execute("SELECT platform, action, target_name, message_sent FROM activity_log")
        row = await cursor.fetchone()
    assert row == ("wyylde", "message", "Marie", "Salut Marie !")


@pytest.mark.asyncio
async def test_activity_log_empty_on_init():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM activity_log")
        count = (await cursor.fetchone())[0]
    assert count == 0


@pytest.mark.asyncio
async def test_activity_log_multiple_entries():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        for i in range(5):
            await db.execute(
                "INSERT INTO activity_log (platform, action, target_name) VALUES (?, ?, ?)",
                ("tinder", "like", f"User_{i}")
            )
        await db.commit()
        cursor = await db.execute("SELECT COUNT(*) FROM activity_log WHERE platform = 'tinder'")
        count = (await cursor.fetchone())[0]
    assert count == 5


@pytest.mark.asyncio
async def test_activity_log_has_timestamp():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity_log (platform, action, target_name) VALUES (?, ?, ?)",
            ("meetic", "like", "Alice")
        )
        await db.commit()
        cursor = await db.execute("SELECT created_at FROM activity_log WHERE target_name = 'Alice'")
        row = await cursor.fetchone()
    assert row[0] is not None, "created_at should be auto-set"


# --- User profile ---

@pytest.mark.asyncio
async def test_user_profile_save_and_load():
    await init_db()
    profile = {"pseudo": "tester", "type": "Homme", "age": "25", "location": "Paris", "description": "Test desc"}
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_profile (id, data) VALUES (1, ?)",
            (json.dumps(profile),)
        )
        await db.commit()
        cursor = await db.execute("SELECT data FROM user_profile WHERE id = 1")
        row = await cursor.fetchone()
    loaded = json.loads(row[0])
    assert loaded["pseudo"] == "tester"
    assert loaded["location"] == "Paris"


@pytest.mark.asyncio
async def test_user_profile_update_replaces():
    await init_db()
    p1 = {"pseudo": "first"}
    p2 = {"pseudo": "second"}
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO user_profile (id, data) VALUES (1, ?)", (json.dumps(p1),))
        await db.commit()
        await db.execute("INSERT OR REPLACE INTO user_profile (id, data) VALUES (1, ?)", (json.dumps(p2),))
        await db.commit()
        cursor = await db.execute("SELECT COUNT(*) FROM user_profile")
        count = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT data FROM user_profile WHERE id = 1")
        row = await cursor.fetchone()
    assert count == 1
    assert json.loads(row[0])["pseudo"] == "second"


@pytest.mark.asyncio
async def test_user_profile_empty_on_init():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM user_profile")
        count = (await cursor.fetchone())[0]
    assert count == 0


# --- Accounts ---

@pytest.mark.asyncio
async def test_accounts_insert():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute("INSERT INTO accounts (platform) VALUES (?)", ("wyylde",))
        await db.commit()
        cursor = await db.execute("SELECT platform, status FROM accounts WHERE platform = 'wyylde'")
        row = await cursor.fetchone()
    assert row[0] == "wyylde"
    assert row[1] == "disconnected"  # default status


@pytest.mark.asyncio
async def test_accounts_status_update():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute("INSERT INTO accounts (platform) VALUES (?)", ("tinder",))
        await db.execute("UPDATE accounts SET status = 'connected' WHERE platform = 'tinder'")
        await db.commit()
        cursor = await db.execute("SELECT status FROM accounts WHERE platform = 'tinder'")
        row = await cursor.fetchone()
    assert row[0] == "connected"


# --- Message templates ---

@pytest.mark.asyncio
async def test_default_templates_created():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM message_templates")
        count = (await cursor.fetchone())[0]
    assert count > 0, "Default templates should be inserted"


@pytest.mark.asyncio
async def test_templates_have_required_fields():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute("SELECT desire, label, content FROM message_templates LIMIT 1")
        row = await cursor.fetchone()
    assert row[0], "desire should not be empty"
    assert row[1], "label should not be empty"
    assert row[2], "content should not be empty"


@pytest.mark.asyncio
async def test_templates_insert_custom():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO message_templates (desire, label, content) VALUES (?, ?, ?)",
            ("Test", "Mon template", "Contenu du template")
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT content FROM message_templates WHERE desire = 'Test' AND label = 'Mon template'"
        )
        row = await cursor.fetchone()
    assert row[0] == "Contenu du template"


@pytest.mark.asyncio
async def test_templates_delete():
    await init_db()
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        await db.execute(
            "INSERT INTO message_templates (desire, label, content) VALUES (?, ?, ?)",
            ("ToDelete", "Del", "Content")
        )
        await db.commit()
        cursor = await db.execute("SELECT id FROM message_templates WHERE desire = 'ToDelete'")
        tid = (await cursor.fetchone())[0]
        await db.execute("DELETE FROM message_templates WHERE id = ?", (tid,))
        await db.commit()
        cursor = await db.execute("SELECT COUNT(*) FROM message_templates WHERE desire = 'ToDelete'")
        count = (await cursor.fetchone())[0]
    assert count == 0


# --- get_db() helper ---

@pytest.mark.asyncio
async def test_get_db_returns_connection():
    await init_db()
    conn = await get_db()
    assert conn is not None
    async with conn as db:
        cursor = await db.execute("SELECT 1")
        row = await cursor.fetchone()
    assert row[0] == 1
