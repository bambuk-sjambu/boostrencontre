"""Test the anti-double-message logic.

RULE: Never send multiple messages to the same person without a reply from them.
Uses the REAL detect_our_last_message() and check_rejection() from source code
instead of reimplementing the logic.
"""
from src.conversation_utils import detect_our_last_message, check_rejection


# ---- _has_new_reply wrapper using real detect_our_last_message ----

def _has_new_reply(full_text: str, last_msg_sent: str | None) -> tuple[bool, str]:
    """Thin wrapper around real detect_our_last_message for test readability.
    Returns (should_reply, reason)."""
    if not last_msg_sent:
        # Never messaged them — reply if there's meaningful content
        return (len(full_text) > 15, "never_messaged")

    result = detect_our_last_message(full_text, last_msg_sent)

    if result["found"]:
        if result["has_new_content"]:
            return (True, f"new_content_after_ours ({result['new_content_len']} chars)")
        else:
            return (False, f"our_msg_found_nothing_new ({result['new_content_len']} chars)")
    else:
        return (False, "msg_not_found_safety")


# ---- Test cases for detect_our_last_message ----

def test_we_sent_last_no_reply():
    """We sent a message, they didn't reply -> DON'T send again."""
    conv = "Bonjour Marie ! Comment vas-tu ?\nAujourd'hui 14:30\nSalut Marie, je suis curieux de te connaitre"
    our_msg = "Salut Marie, je suis curieux de te connaitre"
    should, reason = _has_new_reply(conv, our_msg)
    assert not should, f"Should NOT reply but got: {reason}"


def test_they_replied_after_us():
    """We sent, they replied -> we CAN reply."""
    conv = "Salut Marie, je suis curieux\nAujourd'hui 14:30\nMerci c'est gentil ! Moi aussi j'aimerais bien discuter avec toi"
    our_msg = "Salut Marie, je suis curieux"
    should, reason = _has_new_reply(conv, our_msg)
    assert should, f"Should reply but got: {reason}"


def test_we_sent_only_timestamp_after():
    """Our message is last, only timestamps after -> DON'T reply."""
    conv = "Hey salut, tu veux discuter ?\nAujourd'hui 15:00\nJe suis super content de te parler\nHier 10:30"
    our_msg = "Je suis super content de te parler"
    should, reason = _has_new_reply(conv, our_msg)
    assert not should, f"Should NOT reply but got: {reason}"


def test_never_messaged_they_wrote():
    """We never messaged, they wrote to us -> reply."""
    conv = "Coucou, ton profil m'interesse beaucoup !"
    should, reason = _has_new_reply(conv, None)
    assert should, f"Should reply (they initiated) but got: {reason}"


def test_never_messaged_empty():
    """Empty conversation, never messaged -> don't reply."""
    conv = ""
    should, reason = _has_new_reply(conv, None)
    assert not should, f"Should NOT reply but got: {reason}"


def test_our_msg_not_found_safety():
    """Our message not in conversation (formatting diff) -> DON'T reply (safety)."""
    conv = "Quelqu'un a dit bonjour\nEt ensuite autre chose"
    our_msg = "Ceci est un message completement different qui n'apparait pas"
    should, reason = _has_new_reply(conv, our_msg)
    assert not should, f"Should NOT reply (safety) but got: {reason}"


def test_multiple_messages_no_double():
    """We sent 2 messages, they replied once -> we already replied, DON'T send 3rd."""
    conv = (
        "Bonjour kokins77, j'aime bien ton pseudo\n"
        "Aujourd'hui 10:00\n"
        "Merci c'est sympa !\n"
        "Aujourd'hui 10:05\n"
        "Je suis totalement d'accord, cette authenticite rend chaque rencontre unique\n"
        "Aujourd'hui 10:10"
    )
    # Our LAST message (the reply we already sent)
    our_msg = "Je suis totalement d'accord, cette authenticite rend chaque rencontre unique"
    should, reason = _has_new_reply(conv, our_msg)
    assert not should, f"Should NOT reply (we already replied) but got: {reason}"


def test_they_replied_to_our_second_msg():
    """We sent, they replied, we replied, they replied again -> we CAN reply."""
    conv = (
        "Bonjour !\n"
        "Merci c'est sympa !\n"
        "Je suis d'accord avec toi\n"
        "Oh super, tu as raison, on devrait se voir un de ces jours !"
    )
    our_msg = "Je suis d'accord avec toi"
    should, reason = _has_new_reply(conv, our_msg)
    assert should, f"Should reply (they wrote after our 2nd msg) but got: {reason}"


# ---- Test detect_our_last_message directly ----

def test_detect_returns_dict_structure():
    """detect_our_last_message returns the expected dict keys."""
    result = detect_our_last_message("some chat text", "some message")
    assert "found" in result
    assert "has_new_content" in result
    assert "new_content_len" in result
    assert "new_content" in result


def test_detect_empty_last_sent():
    """If last_sent_msg is empty, found should be False."""
    result = detect_our_last_message("Hello world", "")
    assert not result["found"]


# ---- Rejection tests using real check_rejection ----

def test_rejection_detected():
    """Test rejection patterns using the real check_rejection function."""
    rejects = [
        "T'es pas casse couilles on t'a dit non",
        "Non merci, pas interessée",
        "Arrete de m'ecrire",
        "Laissez-nous tranquille",
        "Stop spam",
        "Tu me harceles",
        "Degage",
    ]
    non_rejects = [
        "Salut, ca va ?",
        "Merci pour ton message",
        "Je ne sais pas encore",
        "Non je n'ai pas de photo",  # "non" alone isn't rejection
    ]

    for text in rejects:
        assert check_rejection(text), f"Should detect rejection in: '{text}'"

    for text in non_rejects:
        assert not check_rejection(text), f"Should NOT detect rejection in: '{text}'"
