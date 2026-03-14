import pytest
from src.chat_utils import detect_last_sender


def test_detect_last_sender_them():
    chat = "alice\nSalut comment ca va?\n14:32\nbob\nBien et toi?\n14:35"
    assert detect_last_sender(chat, "alice", "bob") == "them"


def test_detect_last_sender_me():
    chat = "bob\nSalut!\n14:30\nalice\nOui ca va bien\n14:32"
    assert detect_last_sender(chat, "alice", "bob") == "me"


def test_detect_last_sender_unknown():
    chat = "51/58 ans\nCouple libertin"
    assert detect_last_sender(chat, "alice", "bob") == "unknown"


def test_detect_last_sender_pseudo_in_message():
    """Pseudo appearing inside a message text should NOT count as sender line."""
    chat = "bob\nHey alice comment vas-tu?\n14:32\nalice\nBien merci bob!\n14:35"
    # Last pseudo line is "alice", not "bob" even though "bob" appears in message text
    assert detect_last_sender(chat, "alice", "bob") == "me"


def test_detect_last_sender_case_insensitive():
    chat = "ALICE\nSalut\n14:30\nBOB\nHey!\n14:32"
    assert detect_last_sender(chat, "alice", "bob") == "them"


def test_detect_last_sender_with_ui_artifacts():
    chat = "bob\nSalut!\n14:30\nalice\nCa va\n14:32\nEnvoyer\nVotre message..."
    assert detect_last_sender(chat, "alice", "bob") == "me"


def test_detect_last_sender_empty():
    assert detect_last_sender("", "alice", "bob") == "unknown"
    assert detect_last_sender("   ", "alice", "bob") == "unknown"


def test_detect_last_sender_only_timestamps():
    chat = "14:30\n14:32\n14:35"
    assert detect_last_sender(chat, "alice", "bob") == "unknown"
