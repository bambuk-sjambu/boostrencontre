"""Centralized constants for BoostRencontre.

Shared values used across multiple modules: UI patterns, rejection patterns,
profile type filters, and default settings. Import from here rather than
duplicating values in bot_engine.py, app.py, etc.
"""

# ─── Profile type filters ───
# Used in sidebar scanning, search filters, and dashboard UI
PROFILE_TYPES = [
    "Couple F Bi",
    "Couple hétéro",
    "Couple M Bi",
    "Femme hétéro",
    "Femme Bi",
    "Homme hétéro",
    "Homme Bi",
    "Travesti",
]

# ─── Desire categories ───
# Used in search filters, templates, and dashboard UI
DESIRES = [
    "Gang bang",
    "Échangisme",
    "BDSM",
    "Exhibition",
    "Feeling",
    "Fétichisme",
    "Hard",
    "Papouilles",
    "Pluralité",
]

# ─── Message styles ───
# Canonical list of style keys (definitions in ai_messages.py STYLES dict)
MESSAGE_STYLE_KEYS = [
    "auto",
    "romantique",
    "direct_sexe",
    "humoristique",
    "intellectuel",
    "aventurier",
    "mystérieux",
    "complice",
]

# ─── UI text patterns to strip from chat content ───
# Used when filtering out Wyylde UI artifacts from conversation text
UI_PATTERNS = [
    "DEMANDER À VOIR",
    "CAMERA",
    "Homme hétéro",
    "Femme hétéro",
    "Couple hétéro",
    "Homme Bi",
    "Femme Bi",
    "Couple F Bi",
    "Couple H Bi",
]

# ─── Rejection patterns (regex) ───
# If any of these match in the last 500 chars of a conversation,
# mark the contact as rejected and never reply again.
REJECTION_PATTERNS = [
    r"(?i)\b(non merci|pas int[eé]ress|arr[eê]te|stop|fiche[z-]? (?:moi |nous )?la paix|casse.?couilles?|d[eé]gage|bloqu|on t.a (?:dit|fait) non|lache|spam|harc[eè]l)",
    r"(?i)\b(ne? m.(?:int[eé]resse|convient)|laisse[z-]? (?:moi|nous)|plus la peine|tranquille)",
]

# ─── Timestamp / UI cleanup regex ───
# Used to strip timestamps and UI text when checking for new messages after our last reply
TIMESTAMP_CLEANUP_REGEX = r"(Aujourd'hui \d{1,2}:\d{2}|Hier \d{1,2}:\d{2}|il y a \d+\s*\w+|\d{1,2}:\d{2}|Aujourd'hui|Hier|il y a|à \d|Envoyer|Votre message|paper-plane)"

# ─── Default settings ───
DEFAULT_LIKES_PER_SESSION = 50
DEFAULT_MESSAGES_PER_SESSION = 3
DEFAULT_DELAY_MIN = 3
DEFAULT_DELAY_MAX = 8

# ─── OpenAI model ───
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_TOKENS_MESSAGE = 300
OPENAI_MAX_TOKENS_ENRICH = 500

# ─── Desire keywords for bio detection ───
# Maps each desire category to keywords that may appear in a recipient's bio.
# Used by prompt_builder._detect_desires() to enrich AI prompts.
DESIRE_KEYWORDS = {
    "Gang bang": ["gang", "gb", "gangbang", "multi"],
    "Échangisme": ["echange", "échange", "echangisme", "swap", "couple echangiste"],
    "BDSM": ["bdsm", "domination", "soumission", "dom", "sub", "maitre", "maitresse", "bondage"],
    "Exhibition": ["exhibition", "exhib", "voyeur", "voyeurisme", "montre"],
    "Feeling": ["feeling", "feeling avant tout", "connexion", "complicite", "affinite"],
    "Fétichisme": ["fetich", "fétich", "pieds", "latex", "cuir", "nylon", "talons"],
    "Hard": ["hard", "extreme", "fist", "double"],
    "Papouilles": ["papouille", "tendresse", "caresse", "douceur", "sensuel", "massage"],
    "Pluralité": ["pluralite", "trio", "trouple", "plan a trois", "plan a 3", "melangisme"],
}

# ─── Browser profile directory ───
BROWSER_PROFILE_DIRNAME = ".boostrencontre"
BROWSER_PROFILE_SUBDIR = "browser_profiles"
