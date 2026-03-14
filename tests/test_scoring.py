"""Tests for the profile scoring system."""

import json
import pytest
import aiosqlite

from src.scoring import (
    score_profile,
    save_score,
    _score_desires,
    _score_completeness,
    _score_activity,
    _score_type_compat,
    _score_geography,
    _suggest_style,
    _normalize_type,
)
from src.database import DB_PATH, init_db


# ---------------------------------------------------------------------------
# _normalize_type
# ---------------------------------------------------------------------------


def test_normalize_type_homme_bi():
    assert _normalize_type("Homme Bi") == "homme_bi"


def test_normalize_type_couple_f_bi():
    assert _normalize_type("Couple F Bi") == "couple_f_bi"


def test_normalize_type_femme_hetero():
    assert _normalize_type("Femme hétéro") == "femme_hetero"


def test_normalize_type_unknown():
    assert _normalize_type("") == "unknown"
    assert _normalize_type("Robot") == "unknown"


# ---------------------------------------------------------------------------
# _score_desires
# ---------------------------------------------------------------------------


def test_score_desires_matching():
    bio = "On adore le gang bang et le BDSM, on cherche des gens ouverts"
    pts, details = _score_desires(bio, ["Gang bang", "BDSM", "Feeling"])
    assert pts >= 10
    assert "Gang bang" in details["common"]
    assert "BDSM" in details["common"]


def test_score_desires_no_match():
    bio = "Simple profil sans envies particulieres"
    pts, details = _score_desires(bio, ["Gang bang"])
    assert pts == 0
    assert details["common"] == []


def test_score_desires_empty_bio():
    pts, details = _score_desires("", ["Gang bang"])
    assert pts == 0


def test_score_desires_no_my_desires():
    """When no personal desires, all detected count as positive."""
    bio = "On aime le BDSM et les soirees gang bang"
    pts, details = _score_desires(bio, None)
    assert pts >= 10
    assert len(details["common"]) >= 2


def test_score_desires_detected_but_no_common():
    """Target has desires but none match ours."""
    bio = "On adore le BDSM et le bondage"
    pts, details = _score_desires(bio, ["Gang bang", "Feeling"])
    assert pts == 5  # small bonus for having desires at all
    assert details["common"] == []


# ---------------------------------------------------------------------------
# _score_completeness
# ---------------------------------------------------------------------------


def test_completeness_full_profile():
    profile = {
        "bio": "Une longue description de plus de cinquante caracteres qui decrit bien le profil",
        "type": "Couple F Bi",
        "age": "35",
        "photos": True,
    }
    pts, details = _score_completeness(profile)
    assert pts == 20
    assert details["bio"] == "complete"


def test_completeness_empty_profile():
    pts, details = _score_completeness({})
    assert pts == 0
    assert details["bio"] == "missing"
    assert details["identity"] == "missing"


def test_completeness_partial():
    profile = {
        "bio": "Courte bio ici",
        "type": "Homme Bi",
    }
    pts, details = _score_completeness(profile)
    assert 5 <= pts <= 12
    assert details["bio"] == "partial"


# ---------------------------------------------------------------------------
# _score_activity
# ---------------------------------------------------------------------------


def test_activity_online():
    pts, d = _score_activity({"status": "En ligne"})
    assert pts == 15
    assert d["activity"] == "online"


def test_activity_today():
    pts, d = _score_activity({"last_seen": "Aujourd'hui 14:30"})
    assert pts == 12


def test_activity_yesterday():
    pts, d = _score_activity({"last_seen": "Hier 20:00"})
    assert pts == 10


def test_activity_old():
    pts, d = _score_activity({"last_seen": "il y a 10 jours"})
    assert pts == 0
    assert d["activity"] == "inactive"


def test_activity_unknown():
    pts, d = _score_activity({})
    assert pts == 5
    assert d["activity"] == "unknown"


# ---------------------------------------------------------------------------
# _score_type_compat
# ---------------------------------------------------------------------------


def test_type_compat_homme_bi_couple_f_bi():
    pts, d = _score_type_compat("Homme Bi", "Couple F Bi")
    assert pts == 20
    assert d["match"] == "excellent"


def test_type_compat_homme_hetero_homme_hetero():
    pts, d = _score_type_compat("Homme hétéro", "Homme hétéro")
    assert pts == 0


def test_type_compat_unknown():
    pts, d = _score_type_compat("", "Couple F Bi")
    assert pts == 10  # default for unknown


def test_type_compat_homme_bi_femme_bi():
    pts, d = _score_type_compat("Homme Bi", "Femme Bi")
    assert pts == 20


# ---------------------------------------------------------------------------
# _score_geography
# ---------------------------------------------------------------------------


def test_geo_same_city():
    pts, d = _score_geography("Paris", "Paris")
    assert pts == 15


def test_geo_contains():
    pts, d = _score_geography("Paris", "Paris 15e")
    assert pts == 15


def test_geo_same_region():
    pts, d = _score_geography("Paris", "Versailles 78")
    assert pts == 8  # same Ile-de-France region


def test_geo_different():
    pts, d = _score_geography("Marseille", "Lille")
    assert pts == 0


def test_geo_unknown():
    pts, d = _score_geography("", "Paris")
    assert pts == 5


# ---------------------------------------------------------------------------
# _suggest_style
# ---------------------------------------------------------------------------


def test_suggest_style_explicit_desires():
    target = {"bio": "on aime le bdsm", "type": "Couple F Bi"}
    details = {"desires": {"detected": ["BDSM"], "common": ["BDSM"]}}
    assert _suggest_style(target, 70, details) == "direct_sexe"


def test_suggest_style_couple():
    target = {"bio": "profil sympa", "type": "Couple hétéro"}
    details = {"desires": {"detected": [], "common": []}}
    assert _suggest_style(target, 60, details) == "complice"


def test_suggest_style_fun_bio():
    target = {"bio": "on adore rire et s'amuser", "type": "Femme Bi"}
    details = {"desires": {"detected": [], "common": []}}
    assert _suggest_style(target, 50, details) == "humoristique"


def test_suggest_style_high_score():
    target = {"bio": "profil standard", "type": "Femme hétéro"}
    details = {"desires": {"detected": [], "common": []}}
    assert _suggest_style(target, 80, details) == "romantique"


def test_suggest_style_default():
    target = {"bio": "", "type": ""}
    details = {"desires": {"detected": [], "common": []}}
    assert _suggest_style(target, 30, details) == "auto"


# ---------------------------------------------------------------------------
# score_profile (integration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_profile_complete():
    """A complete and compatible profile should score high."""
    target = {
        "name": "TestCouple",
        "type": "Couple F Bi",
        "age": "32",
        "bio": "Couple ouvert et curieux, on aime les soirees gang bang et le feeling avant tout. Venez nous decouvrir!",
        "location": "Paris",
        "status": "En ligne",
        "photos": True,
    }
    my = {
        "pseudo": "MonPseudo",
        "type": "Homme Bi",
        "age": "35",
        "location": "Paris",
        "description": "Amateur de gang bang et feeling",
        "pratiques": "Gang bang, Feeling, Echangisme",
    }
    result = await score_profile(target, my_profile=my)
    assert result["total"] >= 70
    assert result["grade"] in ("A", "B")
    assert result["recommendation"] == "message"
    assert "details" in result
    assert "suggested_style" in result


@pytest.mark.asyncio
async def test_score_profile_empty():
    """An empty profile should score low."""
    target = {"name": "Empty", "type": "", "bio": "", "age": ""}
    my = {
        "pseudo": "Test",
        "type": "Homme Bi",
        "age": "35",
        "location": "Paris",
        "description": "",
    }
    result = await score_profile(target, my_profile=my)
    assert result["total"] <= 40
    assert result["grade"] in ("C", "D")


@pytest.mark.asyncio
async def test_score_profile_grade_boundaries():
    """Verify grade boundaries: A>=80, B>=60, C>=40, D<40."""
    base = {
        "name": "Test",
        "type": "Couple F Bi",
        "bio": "Gang bang BDSM soumission domination fetichisme cuir exhibition voyeur feeling connexion papouille tendresse trio pluralite echange echangisme",
        "age": "30",
        "location": "Paris",
        "status": "En ligne",
        "photos": True,
        "preferences": "tout",
    }
    my = {
        "pseudo": "Test",
        "type": "Homme Bi",
        "location": "Paris",
        "description": "gang bang bdsm feeling",
        "pratiques": "Gang bang, BDSM, Feeling",
    }
    result = await score_profile(base, my_profile=my)
    # With max everything, this should be A
    assert result["total"] >= 80
    assert result["grade"] == "A"


# ---------------------------------------------------------------------------
# save_score (DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_score_and_retrieve():
    """Test that scores are persisted to the database."""
    await init_db()

    score_result = {
        "total": 75,
        "grade": "B",
        "details": {"desires": {"detected": ["BDSM"]}},
        "recommendation": "message",
        "suggested_style": "direct_sexe",
    }
    await save_score("wyylde", "TestUser", score_result, target_type="Couple F Bi")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM profile_scores WHERE platform = ? AND target_name = ?",
            ("wyylde", "TestUser"),
        )
        row = await cursor.fetchone()

    assert row is not None
    # row columns: id, platform, target_name, target_type, score, grade, recommendation, suggested_style, details, scored_at
    assert row[4] == 75  # score
    assert row[5] == "B"  # grade
    assert row[6] == "message"  # recommendation


@pytest.mark.asyncio
async def test_save_score_upsert():
    """Test that saving the same profile updates the existing score."""
    await init_db()

    score1 = {
        "total": 50, "grade": "C",
        "details": {}, "recommendation": "like_only", "suggested_style": "auto",
    }
    await save_score("wyylde", "UpsertUser", score1, target_type="Femme Bi")

    score2 = {
        "total": 80, "grade": "A",
        "details": {}, "recommendation": "message", "suggested_style": "romantique",
    }
    await save_score("wyylde", "UpsertUser", score2, target_type="Femme Bi")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT score, grade FROM profile_scores WHERE platform = ? AND target_name = ?",
            ("wyylde", "UpsertUser"),
        )
        row = await cursor.fetchone()

    assert row[0] == 80
    assert row[1] == "A"
