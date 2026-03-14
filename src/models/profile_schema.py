"""
Profile schema — 10 categories + identity fields.

Defines the structure of enriched user profiles used for AI message generation.
Each category maps to a free-text field that the user fills via /profile.
"""

import html
import re
from typing import Any

# ---------------------------------------------------------------------------
# Profile categories (10 thematic blocks)
# ---------------------------------------------------------------------------

PROFILE_CATEGORIES: dict[str, dict[str, Any]] = {
    "passions": {
        "label": "Passions & hobbies",
        "placeholder": "Lecture, cuisine, voyages...",
        "max_length": 500,
    },
    "pratiques": {
        "label": "Pratiques & experiences",
        "placeholder": "Echangisme, BDSM...",
        "max_length": 500,
    },
    "personnalite": {
        "label": "Personnalite",
        "placeholder": "Curieux, drole, attentionne...",
        "max_length": 500,
    },
    "physique": {
        "label": "Description physique",
        "placeholder": "Grand, brun, sportif...",
        "max_length": 300,
    },
    "etudes_metier": {
        "label": "Etudes & metier",
        "placeholder": "Ingenieur, artiste...",
        "max_length": 300,
    },
    "voyages": {
        "label": "Voyages",
        "placeholder": "Asie, Amerique du Sud...",
        "max_length": 300,
    },
    "musique_culture": {
        "label": "Musique & culture",
        "placeholder": "Jazz, cinema d'auteur...",
        "max_length": 300,
    },
    "sport": {
        "label": "Sport & bien-etre",
        "placeholder": "Yoga, course, natation...",
        "max_length": 300,
    },
    "humour": {
        "label": "Humour & references",
        "placeholder": "Humour noir, Kaamelott...",
        "max_length": 300,
    },
    "valeurs": {
        "label": "Valeurs",
        "placeholder": "Respect, liberte, authenticite...",
        "max_length": 300,
    },
}

# ---------------------------------------------------------------------------
# Identity fields (core user info)
# ---------------------------------------------------------------------------

IDENTITY_FIELDS: dict[str, dict[str, Any]] = {
    "pseudo": {
        "label": "Pseudo",
        "required": True,
        "max_length": 50,
        "placeholder": "Ton pseudo sur le site",
    },
    "type": {
        "label": "Type",
        "required": True,
        "max_length": 50,
        "placeholder": "Homme, Femme, Couple...",
    },
    "age": {
        "label": "Age",
        "required": True,
        "max_length": 20,
        "placeholder": "35",
    },
    "location": {
        "label": "Localisation",
        "required": True,
        "max_length": 100,
        "placeholder": "Paris, Lyon...",
    },
    "description": {
        "label": "Description generale",
        "required": True,
        "max_length": 1000,
        "placeholder": "Presentation libre...",
    },
}

# ---------------------------------------------------------------------------
# All field keys (useful for iteration)
# ---------------------------------------------------------------------------

ALL_IDENTITY_KEYS = list(IDENTITY_FIELDS.keys())
ALL_CATEGORY_KEYS = list(PROFILE_CATEGORIES.keys())
ALL_PROFILE_KEYS = ALL_IDENTITY_KEYS + ALL_CATEGORY_KEYS


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------

def _sanitize_text(value: str) -> str:
    """Strip leading/trailing whitespace and escape HTML entities."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    # Remove null bytes and control characters (keep newlines and tabs)
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    # Escape HTML to prevent XSS
    value = html.escape(value, quote=True)
    return value


def _truncate(value: str, max_length: int) -> str:
    """Truncate string to max_length."""
    if len(value) > max_length:
        return value[:max_length]
    return value


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ProfileValidationError(Exception):
    """Raised when profile data fails validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Profile validation failed: {'; '.join(errors)}")


def validate_profile(data: dict, strict: bool = False) -> dict:
    """
    Validate and sanitize profile data.

    Args:
        data: Raw profile data dict.
        strict: If True, raise ProfileValidationError on missing required fields.
                If False (default), skip missing fields silently.

    Returns:
        Cleaned profile data dict with only recognized keys,
        sanitized text, and enforced max_length.

    Raises:
        ProfileValidationError: When strict=True and required fields are missing.
    """
    cleaned: dict[str, str] = {}
    errors: list[str] = []

    # -- Identity fields --
    for key, spec in IDENTITY_FIELDS.items():
        raw = data.get(key, "")
        value = _sanitize_text(str(raw) if raw is not None else "")
        value = _truncate(value, spec["max_length"])

        if strict and spec.get("required") and not value:
            errors.append(f"Champ requis manquant : {spec.get('label', key)}")

        if value:
            cleaned[key] = value

    # -- Category fields --
    for key, spec in PROFILE_CATEGORIES.items():
        raw = data.get(key, "")
        value = _sanitize_text(str(raw) if raw is not None else "")
        value = _truncate(value, spec["max_length"])

        if value:
            cleaned[key] = value

    if strict and errors:
        raise ProfileValidationError(errors)

    return cleaned


# ---------------------------------------------------------------------------
# Default profile (empty template)
# ---------------------------------------------------------------------------

def get_default_profile() -> dict[str, str]:
    """Return a profile dict with all keys set to empty strings."""
    return {key: "" for key in ALL_PROFILE_KEYS}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_profile_prompt_text(profile: dict) -> str:
    """
    Build a text block from the profile for inclusion in AI prompts.

    Only includes non-empty fields. Formatted for readability in a system prompt.

    Example output:
        Pseudo: JohnDoe
        Type: Homme
        Age: 35
        Passions & hobbies: Lecture, voyages, cuisine
        ...
    """
    lines: list[str] = []

    # Identity first
    for key, spec in IDENTITY_FIELDS.items():
        value = profile.get(key, "").strip()
        if value:
            lines.append(f"{spec['label']}: {value}")

    # Then categories
    for key, spec in PROFILE_CATEGORIES.items():
        value = profile.get(key, "").strip()
        if value:
            lines.append(f"{spec['label']}: {value}")

    if not lines:
        return "(Profil non renseigne)"

    return "\n".join(lines)
