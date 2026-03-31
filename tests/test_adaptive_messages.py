"""Tests for adaptive AI message generation (recipient context, desires, prompt builder)."""

import copy

import pytest
from unittest.mock import patch, AsyncMock

from src.messaging.prompt_builder import (
    _get_recipient_context,
    _detect_desires,
    _desires_prompt_section,
    _select_approach_template,
    _build_base_prompt,
    build_system_message,
    _build_identity_block,
)
from src.messaging.ai_messages import (
    generate_first_message,
    generate_reply_message,
    MY_PROFILE,
    STYLES,
)

# Save original MY_PROFILE at import time so tests can restore it
_ORIGINAL_MY_PROFILE = copy.deepcopy(MY_PROFILE)


@pytest.fixture(autouse=True)
def _reset_my_profile():
    """Reset MY_PROFILE before each test to avoid cross-test pollution."""
    MY_PROFILE.clear()
    MY_PROFILE.update(copy.deepcopy(_ORIGINAL_MY_PROFILE))
    # Give it some values so prompts are meaningful
    MY_PROFILE.update({
        "pseudo": "TestUser",
        "type": "Homme",
        "age": "35",
        "location": "Paris",
        "description": "Curieux et aventurier",
    })
    yield
    MY_PROFILE.clear()
    MY_PROFILE.update(copy.deepcopy(_ORIGINAL_MY_PROFILE))


def _patch_openai(return_value="Test message"):
    return patch(
        "src.messaging.ai_messages._call_openai_with_retry",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _get_all_prompt_text(mock_call):
    """Concatenate all message contents from the mock call."""
    msgs = mock_call.call_args[1]["messages"]
    return "\n".join(m["content"] for m in msgs)


def _get_messages(mock_call):
    """Return the raw messages list from the mock call."""
    return mock_call.call_args[1]["messages"]


# =========================================================================
# _get_recipient_context
# =========================================================================

class TestGetRecipientContext:

    def test_femme(self):
        ctx = _get_recipient_context({"type": "Femme hetero"})
        assert "femme" in ctx.lower()
        assert "respectueux" in ctx
        assert "compliments physiques" in ctx

    def test_femme_bi(self):
        ctx = _get_recipient_context({"type": "Femme Bi"})
        assert "femme" in ctx.lower()
        assert "respectueux" in ctx

    def test_homme(self):
        ctx = _get_recipient_context({"type": "Homme hetero"})
        assert "homme" in ctx.lower()
        assert "direct" in ctx
        assert "franchise" in ctx

    def test_homme_bi(self):
        ctx = _get_recipient_context({"type": "Homme Bi"})
        assert "homme" in ctx.lower()

    def test_couple_hetero(self):
        ctx = _get_recipient_context({"type": "Couple hetero"})
        assert "couple" in ctx.lower()
        assert "vouvoiement" in ctx
        assert "dynamique a deux" in ctx

    def test_couple_f_bi(self):
        ctx = _get_recipient_context({"type": "Couple F Bi"})
        assert "couple" in ctx.lower()
        assert "vouvoiement" in ctx
        assert "femme bisexuelle" in ctx
        assert "complicite feminine" in ctx

    def test_couple_m_bi(self):
        """Couple M Bi should get the generic couple context (not F Bi)."""
        ctx = _get_recipient_context({"type": "Couple M Bi"})
        assert "couple" in ctx.lower()
        assert "femme bisexuelle" not in ctx

    def test_unknown_type(self):
        ctx = _get_recipient_context({"type": "Travesti"})
        assert ctx == ""

    def test_empty_type(self):
        ctx = _get_recipient_context({"type": ""})
        assert ctx == ""

    def test_missing_type_key(self):
        ctx = _get_recipient_context({})
        assert ctx == ""


# =========================================================================
# _detect_desires
# =========================================================================

class TestDetectDesires:

    def test_single_desire(self):
        desires = _detect_desires("On adore l'echangisme et les rencontres")
        assert "Échangisme" in desires

    def test_multiple_desires(self):
        desires = _detect_desires("Fan de BDSM, domination et un peu de voyeurisme")
        assert "BDSM" in desires
        assert "Exhibition" in desires

    def test_feeling_desire(self):
        desires = _detect_desires("Feeling avant tout, on cherche la connexion")
        assert "Feeling" in desires

    def test_papouilles(self):
        desires = _detect_desires("On aime la tendresse et les massages sensuels")
        assert "Papouilles" in desires

    def test_pluralite(self):
        desires = _detect_desires("Ouvert au trio et au melangisme")
        assert "Pluralité" in desires

    def test_fetichisme(self):
        desires = _detect_desires("Amateur de latex et cuir")
        assert "Fétichisme" in desires

    def test_no_desires(self):
        desires = _detect_desires("J'aime la nature et les balades")
        assert desires == []

    def test_empty_bio(self):
        desires = _detect_desires("")
        assert desires == []

    def test_none_bio(self):
        desires = _detect_desires(None)
        assert desires == []

    def test_case_insensitive(self):
        desires = _detect_desires("Je suis dans le BDSM depuis longtemps")
        assert "BDSM" in desires

    def test_no_duplicates(self):
        """Each category should appear at most once even with multiple keyword matches."""
        desires = _detect_desires("bdsm domination soumission bondage")
        assert desires.count("BDSM") == 1


# =========================================================================
# _desires_prompt_section
# =========================================================================

class TestDesiresPromptSection:

    def test_with_desires(self):
        section = _desires_prompt_section(["BDSM", "Feeling"])
        assert "BDSM" in section
        assert "Feeling" in section
        assert "envies detectees" in section.lower()
        assert "subtilement" in section

    def test_empty_desires(self):
        section = _desires_prompt_section([])
        assert section == ""


# =========================================================================
# _select_approach_template
# =========================================================================

class TestSelectApproachTemplate:

    def test_with_bdsm_desire(self):
        key = _select_approach_template(["BDSM"], "Femme")
        assert key == "confiance_assumee"

    def test_with_feeling_desire(self):
        key = _select_approach_template(["Feeling"], "Couple")
        assert key == "connexion_emotionnelle"

    def test_with_papouilles_desire(self):
        key = _select_approach_template(["Papouilles"], "Femme")
        assert key == "douceur_sensuelle"

    def test_no_desires_falls_back_to_type(self):
        key = _select_approach_template([], "Femme")
        assert key == "complicite_intellectuelle"

    def test_no_desires_no_type(self):
        key = _select_approach_template([], "")
        assert key is None

    def test_first_desire_wins(self):
        """When multiple desires, the first one's template is selected."""
        key = _select_approach_template(["Exhibition", "BDSM"], "Homme")
        assert key == "mystere_attirant"  # Exhibition maps to this


# =========================================================================
# _build_base_prompt
# =========================================================================

class TestBuildBasePrompt:

    def test_contains_identity(self):
        prompt = _build_base_prompt(MY_PROFILE, "style test")
        assert "TestUser" in prompt
        assert "Wyylde" in prompt

    def test_contains_style(self):
        prompt = _build_base_prompt(MY_PROFILE, "Sois romantique")
        assert "Sois romantique" in prompt

    def test_contains_rules(self):
        prompt = _build_base_prompt(MY_PROFILE, "style")
        assert "REGLES STRICTES" in prompt
        assert "VOUVOIE" in prompt
        assert "TUTOIE" in prompt

    def test_contains_antipatterns(self):
        prompt = _build_base_prompt(MY_PROFILE, "style")
        assert "NE FAUT SURTOUT PAS" in prompt
        assert "generique" in prompt

    def test_uses_build_profile_prompt_text(self):
        """Should include profile categories from build_profile_prompt_text."""
        MY_PROFILE["passions"] = "Lecture et voyages"
        prompt = _build_base_prompt(MY_PROFILE, "style")
        assert "Lecture et voyages" in prompt


# =========================================================================
# build_system_message
# =========================================================================

class TestBuildSystemMessage:

    def test_contains_identity(self):
        msg = build_system_message(MY_PROFILE)
        assert "TestUser" in msg

    def test_contains_rules(self):
        msg = build_system_message(MY_PROFILE)
        assert "REGLES STRICTES" in msg

    def test_contains_output_instruction(self):
        msg = build_system_message(MY_PROFILE)
        assert "SORTIE" in msg
        assert "guillemets" in msg


# =========================================================================
# Integration: generate_first_message uses adaptive context
# =========================================================================

class TestFirstMessageAdaptive:

    @pytest.mark.asyncio
    async def test_femme_context_in_prompt(self):
        with _patch_openai("Hello!") as mock_call:
            await generate_first_message({
                "name": "Julie",
                "type": "Femme Bi",
                "bio": "Curieuse de tout",
            })
        text = _get_all_prompt_text(mock_call)
        assert "respectueux" in text or "femme" in text.lower()

    @pytest.mark.asyncio
    async def test_couple_f_bi_context_in_prompt(self):
        with _patch_openai("Bonjour!") as mock_call:
            await generate_first_message({
                "name": "CoupleFun",
                "type": "Couple F Bi",
                "bio": "On adore le feeling",
            })
        text = _get_all_prompt_text(mock_call)
        assert "femme bisexuelle" in text

    @pytest.mark.asyncio
    async def test_desires_detected_in_prompt(self):
        with _patch_openai("Hey!") as mock_call:
            await generate_first_message({
                "name": "Luna",
                "type": "Femme",
                "bio": "J'adore le BDSM et la domination, feeling avant tout",
            })
        text = _get_all_prompt_text(mock_call)
        assert "envies detectees" in text.lower()
        assert "BDSM" in text

    @pytest.mark.asyncio
    async def test_auto_approach_template_from_desires(self):
        """When no approach_template is given but desires are detected, one is auto-selected."""
        with _patch_openai("Yo!") as mock_call:
            await generate_first_message({
                "name": "Alex",
                "type": "Homme",
                "bio": "Fan de tendresse et massage sensuel",
            })
        text = _get_all_prompt_text(mock_call)
        # Papouilles -> douceur_sensuelle template
        assert "APPROCHE" in text

    @pytest.mark.asyncio
    async def test_system_and_user_messages_separated(self):
        """The OpenAI call should have both system and user roles."""
        with _patch_openai("Salut!") as mock_call:
            await generate_first_message({
                "name": "Test",
                "type": "Femme",
                "bio": "Hello",
            })
        msgs = _get_messages(mock_call)
        roles = [m["role"] for m in msgs]
        assert "system" in roles
        assert "user" in roles

    @pytest.mark.asyncio
    async def test_no_desires_type_fallback_approach_section(self):
        """When bio has no desires but type is known, APPROCHE section uses type fallback."""
        with _patch_openai("Coucou!") as mock_call:
            await generate_first_message({
                "name": "Marie",
                "type": "Femme",
                "bio": "J'aime les balades en foret",
            })
        text = _get_all_prompt_text(mock_call)
        assert "APPROCHE" in text

    @pytest.mark.asyncio
    async def test_no_desires_no_type_no_approach_section(self):
        """When bio has no desires and no type, no APPROCHE section."""
        with _patch_openai("Coucou!") as mock_call:
            await generate_first_message({
                "name": "Marie",
                "type": "",
                "bio": "J'aime les balades en foret",
            })
        text = _get_all_prompt_text(mock_call)
        assert "APPROCHE" not in text


# =========================================================================
# Integration: generate_reply_message uses adaptive context
# =========================================================================

class TestReplyMessageAdaptive:

    @pytest.mark.asyncio
    async def test_recipient_context_in_reply(self):
        with _patch_openai("Super!") as mock_call:
            await generate_reply_message(
                "Julie",
                "Salut, ca va ?",
                profile_info={"type": "Femme Bi", "bio": "Curieuse"},
            )
        text = _get_all_prompt_text(mock_call)
        # Femme context should appear
        assert "femme" in text.lower()

    @pytest.mark.asyncio
    async def test_desires_in_reply(self):
        with _patch_openai("Cool!") as mock_call:
            await generate_reply_message(
                "CoupleX",
                "On adore discuter",
                profile_info={"type": "Couple hetero", "bio": "Echangisme et feeling"},
            )
        text = _get_all_prompt_text(mock_call)
        assert "envies detectees" in text.lower()

    @pytest.mark.asyncio
    async def test_reply_system_user_separation(self):
        with _patch_openai("Ok!") as mock_call:
            await generate_reply_message(
                "Bob",
                "Hello",
                profile_info={"type": "Homme", "bio": "Sportif"},
            )
        msgs = _get_messages(mock_call)
        roles = [m["role"] for m in msgs]
        assert "system" in roles
        assert "user" in roles

    @pytest.mark.asyncio
    async def test_reply_without_profile_info(self):
        """Reply without profile_info should still work (no adaptive context)."""
        with _patch_openai("D'accord!") as mock_call:
            msg = await generate_reply_message("Bob", "Salut")
        assert msg is not None
