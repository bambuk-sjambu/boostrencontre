import copy

import pytest
from unittest.mock import patch, AsyncMock
from src.messaging.ai_messages import (
    generate_first_message, generate_reply_message, STYLES, MY_PROFILE,
    _sanitize_ai_message, MAX_MESSAGE_LENGTH,
)
from src.messaging.approach_templates import APPROACH_TEMPLATES

# Save original MY_PROFILE at import time so tests can restore it
_ORIGINAL_MY_PROFILE = copy.deepcopy(MY_PROFILE)


@pytest.fixture(autouse=True)
def _reset_my_profile():
    """Reset MY_PROFILE before each test to avoid cross-test pollution."""
    MY_PROFILE.clear()
    MY_PROFILE.update(copy.deepcopy(_ORIGINAL_MY_PROFILE))
    yield
    MY_PROFILE.clear()
    MY_PROFILE.update(copy.deepcopy(_ORIGINAL_MY_PROFILE))


# Helper: patch the internal _call_openai_with_retry to return a fixed string
def _patch_openai(return_value="Test"):
    return patch(
        "src.messaging.ai_messages._call_openai_with_retry",
        new_callable=AsyncMock,
        return_value=return_value,
    )


@pytest.fixture(autouse=True)
def _mock_conversation_manager():
    """Mock conversation_manager functions to avoid DB calls in messaging tests."""
    stage_result = {
        "stage": "accroche",
        "stage_info": {"description": "Premier contact", "max_turns": 1, "next": "interet", "prompt_addon": "C'est ton premier message."},
        "sent_count": 0, "received_count": 0, "total_turns": 0, "history": [],
    }
    patches = [
        patch("src.messaging.conversation_manager.get_conversation_stage", new_callable=AsyncMock, return_value=stage_result),
        patch("src.messaging.conversation_manager.get_conversation_summary", new_callable=AsyncMock, return_value=""),
        patch("src.messaging.conversation_manager.record_message", new_callable=AsyncMock),
        patch("src.messaging.conversation_manager.detect_stage_transition", new_callable=AsyncMock, return_value="accroche"),
    ]
    started = [p.start() for p in patches]
    yield
    for p in patches:
        p.stop()


def _get_prompt(mock_call):
    """Extract the full prompt text from the mock call args (system + user)."""
    msgs = mock_call.call_args[1]["messages"]
    return "\n".join(m["content"] for m in msgs)


# --- generate_first_message tests ---

@pytest.mark.asyncio
async def test_generate_first_message_with_profile():
    with _patch_openai("Salut Marie, j'ai vu que tu aimais la rando !") as mock_call:
        msg = await generate_first_message({
            "name": "Marie",
            "age": "28",
            "bio": "Fan de rando et de cuisine asiatique, on adore voyager ensemble",
            "type": "Couple F Bi",
            "interests": ["Randonnee", "Cuisine"],
        })

    assert isinstance(msg, str)
    assert len(msg) > 0
    prompt = _get_prompt(mock_call)
    assert MY_PROFILE["pseudo"] in prompt
    assert "Marie" in prompt
    assert "rando" in prompt


@pytest.mark.asyncio
async def test_generate_first_message_with_empty_profile():
    with _patch_openai("Salut, ton profil m'a intrigue !") as mock_call:
        msg = await generate_first_message({
            "name": "",
            "age": "",
            "bio": "",
            "interests": [],
        })

    assert isinstance(msg, str)
    assert len(msg) > 0


@pytest.mark.asyncio
async def test_generate_first_message_with_style():
    with _patch_openai("Test") as mock_call:
        await generate_first_message({"name": "Test"}, style="humoristique")

    prompt = _get_prompt(mock_call)
    assert "drole" in prompt.lower() or "humour" in prompt.lower()


@pytest.mark.asyncio
async def test_generate_first_message_with_couple_profile():
    """Couple profiles should trigger 'vous' in the prompt."""
    with _patch_openai("Bonjour !") as mock_call:
        await generate_first_message({
            "name": "CoupleFun",
            "type": "Couple",
            "bio": "Couple sympa et ouvert",
        })

    prompt = _get_prompt(mock_call)
    assert "Couple" in prompt
    assert "VOUVOIE" in prompt


@pytest.mark.asyncio
async def test_generate_first_message_solo_profile_tutoie():
    """Solo profiles (Homme/Femme) should trigger 'tu' in the prompt."""
    with _patch_openai("Hey !") as mock_call:
        await generate_first_message({
            "name": "Julie",
            "type": "Femme",
            "bio": "Coucou je suis Julie",
        })

    prompt = _get_prompt(mock_call)
    assert "TUTOIE" in prompt


@pytest.mark.asyncio
async def test_generate_first_message_invalid_style_falls_back():
    """Invalid style should fall back to 'auto'."""
    with _patch_openai("Salut !") as mock_call:
        msg = await generate_first_message({"name": "Test"}, style="nonexistent_style")
    assert isinstance(msg, str)
    prompt = _get_prompt(mock_call)
    assert "adapte" in prompt.lower() or "choisis" in prompt.lower()


@pytest.mark.asyncio
async def test_generate_first_message_with_approach_template():
    """approach_template should be included in the prompt."""
    with _patch_openai("Yo !") as mock_call:
        await generate_first_message(
            {"name": "Test", "bio": "Profil test"},
            approach_template="On organise des soirees thematiques"
        )

    prompt = _get_prompt(mock_call)
    assert "soirees thematiques" in prompt.lower()
    assert "APPROCHE" in prompt


@pytest.mark.asyncio
async def test_each_style_affects_prompt():
    """Each style should produce a different style_instruction in the prompt."""
    prompts = {}
    for style_name in STYLES:
        with _patch_openai("Msg") as mock_call:
            await generate_first_message({"name": "Test"}, style=style_name)
        prompts[style_name] = _get_prompt(mock_call)

    unique_prompts = set(prompts.values())
    assert len(unique_prompts) >= len(STYLES) - 1, "Most styles should produce distinct prompts"


# --- generate_reply_message tests ---

@pytest.mark.asyncio
async def test_generate_reply_message():
    with _patch_openai("Merci pour ton message, ca fait plaisir !") as mock_call:
        msg = await generate_reply_message(
            sender_name="SportifNice",
            conversation_text="Salut, ton profil m'interesse !",
            style="auto"
        )

    assert isinstance(msg, str)
    assert len(msg) > 0
    prompt = _get_prompt(mock_call)
    assert "SportifNice" in prompt
    assert MY_PROFILE["pseudo"] in prompt


@pytest.mark.asyncio
async def test_generate_reply_with_profile_info():
    """Reply generation with profile_info should include profile details in prompt."""
    with _patch_openai("Cool !") as mock_call:
        await generate_reply_message(
            "Marie",
            "Salut comment vas-tu ?",
            style="romantique",
            profile_info={"type": "Couple F Bi", "bio": "On adore voyager", "age": "30"}
        )

    prompt = _get_prompt(mock_call)
    assert "VOUVOIE" in prompt
    assert "voyager" in prompt


@pytest.mark.asyncio
async def test_generate_reply_with_long_conversation():
    """Very long conversation text should be truncated in prompt."""
    long_conv = "Blablabla message de test. " * 500
    with _patch_openai("D'accord !") as mock_call:
        msg = await generate_reply_message("Alice", long_conv, style="auto")

    assert isinstance(msg, str)
    prompt = _get_prompt(mock_call)
    assert len(prompt) < len(long_conv)


@pytest.mark.asyncio
async def test_generate_reply_safety_filter_blocks_bad_reply():
    """Replies containing bad patterns should return None."""
    bad_replies = [
        "Je ne vois pas de message",
        "Il n'y a pas de message visible",
        "Pas de conversation ici",
        "Je ne trouve pas le message",
        "Aucun message dans cette discussion",
        "Je ne peux pas voir ce que tu dis",
        "Je n'arrive pas a lire la conversation",
        "Desole mais je ne comprends pas",
        "Désolé mais je ne sais pas quoi repondre",
    ]
    for bad in bad_replies:
        with _patch_openai(bad):
            msg = await generate_reply_message("X", "Test", style="auto")
        assert msg is None, f"Should have filtered: '{bad}'"


@pytest.mark.asyncio
async def test_generate_reply_safety_filter_passes_good_reply():
    """Normal replies should pass the safety filter."""
    with _patch_openai("Super, on se capte bientot ?"):
        msg = await generate_reply_message("Bob", "Salut, ca va ?", style="auto")
    assert msg is not None
    assert "capte" in msg


# --- STYLES dict tests ---

def test_all_styles_exist():
    expected = ["auto", "romantique", "direct_sexe", "humoristique", "intellectuel", "aventurier", "mystérieux", "complice"]
    for s in expected:
        assert s in STYLES, f"Style '{s}' missing from STYLES dict"


def test_styles_are_detailed():
    """Each style instruction should be at least 100 chars (enriched, not just a short sentence)."""
    for name, instruction in STYLES.items():
        assert len(instruction) >= 100, (
            f"Style '{name}' is too short ({len(instruction)} chars). "
            f"Should be >= 100 chars for quality prompting."
        )


def test_styles_values_are_nonempty_strings():
    for style_name, instruction in STYLES.items():
        assert isinstance(instruction, str), f"STYLES['{style_name}'] should be a string"
        assert len(instruction) > 10, f"STYLES['{style_name}'] instruction is too short"


# --- MY_PROFILE tests ---

def test_my_profile_has_required_fields():
    """MY_PROFILE must have all required keys (values are empty by default, loaded from DB at startup)."""
    required = ["pseudo", "type", "age", "location", "description"]
    for field in required:
        assert field in MY_PROFILE, f"MY_PROFILE missing '{field}'"


# --- Approach templates tests ---

def test_approach_templates_count():
    assert len(APPROACH_TEMPLATES) == 13, f"Expected 13 templates, got {len(APPROACH_TEMPLATES)}"


def test_approach_templates_structure():
    """Each template must have name, description, and example."""
    for key, tmpl in APPROACH_TEMPLATES.items():
        assert "name" in tmpl, f"Template '{key}' missing 'name'"
        assert "description" in tmpl, f"Template '{key}' missing 'description'"
        assert "example" in tmpl, f"Template '{key}' missing 'example'"
        assert len(tmpl["name"]) > 0, f"Template '{key}' has empty name"
        assert len(tmpl["description"]) > 20, f"Template '{key}' description too short"
        assert len(tmpl["example"]) > 20, f"Template '{key}' example too short"


def test_approach_templates_keys():
    """Check that all expected template keys exist."""
    expected_keys = [
        "complicite_intellectuelle", "aventure_sensuelle", "humour_decale",
        "connexion_emotionnelle", "proposition_directe", "mystere_attirant",
        "terrain_commun", "compliment_precis", "taquin_seducteur",
        "experience_partagee", "curiosite_sincere", "confiance_assumee",
        "douceur_sensuelle",
    ]
    for key in expected_keys:
        assert key in APPROACH_TEMPLATES, f"Template '{key}' missing from APPROACH_TEMPLATES"


@pytest.mark.asyncio
async def test_generate_first_message_with_real_approach_template():
    """Using a real approach template example should include it in the prompt."""
    template_text = APPROACH_TEMPLATES["aventure_sensuelle"]["example"]
    with _patch_openai("Test avec template") as mock_call:
        await generate_first_message(
            {"name": "Luna", "type": "Femme", "bio": "Curieuse de tout"},
            style="auto",
            approach_template=template_text,
        )

    prompt = _get_prompt(mock_call)
    assert "magnetique" in prompt.lower()
    assert "APPROCHE" in prompt


# --- Security: AI message sanitizer ---

def test_sanitize_filters_ai_identity_leak():
    """Messages revealing AI identity must be blocked."""
    assert _sanitize_ai_message("En tant qu'IA, je peux t'aider") is None
    assert _sanitize_ai_message("Je suis un assistant virtuel") is None
    assert _sanitize_ai_message("This is generated by ChatGPT") is None
    assert _sanitize_ai_message("As an AI language model") is None


def test_sanitize_truncates_long_messages():
    """Messages exceeding MAX_MESSAGE_LENGTH are truncated."""
    long_msg = "Salut! " * 200  # way over 500 chars
    result = _sanitize_ai_message(long_msg)
    assert result is not None
    assert len(result) <= MAX_MESSAGE_LENGTH


def test_sanitize_strips_quotes():
    """Wrapping quotes from AI output are stripped."""
    assert _sanitize_ai_message('"Hello there"') == "Hello there"
    assert _sanitize_ai_message("'Bonjour!'") == "Bonjour!"


def test_sanitize_returns_none_for_empty():
    assert _sanitize_ai_message("") is None
    assert _sanitize_ai_message(None) is None
    assert _sanitize_ai_message("   ") is None


def test_sanitize_passes_normal_message():
    msg = "Ton profil m'a intrigue, t'as l'air cool!"
    assert _sanitize_ai_message(msg) == msg


@pytest.mark.asyncio
async def test_first_message_also_filtered():
    """generate_first_message should also filter bad patterns."""
    with _patch_openai("En tant qu'IA, bonjour"):
        msg = await generate_first_message({"name": "Test"})
    assert msg is None
