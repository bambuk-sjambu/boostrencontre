import asyncio
import logging
import os
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv
from ..constants import OPENAI_MODEL, OPENAI_MAX_TOKENS_MESSAGE
from .prompt_builder import (
    _get_recipient_context,
    _detect_desires,
    _desires_prompt_section,
    _select_approach_template,
    _build_base_prompt,
    build_system_message,
)
from .approach_templates import APPROACH_TEMPLATES

load_dotenv()

logger = logging.getLogger(__name__)

# Singleton AsyncOpenAI client
_client = None


def _get_client() -> AsyncOpenAI:
    """Get or create the singleton AsyncOpenAI client."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def _call_openai_with_retry(messages: list, max_tokens: int = 300, max_retries: int = 3) -> str:
    """Call OpenAI API with retry and exponential backoff."""
    client = _get_client()
    last_error = None
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + 0.5
                logger.warning(f"OpenAI call failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"OpenAI call failed after {max_retries} attempts: {e}")
    raise last_error


# --- Security: Safety filter for AI-generated messages ---
MAX_MESSAGE_LENGTH = 500  # Max chars for any generated message

# Patterns that indicate the AI broke character or generated garbage
_BAD_PATTERNS = [
    "je ne vois pas", "pas de message", "je n'ai pas vu",
    "pas de conversation", "je ne trouve pas", "aucun message",
    "je ne peux pas voir", "je n'arrive pas", "desole mais je",
    "désolé mais je", "en tant qu'ia", "en tant qu'assistant",
    "en tant que modele", "je suis un assistant", "je suis une ia",
    "openai", "chatgpt", "gpt-4", "gpt-3", "language model",
    "as an ai", "i'm an ai", "i cannot", "i can't",
    "je suis programme", "je suis un programme",
    "cette conversation est fictive", "ceci est un message genere",
    "je ne suis pas une vraie personne",
]


def _sanitize_prompt_input(text: str, max_len: int = 800) -> str:
    """Strip potential prompt injection markers from user-controlled text."""
    if len(text) > max_len:
        text = text[-max_len:]  # keep the most recent content
    text = text.replace('"""', '').replace("'''", "")
    text = re.sub(
        r'(?i)(ignore|forget|disregard)\s+(all\s+)?(previous|above|prior)\s+(instructions?|context|rules?)',
        '[filtre]', text
    )
    text = re.sub(
        r'(?i)(you are now|act as|pretend to be|your new role|tu es maintenant|agis comme)',
        '[filtre]', text
    )
    return text


def _sanitize_ai_message(text: str | None) -> str | None:
    """Filter and truncate AI-generated messages. Returns None if unsafe."""
    if not text:
        logger.warning("AI message rejected: empty or None")
        return None
    # Strip whitespace and quotes that AI sometimes wraps messages in
    text = text.strip().strip('"').strip("'").strip()
    if not text:
        logger.warning("AI message rejected: empty after stripping")
        return None
    # Truncate to max length
    if len(text) > MAX_MESSAGE_LENGTH:
        # Cut at last sentence boundary within limit
        truncated = text[:MAX_MESSAGE_LENGTH]
        last_period = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
        if last_period > MAX_MESSAGE_LENGTH // 2:
            text = truncated[:last_period + 1]
        else:
            text = truncated
        logger.info(f"AI message truncated to {len(text)} chars (max {MAX_MESSAGE_LENGTH})")
    # Check for bad patterns
    lower = text.lower()
    for bad in _BAD_PATTERNS:
        if bad in lower:
            logger.warning(f"AI message rejected: matched bad pattern '{bad}' in: {text[:100]}...")
            return None
    return text


# Who I am — used in all message generation
# Empty defaults: real values are loaded from the database at startup (see app.py lifespan)
MY_PROFILE = {
    "pseudo": "",
    "type": "",
    "age": "",
    "location": "",
    "description": "",
}

# Available message styles
STYLES = {
    "auto": (
        "Analyse le profil de la personne et choisis le ton le plus adapte parmi : "
        "romantique, humoristique, direct, intellectuel, aventurier, mysterieux ou complice. "
        "Adapte-toi a ce que la personne semble chercher d'apres sa bio et son type de profil. "
        "Si le profil est explicite sur ses envies, sois plus direct ; si c'est poetique ou discret, sois plus subtil."
    ),
    "romantique": (
        "Sois romantique, doux et attentionne. Montre un interet sincere pour la personne, "
        "pas juste pour son physique. Utilise des mots chaleureux, fais des compliments subtils "
        "sur sa personnalite ou ce qu'elle degage plutot que son apparence. "
        "Cree une atmosphere intime et bienveillante, comme si tu cherchais une vraie connexion emotionnelle. "
        "Evite les cliches type 'tu es la plus belle' — sois authentique et specifique."
    ),
    "direct_sexe": (
        "Sois direct et assume sur le desir, sans detour ni fausse pudeur. "
        "On est sur un site libertin entre adultes consentants — assume le contexte. "
        "Evoque le plaisir, l'attirance, les envies de maniere franche mais jamais vulgaire. "
        "Montre que tu sais ce que tu veux tout en restant respectueux et a l'ecoute. "
        "Le but est d'exciter la curiosite, pas de choquer. Pas de vocabulaire porno, mais un langage sensuel et affirme."
    ),
    "humoristique": (
        "Sois drole, decale et surprenant. Utilise l'humour pour briser la glace et creer "
        "une connivence immediate. Privilegie l'autodérision, les jeux de mots malins ou les "
        "references inattendues. L'objectif est de faire sourire ou rire des la premiere phrase. "
        "Evite l'humour lourd, les blagues de mec relou, ou les vannes sur le physique. "
        "Le ton doit rester leger et donne envie de repondre pour continuer l'echange fun."
    ),
    "intellectuel": (
        "Sois curieux, cultive et stimulant intellectuellement. Pose des questions qui font "
        "reflechir ou partage une reflexion originale en lien avec le profil de la personne. "
        "Montre de la culture sans etre pedant — c'est une conversation, pas une conference. "
        "Fais des liens entre ses centres d'interet et des sujets plus larges (philo, art, voyages, societe). "
        "L'objectif est de montrer que tu es quelqu'un avec qui on peut avoir des echanges profonds ET legers."
    ),
    "aventurier": (
        "Sois spontane, energique et tourne vers l'action. Propose une idee, une experience, "
        "un plan concret plutot que de rester dans les banalites. Montre que tu es quelqu'un "
        "qui vit des choses et qui aime decouvrir. Evoque des experiences passees ou des envies futures "
        "qui donnent envie de te suivre. Le message doit donner l'impression que la vie avec toi serait "
        "un enchainement de moments forts et de decouvertes."
    ),
    "mystérieux": (
        "Sois intrigant et enigmatique. Ne devoile pas tout, laisse planer un mystere qui "
        "donne envie d'en savoir plus. Utilise des phrases suggestives, des sous-entendus elegants, "
        "des formulations qui ouvrent l'imagination. Fais comprendre qu'il y a beaucoup a decouvrir "
        "sous la surface. Evite d'etre obscur ou confus — le mystere doit etre attirant, pas frustrant. "
        "L'objectif est que la personne ait ENVIE de te repondre pour en apprendre davantage."
    ),
    "complice": (
        "Sois chaleureux et familier, comme si vous vous connaissiez deja un peu. "
        "Cree une complicite immediate en trouvant un terrain commun ou en reagissant "
        "a un detail de son profil comme le ferait un ami proche. Utilise un ton decontracte, "
        "bienveillant et inclusif. Fais sentir que tu es quelqu'un de confiance avec qui "
        "on peut etre soi-meme sans filtre. Pas de distance formelle, mais pas non plus de familiarite forcee."
    ),
}


async def generate_first_message(profile_info: dict, style: str = "auto", approach_template: str = "") -> str:
    """Generate a personalized first message based on profile info and style."""

    name = profile_info.get("name", "")
    bio = profile_info.get("bio", "")
    age = profile_info.get("age", "")
    profile_type = profile_info.get("type", "")
    interests = profile_info.get("interests", [])
    location = profile_info.get("location", "")
    preferences = profile_info.get("preferences", "")

    style_instruction = STYLES.get(style, STYLES["auto"])

    # --- Adaptive context based on recipient type ---
    recipient_context = _get_recipient_context(profile_info)

    # --- Detect desires in bio ---
    desires = _detect_desires(bio)
    desires_section = _desires_prompt_section(desires)

    # --- Auto-select approach template if none provided and desires detected ---
    if not approach_template:
        auto_key = _select_approach_template(desires, profile_type)
        if auto_key and auto_key in APPROACH_TEMPLATES:
            approach_template = APPROACH_TEMPLATES[auto_key]["example"]

    # Adapt prompt based on whether we have bio info
    bio_section = ""
    if bio and len(bio) > 10:
        clean_bio = _sanitize_prompt_input(bio)
        bio_section = f"""
IMPORTANT : Voici ce que cette personne a ecrit dans sa presentation :
\"\"\"{clean_bio}\"\"\"
Tu DOIS faire reference a un element specifique de cette presentation dans ton message.
Montre que tu as lu leur profil attentivement."""
    else:
        bio_section = """
Pas de presentation disponible. Base-toi sur le pseudo et le type de profil."""

    prefs_section = ""
    if preferences and len(preferences) > 10:
        prefs_section = f"\nLeurs preferences/envies : {_sanitize_prompt_input(preferences)}"

    location_section = ""
    if location:
        location_section = f"\n- Localisation : {location}"

    approach_section = ""
    if approach_template:
        approach_section = f"""
APPROCHE A UTILISER : Tu dois t'inspirer de cette idee pour ton message (reformule avec tes mots, adapte au profil) :
\"\"\"{approach_template}\"\"\"
Integre cette approche naturellement dans ton message personnalise."""

    # --- Build system + user messages ---
    my = MY_PROFILE
    system_msg = build_system_message(my)

    # Recipient context block
    recipient_block = ""
    if recipient_context:
        recipient_block = f"\n--- CONTEXTE DESTINATAIRE ---\n{recipient_context}\n"

    user_prompt = f"""--- MISSION ---
Ecris un PREMIER message court et percutant (2-3 phrases max, 50 mots max) pour engager la conversation avec cette personne.

--- PROFIL DE LA PERSONNE ---
- Pseudo : {name}
- Type : {profile_type}
- Age : {age}{location_section}
- Interets : {', '.join(interests) if interests else 'non renseigne'}
{bio_section}{prefs_section}{desires_section}
{recipient_block}
--- STYLE ---
{style_instruction}
{approach_section}
--- SORTIE ---
Reponds UNIQUEMENT avec le message, rien d'autre. Pas de guillemets, pas de commentaire."""

    raw = await _call_openai_with_retry(
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=300,
    )
    return _sanitize_ai_message(raw)


async def generate_reply_message(
    sender_name: str,
    conversation_text: str,
    style: str = "auto",
    profile_info: dict = None,
    platform: str = "wyylde",
) -> str:
    """Generate a reply to an existing conversation.

    Integrates with the conversation manager to use stage-aware prompts
    and record messages in conversation_history.
    """
    from .conversation_manager import (
        get_conversation_stage, get_conversation_summary,
        record_message, detect_stage_transition,
    )

    style_instruction = STYLES.get(style, STYLES["auto"])
    my = MY_PROFILE

    # --- Conversation stage ---
    conv_state = await get_conversation_stage(platform, sender_name)
    stage_info = conv_state["stage_info"]
    stage_addon = stage_info["prompt_addon"]

    # --- Conversation history summary from DB ---
    history_summary = await get_conversation_summary(platform, sender_name)

    # --- Adaptive context based on recipient type ---
    recipient_context = ""
    if profile_info:
        recipient_context = _get_recipient_context(profile_info)

    # --- Detect desires in bio ---
    desires_section = ""
    if profile_info:
        bio = profile_info.get("bio", "")
        desires = _detect_desires(bio)
        desires_section = _desires_prompt_section(desires)

    # Determine tu/vous based on profile type
    profile_section = ""
    tutoiement = "Tutoie sauf si la personne vouvoie"
    if profile_info:
        ptype = profile_info.get("type", "")
        bio = profile_info.get("bio", "")
        age = profile_info.get("age", "")
        location = profile_info.get("location", "")
        profile_section = f"\nProfil de {sender_name} :"
        if ptype:
            profile_section += f"\n- Type : {ptype}"
        if age:
            profile_section += f"\n- Age : {age}"
        if location:
            profile_section += f"\n- Localisation : {location}"
        if bio and len(bio) > 10:
            profile_section += f"\n- Presentation : \"{bio[:500]}\""
        if "couple" in ptype.lower():
            tutoiement = "VOUVOIE (c'est un couple, dis 'vous', 'votre', etc.)"
        else:
            tutoiement = "TUTOIE (c'est une personne seule, dis 'tu', 'ton', etc.)"

    # --- Build system + user messages ---
    system_msg = build_system_message(my)

    # Recipient context block
    recipient_block = ""
    if recipient_context:
        recipient_block = f"\n--- CONTEXTE DESTINATAIRE ---\n{recipient_context}\n"

    # Stage and history context
    stage_block = f"\n--- ETAPE DE LA CONVERSATION ---\nEtape actuelle : {conv_state['stage']} ({stage_info['description']})\n{stage_addon}\n"
    history_block = ""
    if history_summary:
        history_block = f"\n--- HISTORIQUE PRECEDENT ---\n{history_summary}\n"

    user_prompt = f"""{profile_section}

--- CONVERSATION COMPLETE AVEC {sender_name.upper()} ---
\"\"\"
{_sanitize_prompt_input(conversation_text, max_len=3000)}
\"\"\"{desires_section}
{recipient_block}{stage_block}{history_block}
--- MISSION ---
ANALYSE la conversation ENTIERE ci-dessus pour comprendre :
1. Le contexte et le ton de l'echange (dragueur, amical, sexuel, curieux, taquin...)
2. Ce que {sender_name} cherche / ses envies explicites ou implicites
3. Les sujets deja abordes (ne les repete PAS, fais avancer la discussion)
4. Le DERNIER message de {sender_name} auquel tu dois repondre

Puis REPONDS DIRECTEMENT au dernier message de {sender_name}.
- Si {sender_name} pose une question -> REPONDS a cette question d'abord, puis eventuellement rebondis
- Si {sender_name} fait un commentaire -> rebondis dessus de maniere pertinente
- Si {sender_name} flirte ou est explicite -> assume le meme niveau d'intensite (on est entre adultes)

Ecris une reponse courte et pertinente (1-3 phrases, 50 mots max).

--- STYLE ---
{style_instruction}

--- REGLES SUPPLEMENTAIRES ---
1. C'est une conversation DEJA EN COURS — JAMAIS de 'Salut', 'Bonjour', 'Hey', 'Coucou' ou formule d'accueil
2. Sois coherent avec ce qui a DEJA ETE DIT — ne te repete pas, ne change pas de sujet sans raison
3. Montre que tu as compris ce que la personne veut ou ressent
4. Sois naturel, comme dans une vraie conversation entre adultes sur un chat
5. NE TERMINE PAS systematiquement par une question — parfois une reponse simple suffit
6. 1 emoji max (optionnel)
7. {tutoiement}
8. NE DIS JAMAIS que tu ne vois pas de message ou que tu n'as pas de contexte. Si le texte est confus, rebondis sur n'importe quel element.

--- CE QU'IL NE FAUT SURTOUT PAS FAIRE ---
- Repeter un sujet deja aborde dans la conversation (relis tout avant de repondre)
- Repondre par une question quand la personne attend une reponse concrete
- Enchainer question sur question sans jamais rien donner de toi
- Ecrire des phrases creuses type "c'est interessant" ou "je suis curieux d'en savoir plus"
- Etre trop poli ou formel — on est sur un site libertin, pas sur LinkedIn
- Ignorer le ton de la conversation (si c'est chaud, reste chaud ; si c'est fun, reste fun)

--- SORTIE ---
Reponds UNIQUEMENT avec le message, rien d'autre. Pas de guillemets, pas de commentaire."""

    reply = await _call_openai_with_retry(
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=300,
    )

    # Safety filter: reject bad AI outputs (expanded patterns + length limit)
    sanitized = _sanitize_ai_message(reply)

    # Record in conversation history and detect stage transition
    if sanitized:
        try:
            await record_message(platform, sender_name, "sent", sanitized, style=style)
            await detect_stage_transition(platform, sender_name, conversation_text)
        except Exception as e:
            logger.warning(f"Failed to record conversation history: {e}")

    return sanitized
