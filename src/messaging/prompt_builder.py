"""
Prompt builder helpers for adaptive AI messages.

Extracts prompt construction logic from ai_messages.py to keep that module
under the 500-line limit. All functions here are pure (no I/O, no async).
"""

import re
from ..constants import DESIRE_KEYWORDS
from ..models.profile_schema import build_profile_prompt_text


# ---------------------------------------------------------------------------
# Recipient context by type
# ---------------------------------------------------------------------------

_RECIPIENT_CONTEXTS = {
    "femme": (
        "Tu t'adresses a une femme. Sois respectueux de son espace, "
        "montre ton interet sans etre insistant. Valorise sa personnalite "
        "avant tout. Evite les compliments physiques directs au premier message."
    ),
    "homme": (
        "Tu t'adresses a un homme. Sois direct et naturel, comme entre potes "
        "qui se decouvrent. Pas besoin de tourner autour du pot, montre ce "
        "que tu cherches avec franchise et humour."
    ),
    "couple": (
        "Tu t'adresses a un couple. Utilise le vouvoiement. Montre que tu "
        "respectes leur dynamique a deux. Propose une energie complementaire, "
        "pas une intrusion. Evoque la complicite et le partage."
    ),
    "couple_f_bi": (
        "Tu t'adresses a un couple. Utilise le vouvoiement. Montre que tu "
        "respectes leur dynamique a deux. Propose une energie complementaire, "
        "pas une intrusion. Evoque la complicite et le partage. "
        "Ce couple inclut une femme bisexuelle. Tu peux evoquer la complicite "
        "feminine si c'est pertinent."
    ),
}


def _get_recipient_context(profile_info: dict) -> str:
    """Return adaptive prompt text based on the recipient's type.

    Args:
        profile_info: Dict with at least a ``type`` key (e.g. "Femme Bi",
            "Couple F Bi", "Homme hetero").

    Returns:
        A prompt paragraph tailored to the recipient type, or an empty
        string if the type is unknown.
    """
    raw_type = (profile_info.get("type") or "").strip().lower()

    if not raw_type:
        return ""

    # Couple F Bi (most specific) must be checked before generic "couple"
    if "couple" in raw_type and "f bi" in raw_type:
        return _RECIPIENT_CONTEXTS["couple_f_bi"]
    if "couple" in raw_type:
        return _RECIPIENT_CONTEXTS["couple"]
    if "femme" in raw_type:
        return _RECIPIENT_CONTEXTS["femme"]
    if "homme" in raw_type:
        return _RECIPIENT_CONTEXTS["homme"]

    return ""


# ---------------------------------------------------------------------------
# Desire detection in bios
# ---------------------------------------------------------------------------

def _detect_desires(bio_text: str) -> list[str]:
    """Scan a bio for desire-related keywords.

    Args:
        bio_text: Free-text bio/presentation of the recipient.

    Returns:
        List of matching desire category names (e.g. ``["BDSM", "Feeling"]``).
        Empty list when nothing matches or bio is empty.
    """
    if not bio_text:
        return []

    lower = bio_text.lower()
    detected: list[str] = []

    for desire, keywords in DESIRE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                detected.append(desire)
                break  # one match per category is enough

    return detected


def _desires_prompt_section(desires: list[str]) -> str:
    """Build a prompt snippet from detected desires (or empty string)."""
    if not desires:
        return ""
    return (
        f"\nSes envies detectees : {', '.join(desires)}. "
        "Fais-y subtilement reference dans ton message si c'est naturel."
    )


# ---------------------------------------------------------------------------
# Approach template selection
# ---------------------------------------------------------------------------

# Maps desire categories to the most relevant approach template key.
_DESIRE_TO_TEMPLATE = {
    "Gang bang": "proposition_directe",
    "Échangisme": "experience_partagee",
    "BDSM": "confiance_assumee",
    "Exhibition": "mystere_attirant",
    "Feeling": "connexion_emotionnelle",
    "Fétichisme": "taquin_seducteur",
    "Hard": "proposition_directe",
    "Papouilles": "douceur_sensuelle",
    "Pluralité": "aventure_sensuelle",
}

# Recipient-type fallback when no desire is detected
_TYPE_TO_TEMPLATE = {
    "femme": "complicite_intellectuelle",
    "homme": "humour_decale",
    "couple": "terrain_commun",
    "couple_f_bi": "terrain_commun",
}


def _select_approach_template(
    desires: list[str],
    recipient_type: str,
) -> str | None:
    """Choose the best approach template key given desires and type.

    Args:
        desires: List of detected desire names (from ``_detect_desires``).
        recipient_type: Raw type string from profile_info.

    Returns:
        An approach template key (str) or ``None`` when no mapping applies.
    """
    from .approach_templates import APPROACH_TEMPLATES

    # If desires detected, pick the template for the first matching desire
    for desire in desires:
        key = _DESIRE_TO_TEMPLATE.get(desire)
        if key and key in APPROACH_TEMPLATES:
            return key

    # Fallback: choose template based on recipient type
    raw_type = (recipient_type or "").strip().lower()
    for type_key, template_key in _TYPE_TO_TEMPLATE.items():
        if type_key in raw_type and template_key in APPROACH_TEMPLATES:
            return template_key

    return None


# ---------------------------------------------------------------------------
# Base prompt builder (shared between first-message and reply)
# ---------------------------------------------------------------------------

def _build_identity_block(my_profile: dict) -> str:
    """Build the 'who you are' section using build_profile_prompt_text."""
    profile_text = build_profile_prompt_text(my_profile)
    return (
        f"Tu es {my_profile.get('pseudo', '???')} sur Wyylde "
        f"(site de rencontres libertines entre adultes consentants).\n\n"
        f"--- TON PROFIL ---\n{profile_text}"
    )


def _build_rules_block() -> str:
    """Return the strict rules section shared by all prompts."""
    return """--- REGLES STRICTES ---
1. Sois naturel, comme un vrai humain qui ecrit sur un chat — pas un robot, pas un dragueur lourd
2. Le message DOIT etre personnalise : reference un element CONCRET du profil (bio, pseudo, interet)
3. Pose UNE question ouverte OU fais UN commentaire engageant — pas les deux
4. 1 emoji max (et c'est optionnel)
5. Si c'est un Couple : VOUVOIE (dites 'vous', 'votre', 'vos')
6. Si c'est un Homme ou une Femme seul(e) : TUTOIE (dis 'tu', 'ton', 'ta')"""


def _build_antipatterns_block() -> str:
    """Return the anti-patterns section shared by all prompts."""
    return """--- CE QU'IL NE FAUT SURTOUT PAS FAIRE ---
- "Hey", "Salut ca va ?", "Coucou" ou toute accroche generique
- "J'ai vu ton profil et..." — tout le monde dit ca, c'est invisible
- Complimenter le physique ("tu es belle/beau") — trop banal et impersonnel
- Ecrire un pave — 2-3 phrases max, sinon c'est trop
- Enchainer les questions — une seule suffit
- Utiliser des formules toutes faites type "on a plein de choses en commun"
- Mettre des smileys partout ou des points de suspension a chaque phrase"""


def _build_base_prompt(my_profile: dict, style_text: str) -> str:
    """Assemble the identity + rules + anti-patterns + style sections.

    This is the common foundation used by both ``generate_first_message``
    and ``generate_reply_message``.

    Returns:
        A multi-section prompt string (no trailing newline).
    """
    identity = _build_identity_block(my_profile)
    rules = _build_rules_block()
    anti = _build_antipatterns_block()

    return f"""{identity}

--- STYLE ---
{style_text}

{rules}

{anti}"""


def build_system_message(my_profile: dict) -> str:
    """Build the permanent system message (identity + rules).

    Separated from the user message so OpenAI can treat it as persistent
    context across the conversation.
    """
    identity = _build_identity_block(my_profile)
    rules = _build_rules_block()
    anti = _build_antipatterns_block()

    return f"""{identity}

{rules}

{anti}

--- SORTIE ---
Reponds UNIQUEMENT avec le message, rien d'autre. Pas de guillemets, pas de commentaire."""
