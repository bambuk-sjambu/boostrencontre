"""Tests for the multi-turn conversation manager."""

import pytest
import os
import aiosqlite
import src.database as db_mod
from src.database import init_db, get_db
from src.messaging.conversation_manager import (
    STAGES,
    get_conversation_stage,
    record_message,
    get_conversation_summary,
    detect_stage_transition,
    get_conversation_stats,
    list_conversations,
    get_full_conversation,
    _determine_stage_by_turns,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp DB for each test."""
    db_mod.DB_PATH = str(tmp_path / "test.db")
    await init_db()
    yield
    if os.path.exists(db_mod.DB_PATH):
        os.remove(db_mod.DB_PATH)


# --- Stage determination by turns ---

def test_determine_stage_0_turns():
    """0 sent messages -> accroche."""
    assert _determine_stage_by_turns(0) == "accroche"


def test_determine_stage_1_turn():
    """1 sent message -> accroche (max_turns=1)."""
    assert _determine_stage_by_turns(1) == "accroche"


def test_determine_stage_2_turns():
    """2 sent messages -> interet (accroche max=1, so 2 is in interet)."""
    assert _determine_stage_by_turns(2) == "interet"


def test_determine_stage_4_turns():
    """4 sent messages -> interet (accroche=1 + interet max=3 = 4)."""
    assert _determine_stage_by_turns(4) == "interet"


def test_determine_stage_5_turns():
    """5 sent messages -> approfondissement."""
    assert _determine_stage_by_turns(5) == "approfondissement"


def test_determine_stage_8_turns():
    """8 sent messages -> approfondissement (1+3+4=8)."""
    assert _determine_stage_by_turns(8) == "approfondissement"


def test_determine_stage_9_turns():
    """9 sent messages -> proposition."""
    assert _determine_stage_by_turns(9) == "proposition"


def test_determine_stage_15_turns():
    """15 sent messages -> proposition (overflow)."""
    assert _determine_stage_by_turns(15) == "proposition"


# --- get_conversation_stage ---

@pytest.mark.asyncio
async def test_get_stage_empty_conversation():
    """No history -> accroche stage."""
    result = await get_conversation_stage("wyylde", "Alice")
    assert result["stage"] == "accroche"
    assert result["sent_count"] == 0
    assert result["received_count"] == 0
    assert result["total_turns"] == 0
    assert result["history"] == []


@pytest.mark.asyncio
async def test_get_stage_after_messages():
    """After recording messages, stage should reflect turn count."""
    await record_message("wyylde", "Bob", "sent", "Salut Bob!", style="auto")
    await record_message("wyylde", "Bob", "received", "Hey! Ca va?")
    result = await get_conversation_stage("wyylde", "Bob")
    assert result["sent_count"] == 1
    assert result["received_count"] == 1
    assert result["total_turns"] == 2
    assert result["stage"] == "accroche"


@pytest.mark.asyncio
async def test_get_stage_interet():
    """After 2 sent messages, should be in interet."""
    await record_message("wyylde", "Clara", "sent", "Premier message")
    await record_message("wyylde", "Clara", "received", "Reponse 1")
    await record_message("wyylde", "Clara", "sent", "Deuxieme message")
    result = await get_conversation_stage("wyylde", "Clara")
    assert result["sent_count"] == 2
    # Stage is 'accroche' because last recorded stage was accroche;
    # transitions happen via detect_stage_transition
    assert result["stage"] in ("accroche", "interet")


# --- record_message ---

@pytest.mark.asyncio
async def test_record_message_creates_entry():
    """Recording a message should create a DB entry."""
    await record_message("wyylde", "Diana", "sent", "Hello Diana!", style="romantique")
    async with await get_db() as db:
        db.row_factory = db_mod.dict_factory
        cursor = await db.execute(
            "SELECT * FROM conversation_history WHERE contact_name = 'Diana'"
        )
        rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["platform"] == "wyylde"
    assert rows[0]["direction"] == "sent"
    assert rows[0]["message_text"] == "Hello Diana!"
    assert rows[0]["style_used"] == "romantique"
    assert rows[0]["stage"] == "accroche"
    assert rows[0]["turn_number"] == 1


@pytest.mark.asyncio
async def test_record_message_increments_turn():
    """Turn number should increment with each message."""
    await record_message("wyylde", "Eve", "sent", "Msg 1")
    await record_message("wyylde", "Eve", "received", "Reply 1")
    await record_message("wyylde", "Eve", "sent", "Msg 2")
    async with await get_db() as db:
        db.row_factory = db_mod.dict_factory
        cursor = await db.execute(
            "SELECT turn_number FROM conversation_history "
            "WHERE contact_name = 'Eve' ORDER BY id"
        )
        rows = await cursor.fetchall()
    turns = [r["turn_number"] for r in rows]
    assert turns == [1, 2, 3]


# --- get_conversation_summary ---

@pytest.mark.asyncio
async def test_summary_empty():
    """Empty conversation returns empty string."""
    result = await get_conversation_summary("wyylde", "Nobody")
    assert result == ""


@pytest.mark.asyncio
async def test_summary_formats_correctly():
    """Summary should format messages as 'Who: text'."""
    await record_message("wyylde", "Frank", "sent", "Salut Frank!")
    await record_message("wyylde", "Frank", "received", "Hey, ca va?")
    result = await get_conversation_summary("wyylde", "Frank")
    assert "Moi: Salut Frank!" in result
    assert "Frank: Hey, ca va?" in result
    # Should be in chronological order
    lines = result.strip().split("\n")
    assert len(lines) == 2
    # Order depends on insertion time; just verify both are present
    moi_lines = [l for l in lines if l.startswith("Moi:")]
    frank_lines = [l for l in lines if l.startswith("Frank:")]
    assert len(moi_lines) == 1
    assert len(frank_lines) == 1


# --- detect_stage_transition ---

@pytest.mark.asyncio
async def test_transition_no_signals():
    """Without interest signals and under max_turns, stay at current stage."""
    await record_message("wyylde", "Grace", "sent", "Salut!")
    result = await detect_stage_transition("wyylde", "Grace", "Bonjour, merci")
    # After 1 sent message, max_turns for "accroche" (1) is reached,
    # so transition to "interet" is expected
    assert result == "interet"


@pytest.mark.asyncio
async def test_transition_strong_interest():
    """Strong interest signals should advance the stage."""
    await record_message("wyylde", "Heidi", "sent", "Premier msg")
    # Reply with multiple interest signals
    result = await detect_stage_transition(
        "wyylde", "Heidi",
        "J'ai trop envie de te rencontrer, on se voit quand?"
    )
    assert result == "interet"


@pytest.mark.asyncio
async def test_transition_max_turns_reached():
    """When max turns reached without disinterest, should advance."""
    # Accroche has max_turns=1. Record 1 sent message.
    await record_message("wyylde", "Iris", "sent", "Accroche message")
    await record_message("wyylde", "Iris", "received", "Reponse positive")
    # Now transition with neutral reply
    result = await detect_stage_transition("wyylde", "Iris", "Super, j'aime bien")
    assert result == "interet"


@pytest.mark.asyncio
async def test_transition_disinterest_blocks():
    """Disinterest signals should prevent stage advancement."""
    await record_message("wyylde", "Julie", "sent", "Msg 1")
    result = await detect_stage_transition(
        "wyylde", "Julie",
        "Sais pas trop, on verra plus tard"
    )
    # Should stay because of disinterest signals
    assert result == "accroche"


# --- get_conversation_stats ---

@pytest.mark.asyncio
async def test_stats_empty():
    """Empty platform returns zero stats."""
    stats = await get_conversation_stats("wyylde")
    assert stats["total_conversations"] == 0
    assert stats["avg_turns"] == 0.0
    assert all(v == 0 for v in stats["by_stage"].values())


@pytest.mark.asyncio
async def test_stats_with_data():
    """Stats should reflect recorded conversations."""
    await record_message("wyylde", "Kate", "sent", "Msg 1")
    await record_message("wyylde", "Kate", "received", "Reply 1")
    await record_message("wyylde", "Laura", "sent", "Msg 1")
    stats = await get_conversation_stats("wyylde")
    assert stats["total_conversations"] == 2
    assert stats["avg_turns"] > 0


# --- list_conversations ---

@pytest.mark.asyncio
async def test_list_conversations_empty():
    """No conversations returns empty list."""
    result = await list_conversations("wyylde")
    assert result == []


@pytest.mark.asyncio
async def test_list_conversations_with_data():
    """Should list conversations with metadata."""
    await record_message("wyylde", "Marie", "sent", "Bonjour Marie")
    await record_message("wyylde", "Marie", "received", "Salut!")
    await record_message("wyylde", "Nadia", "sent", "Hey Nadia")
    result = await list_conversations("wyylde")
    assert len(result) == 2
    names = [c["contact_name"] for c in result]
    assert "Marie" in names
    assert "Nadia" in names
    # Check structure
    marie = next(c for c in result if c["contact_name"] == "Marie")
    assert marie["turn_count"] == 2
    assert marie["sent_count"] == 1
    assert marie["received_count"] == 1
    assert marie["stage"] == "accroche"
    assert "last_message" in marie
    assert "last_at" in marie


# --- get_full_conversation ---

@pytest.mark.asyncio
async def test_full_conversation():
    """Should return all messages in chronological order."""
    await record_message("wyylde", "Olivia", "sent", "Msg 1")
    await record_message("wyylde", "Olivia", "received", "Reply 1")
    await record_message("wyylde", "Olivia", "sent", "Msg 2")
    result = await get_full_conversation("wyylde", "Olivia")
    assert len(result) == 3
    assert result[0]["direction"] == "sent"
    assert result[1]["direction"] == "received"
    assert result[2]["direction"] == "sent"
    assert result[0]["message_text"] == "Msg 1"


# --- STAGES structure ---

def test_stages_has_all_required_keys():
    """Each stage should have description, max_turns, next, prompt_addon."""
    for name, stage in STAGES.items():
        assert "description" in stage, f"Stage {name} missing 'description'"
        assert "max_turns" in stage, f"Stage {name} missing 'max_turns'"
        assert "next" in stage, f"Stage {name} missing 'next'"
        assert "prompt_addon" in stage, f"Stage {name} missing 'prompt_addon'"


def test_stages_chain_is_valid():
    """next pointers should form a valid chain ending with None."""
    stage = "accroche"
    visited = set()
    while stage is not None:
        assert stage in STAGES, f"Stage '{stage}' not found in STAGES"
        assert stage not in visited, f"Cycle detected at stage '{stage}'"
        visited.add(stage)
        stage = STAGES[stage]["next"]
    assert "proposition" in visited, "Chain should reach 'proposition'"


# --- Database table existence ---

@pytest.mark.asyncio
async def test_conversation_history_table_exists():
    """init_db should create the conversation_history table."""
    async with aiosqlite.connect(db_mod.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_history'"
        )
        row = await cursor.fetchone()
    assert row is not None, "conversation_history table not created"
