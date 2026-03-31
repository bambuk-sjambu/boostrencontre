import asyncio
import time

import pytest
from src.conversation_utils import check_rejection, filter_ui_text, detect_our_last_message, _human_delay, _human_delay_with_pauses


# ─── check_rejection ───

def test_check_rejection_non_merci():
    assert check_rejection("Blabla non merci, ca ne m'interesse pas") is True


def test_check_rejection_pas_interesse():
    assert check_rejection("On est pas interessees par ce genre de choses") is True


def test_check_rejection_arrete():
    assert check_rejection("Arrete de m'ecrire stp") is True


def test_check_rejection_stop():
    assert check_rejection("Stop! Ne m'ecris plus") is True


def test_check_rejection_degage():
    assert check_rejection("Degage d'ici") is True


def test_check_rejection_harcelement():
    assert check_rejection("Tu harceles les gens") is True


def test_check_rejection_laisse_nous():
    assert check_rejection("Laissez-nous tranquille") is True


def test_check_rejection_bloque():
    assert check_rejection("Je vais te bloquer") is True


def test_check_rejection_normal_text_not_rejected():
    assert check_rejection("Salut, ton profil m'interesse beaucoup !") is False


def test_check_rejection_empty_text():
    assert check_rejection("") is False


def test_check_rejection_friendly_conversation():
    assert check_rejection("On adore voyager, on part bientot en Espagne !") is False


def test_check_rejection_uses_last_500_chars():
    """Only the last 500 chars should be checked; rejection early in text should not match."""
    padding = "Coucou tout va bien je suis content " * 20  # ~700 chars
    text = "Non merci, degage" + padding
    assert check_rejection(text) is False


def test_check_rejection_recent_rejection_detected():
    """Rejection in the last 500 chars should be detected."""
    padding = "Texte normal " * 10
    text = padding + "Non merci laisse moi tranquille"
    assert check_rejection(text) is True


def test_check_rejection_case_insensitive():
    assert check_rejection("NON MERCI") is True
    assert check_rejection("Pas Interessé") is True


# ─── filter_ui_text ───

def test_filter_ui_text_removes_camera():
    lines = filter_ui_text("CAMERA\nSalut comment vas-tu aujourd'hui?")
    assert not any("CAMERA" in l for l in lines)


def test_filter_ui_text_removes_demander_a_voir():
    lines = filter_ui_text("DEMANDER À VOIR\nBonjour c'est un test de texte long")
    assert not any("DEMANDER" in l for l in lines)


def test_filter_ui_text_removes_profile_types():
    text = "Homme hétéro\nSalut comment ca va aujourd'hui?"
    lines = filter_ui_text(text)
    assert not any("Homme hétéro" in l for l in lines)


def test_filter_ui_text_removes_sender_name():
    text = "JeanDupont\nSalut je suis JeanDupont et je veux te parler"
    lines = filter_ui_text(text, sender_name="JeanDupont")
    assert not any("JeanDupont" in l for l in lines)


def test_filter_ui_text_keeps_meaningful_lines():
    text = "CAMERA\nSalut comment vas tu ca fait longtemps ?\nBien et toi mon ami?"
    lines = filter_ui_text(text)
    assert len(lines) >= 2


def test_filter_ui_text_drops_short_lines():
    text = "Ok\nBien\nSalut comment ca va toi aussi ?"
    lines = filter_ui_text(text)
    # "Ok" and "Bien" are <= 10 chars, should be dropped
    assert all(len(l) > 10 for l in lines)


def test_filter_ui_text_empty_input():
    assert filter_ui_text("") == []


def test_filter_ui_text_only_ui_patterns():
    text = "CAMERA\nDEMANDER À VOIR\nCouple hétéro"
    lines = filter_ui_text(text)
    assert lines == []


# ─── detect_our_last_message ───

def test_detect_our_msg_found_and_no_new_content():
    our_msg = "Salut comment ca va toi ?"
    chat = "Bonjour a tous\n" + our_msg
    result = detect_our_last_message(chat, our_msg)
    assert result["found"] is True
    assert result["has_new_content"] is False


def test_detect_our_msg_found_with_new_content():
    our_msg = "Salut comment ca va toi ?"
    new_reply = "Ca va super bien merci de demander !"
    chat = "Bonjour\n" + our_msg + "\n" + new_reply
    result = detect_our_last_message(chat, our_msg)
    assert result["found"] is True
    assert result["has_new_content"] is True
    assert result["new_content_len"] > 0


def test_detect_our_msg_not_found():
    chat = "Bonjour tout le monde comment allez vous"
    result = detect_our_last_message(chat, "Message jamais envoye dans cette conversation")
    assert result["found"] is False
    assert result["has_new_content"] is False


def test_detect_our_msg_empty_last_sent():
    result = detect_our_last_message("Some chat text here", "")
    assert result["found"] is False


def test_detect_our_msg_none_last_sent():
    result = detect_our_last_message("Some chat text here", None)
    assert result["found"] is False


def test_detect_our_msg_partial_match():
    """Should match even with a short snippet (15 chars)."""
    our_msg = "Salut ca va bien?"
    chat = "Hey\n" + our_msg + "\nReponse de quelqu'un d'autre ici"
    result = detect_our_last_message(chat, our_msg)
    assert result["found"] is True


def test_detect_our_msg_timestamp_after_our_msg_ignored():
    """Timestamps after our message should not count as new content."""
    our_msg = "Mon message envoye ici comme test"
    chat = "Hey\n" + our_msg + "\nAujourd'hui 14:32"
    result = detect_our_last_message(chat, our_msg)
    assert result["found"] is True
    assert result["has_new_content"] is False


# ─── _human_delay ───

@pytest.mark.asyncio
async def test_human_delay_returns_within_range():
    start = time.monotonic()
    await _human_delay(min_s=0.01, max_s=0.05)
    elapsed = time.monotonic() - start
    assert 0.005 <= elapsed <= 0.15


@pytest.mark.asyncio
async def test_human_delay_default_params():
    """Default params should not raise."""
    # Just test it completes quickly with small values
    await _human_delay(min_s=0.001, max_s=0.002)


@pytest.mark.asyncio
async def test_human_delay_custom_range():
    start = time.monotonic()
    await _human_delay(min_s=0.02, max_s=0.03)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.015  # allow small margin


# ─── _human_delay_with_pauses ───

@pytest.mark.asyncio
async def test_human_delay_with_pauses_completes():
    """Should complete without error and take at least min_s."""
    start = time.monotonic()
    await _human_delay_with_pauses(min_s=0.01, max_s=0.05)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.005


@pytest.mark.asyncio
async def test_human_delay_with_pauses_within_range():
    """Over several calls, delay should generally stay within a reasonable range."""
    import src.conversation_utils as cu
    cu._action_counters.clear()  # Reset counters to avoid long pause on first call
    durations = []
    for _ in range(5):
        start = time.monotonic()
        await _human_delay_with_pauses(min_s=0.01, max_s=0.04)
        durations.append(time.monotonic() - start)
    # At least some should be in the normal range (not all long pauses)
    normal = [d for d in durations if d < 1.0]
    assert len(normal) >= 3
