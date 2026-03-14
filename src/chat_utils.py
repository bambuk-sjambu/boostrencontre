import re

# Lines to ignore when scanning chat content
_IGNORE_PATTERNS = [
    re.compile(r'^\d{1,2}[:/h]\d{2}$'),          # timestamps like "14:32" or "14h32"
    re.compile(r'^\d{1,2}:\d{2}\s*(AM|PM)$', re.IGNORECASE),
    re.compile(r'^Envoyer$', re.IGNORECASE),
    re.compile(r'^Votre message', re.IGNORECASE),
    re.compile(r'^NOUVEAUX$', re.IGNORECASE),
    re.compile(r'^\d+$'),                          # pure numbers
    re.compile(r'^Aujourd.hui$', re.IGNORECASE),
    re.compile(r'^Hier$', re.IGNORECASE),
    re.compile(r'^\d{1,2}\s+(janv|f[eé]vr|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[eé]c)', re.IGNORECASE),
]


def detect_last_sender(chat_content: str, my_pseudo: str, sender_name: str) -> str:
    """Scan chat text bottom-up to find whose pseudo appears last as a standalone line.

    Returns 'me', 'them', or 'unknown'.
    """
    if not chat_content or not chat_content.strip():
        return "unknown"

    lines = chat_content.strip().splitlines()
    my_lower = my_pseudo.strip().lower()
    their_lower = sender_name.strip().lower()

    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Skip known UI artifacts and timestamps
        if any(p.match(stripped) for p in _IGNORE_PATTERNS):
            continue

        # Exact line match (case-insensitive) against pseudos
        line_lower = stripped.lower()
        if line_lower == my_lower:
            return "me"
        if line_lower == their_lower:
            return "them"

    return "unknown"
