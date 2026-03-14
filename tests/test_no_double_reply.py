"""Test the anti-double-message logic.

RULE: Never send multiple messages to the same person without a reply from them.
The detection must find our last message in the conversation text,
and only reply if there is new content AFTER our message.
"""
import re


def _has_new_reply(full_text: str, last_msg_sent: str) -> tuple[bool, str]:
    """Simulate the logic from check_and_reply_unread.
    Returns (should_reply, reason)."""
    if not last_msg_sent:
        # Never messaged them
        return (len(full_text) > 15, "never_messaged")

    # Try to find our last message in the conversation
    # Use the longest matching snippet, then skip past the FULL message length
    found_our_msg = False
    our_msg_end_idx = -1
    for slen in [60, 40, 25, 15]:
        snippet = last_msg_sent[:slen]
        idx = full_text.rfind(snippet)
        if idx >= 0:
            found_our_msg = True
            # Skip past the full message (not just the snippet)
            our_msg_end_idx = idx + len(last_msg_sent)
            # But don't go past the conversation text
            if our_msg_end_idx > len(full_text):
                our_msg_end_idx = len(full_text)
            break

    if found_our_msg:
        after_our_msg = full_text[our_msg_end_idx:].strip()
        clean_after = re.sub(
            r"(Aujourd'hui \d{1,2}:\d{2}|Hier \d{1,2}:\d{2}|il y a \d+\s*\w+|\d{1,2}:\d{2}|Aujourd'hui|Hier|il y a|à \d|Envoyer|Votre message|paper-plane)",
            '', after_our_msg
        )
        clean_after = clean_after.strip()
        if len(clean_after) < 15:
            return (False, f"our_msg_found_nothing_new ({len(clean_after)} chars)")
        else:
            return (True, f"new_content_after_ours ({len(clean_after)} chars)")
    else:
        # Cannot find our message -> safety: do NOT reply
        return (False, "msg_not_found_safety")


# ---- Test cases ----

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


def test_rejection_detected():
    """Test rejection patterns."""
    rejection_patterns = [
        r"(?i)\b(non merci|pas int[eé]ress|arr[eê]te|stop|fiche[z-]? (?:moi |nous )?la paix|casse.?couilles?|d[eé]gage|bloqu|on t.a (?:dit|fait) non|lache|spam|harc[eè]l)",
        r"(?i)\b(ne? m.(?:int[eé]resse|convient)|laisse[z-]? (?:moi|nous)|plus la peine|tranquille)",
    ]

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
        found = any(re.search(p, text) for p in rejection_patterns)
        assert found, f"Should detect rejection in: '{text}'"

    for text in non_rejects:
        found = any(re.search(p, text) for p in rejection_patterns)
        assert not found, f"Should NOT detect rejection in: '{text}'"
