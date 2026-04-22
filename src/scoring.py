"""
Profile scoring — compute compatibility between our profile and a target.

Scores a target profile on 100 points across 5 dimensions:
  1. Desire matching (0-30)
  2. Profile completeness (0-20)
  3. Recent activity (0-15)
  4. Type compatibility (0-20)
  5. Geography (0-15)
"""

import json
import logging
import re

from .constants import DESIRE_KEYWORDS
from .messaging.prompt_builder import _detect_desires

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type compatibility matrix
# ---------------------------------------------------------------------------
# Key: (our_type_category, target_type_category) -> score 0-20
# Categories: homme, femme, couple, couple_f_bi, couple_m_bi, couple_hetero

_TYPE_COMPAT: dict[tuple[str, str], int] = {
    # Homme Bi targeting
    ("homme_bi", "couple_f_bi"): 20,
    ("homme_bi", "couple_m_bi"): 18,
    ("homme_bi", "couple_hetero"): 15,
    ("homme_bi", "femme_bi"): 20,
    ("homme_bi", "femme_hetero"): 18,
    ("homme_bi", "homme_bi"): 16,
    ("homme_bi", "homme_hetero"): 5,
    ("homme_bi", "travesti"): 14,
    # Homme hetero targeting
    ("homme_hetero", "couple_f_bi"): 18,
    ("homme_hetero", "couple_hetero"): 16,
    ("homme_hetero", "couple_m_bi"): 8,
    ("homme_hetero", "femme_bi"): 20,
    ("homme_hetero", "femme_hetero"): 20,
    ("homme_hetero", "homme_bi"): 0,
    ("homme_hetero", "homme_hetero"): 0,
    ("homme_hetero", "travesti"): 5,
    # Femme Bi targeting
    ("femme_bi", "couple_f_bi"): 20,
    ("femme_bi", "couple_hetero"): 16,
    ("femme_bi", "couple_m_bi"): 14,
    ("femme_bi", "femme_bi"): 20,
    ("femme_bi", "femme_hetero"): 10,
    ("femme_bi", "homme_bi"): 18,
    ("femme_bi", "homme_hetero"): 18,
    ("femme_bi", "travesti"): 12,
    # Couple targeting
    ("couple", "couple_f_bi"): 20,
    ("couple", "couple_hetero"): 18,
    ("couple", "couple_m_bi"): 16,
    ("couple", "femme_bi"): 20,
    ("couple", "femme_hetero"): 16,
    ("couple", "homme_bi"): 16,
    ("couple", "homme_hetero"): 12,
    ("couple", "travesti"): 10,
}


def _normalize_type(raw: str) -> str:
    """Normalize a profile type string to a lookup key."""
    t = raw.strip().lower()
    if "couple" in t and "f bi" in t:
        return "couple_f_bi"
    if "couple" in t and "m bi" in t:
        return "couple_m_bi"
    if "couple" in t and ("hétéro" in t or "hetero" in t):
        return "couple_hetero"
    if "couple" in t:
        return "couple"
    if "femme" in t and "bi" in t:
        return "femme_bi"
    if "femme" in t:
        return "femme_hetero"
    if "homme" in t and "bi" in t:
        return "homme_bi"
    if "homme" in t:
        return "homme_hetero"
    if "travesti" in t:
        return "travesti"
    return "unknown"


def _score_desires(target_bio: str, my_desires: list[str] | None = None) -> tuple[int, dict]:
    """Score desire matching (0-30 points)."""
    detected = _detect_desires(target_bio or "")
    if not detected:
        return 0, {"detected": [], "common": [], "points": 0}

    if my_desires:
        common = [d for d in detected if d in my_desires]
    else:
        # If no explicit desires, treat all detected as positive signal
        common = detected

    # 10 points for first match, +5 per additional, capped at 30
    if not common:
        return 5, {"detected": detected, "common": [], "points": 5}
    points = min(10 + (len(common) - 1) * 5, 30)
    return points, {"detected": detected, "common": common, "points": points}


def _score_completeness(target: dict) -> tuple[int, dict]:
    """Score profile completeness (0-20 points)."""
    points = 0
    detail = {}

    bio = target.get("bio", "") or ""
    if bio and len(bio) > 50:
        points += 10
        detail["bio"] = "complete"
    elif bio and len(bio) > 10:
        points += 5
        detail["bio"] = "partial"
    else:
        detail["bio"] = "missing"

    # Type and age present
    has_type = bool(target.get("type", ""))
    has_age = bool(target.get("age", ""))
    if has_type and has_age:
        points += 5
        detail["identity"] = "complete"
    elif has_type or has_age:
        points += 2
        detail["identity"] = "partial"
    else:
        detail["identity"] = "missing"

    # Photos or preferences
    has_photos = bool(target.get("photos")) or bool(target.get("photo"))
    has_prefs = bool(target.get("preferences", ""))
    if has_photos or has_prefs:
        points += 5
        detail["extras"] = "present"
    else:
        detail["extras"] = "missing"

    return points, detail


def _score_activity(target: dict) -> tuple[int, dict]:
    """Score recent activity (0-15 points)."""
    status = (target.get("status", "") or target.get("online", "") or "").lower()
    last_seen = (target.get("last_seen", "") or "").lower()

    if "en ligne" in status or "online" in status or status == "online":
        return 15, {"activity": "online"}

    if last_seen:
        if "aujourd" in last_seen or "heure" in last_seen or "minute" in last_seen:
            return 12, {"activity": "today"}
        if "hier" in last_seen or "yesterday" in last_seen:
            return 10, {"activity": "yesterday"}
        # Check for "X jours" pattern
        match = re.search(r"(\d+)\s*jour", last_seen)
        if match:
            days = int(match.group(1))
            if days <= 3:
                return 8, {"activity": f"{days}_days"}
            if days <= 7:
                return 4, {"activity": f"{days}_days"}
            return 0, {"activity": "inactive"}

    # No activity info — give neutral score
    return 5, {"activity": "unknown"}


def _score_type_compat(my_type: str, target_type: str) -> tuple[int, dict]:
    """Score type compatibility (0-20 points)."""
    my_norm = _normalize_type(my_type)
    target_norm = _normalize_type(target_type)

    if my_norm == "unknown" or target_norm == "unknown":
        return 10, {"my_type": my_norm, "target_type": target_norm, "match": "unknown"}

    # Direct lookup
    score = _TYPE_COMPAT.get((my_norm, target_norm))
    if score is not None:
        quality = "excellent" if score >= 18 else "good" if score >= 12 else "low"
        return score, {"my_type": my_norm, "target_type": target_norm, "match": quality}

    # For couple subtypes as our type, try generic couple
    if my_norm.startswith("couple"):
        score = _TYPE_COMPAT.get(("couple", target_norm))
        if score is not None:
            return score, {"my_type": my_norm, "target_type": target_norm, "match": "generic_couple"}

    return 10, {"my_type": my_norm, "target_type": target_norm, "match": "default"}


def _score_geography(my_location: str, target_location: str) -> tuple[int, dict]:
    """Score geographical proximity (0-15 points)."""
    my_loc = (my_location or "").strip().lower()
    target_loc = (target_location or "").strip().lower()

    if not my_loc or not target_loc:
        return 5, {"geo": "unknown"}

    # Exact city match
    if my_loc == target_loc:
        return 15, {"geo": "same_city"}

    # Check if one location contains the other (e.g. "Paris" in "Paris 15e")
    if my_loc in target_loc or target_loc in my_loc:
        return 15, {"geo": "same_city"}

    # Same department (French dept codes, e.g. "75" in both)
    my_dept = re.search(r"\b(\d{2,3})\b", my_loc)
    target_dept = re.search(r"\b(\d{2,3})\b", target_loc)
    if my_dept and target_dept and my_dept.group(1) == target_dept.group(1):
        return 10, {"geo": "same_dept"}

    # Same region — check if they share a region keyword
    regions = {
        "ile-de-france": ["paris", "idf", "ile de france", "ile-de-france", "92", "93", "94", "95", "77", "78", "91"],
        "paca": ["marseille", "nice", "toulon", "paca", "provence", "13", "06", "83", "84"],
        "auvergne-rhone-alpes": ["lyon", "grenoble", "saint-etienne", "69", "38", "42"],
        "occitanie": ["toulouse", "montpellier", "31", "34"],
        "nouvelle-aquitaine": ["bordeaux", "33"],
        "bretagne": ["rennes", "brest", "35", "29"],
        "normandie": ["rouen", "caen", "76", "14"],
    }
    my_region = None
    target_region = None
    for region, keywords in regions.items():
        for kw in keywords:
            if kw in my_loc:
                my_region = region
            if kw in target_loc:
                target_region = region
    if my_region and target_region and my_region == target_region:
        return 8, {"geo": "same_region"}

    return 0, {"geo": "different"}


def _suggest_style(target: dict, score: int, details: dict) -> str:
    """Suggest the best message style based on profile analysis."""
    bio = (target.get("bio", "") or "").lower()
    target_type = (target.get("type", "") or "").lower()
    desire_details = details.get("desires", {})
    detected = desire_details.get("detected", [])

    # Explicit sexual desires -> direct_sexe
    explicit_desires = {"Gang bang", "BDSM", "Hard", "Fétichisme", "Exhibition"}
    if any(d in explicit_desires for d in detected):
        return "direct_sexe"

    # Long/intellectual bio -> intellectuel
    if bio and len(bio) > 200:
        intellectual_words = ["lecture", "philosophie", "art", "culture", "voyage", "cinema", "musique", "theatre"]
        if any(w in bio for w in intellectual_words):
            return "intellectuel"

    # Fun/light profile -> humoristique
    fun_words = ["rire", "humour", "drole", "fun", "rigol", "blague", "deconner"]
    if any(w in bio for w in fun_words):
        return "humoristique"

    # Couple -> complice
    if "couple" in target_type:
        return "complice"

    # Feeling/tenderness -> romantique
    soft_desires = {"Feeling", "Papouilles"}
    if any(d in soft_desires for d in detected):
        return "romantique"

    # High score = more investment -> romantique
    if score >= 75:
        return "romantique"

    return "auto"


async def score_profile(
    target_profile: dict,
    my_profile: dict | None = None,
    platform: str | None = None,
) -> dict:
    """Score a target profile on 100 points.

    Args:
        target_profile: Target's profile data (name, type, bio, age, location, etc.)
        my_profile: Our profile. If None, uses MY_PROFILE from ai_messages.
        platform: Platform name. If "tinder", uses the Tinder-adapted scorer
            (passions + distance + photos + bio) instead of the Wyylde one.

    Returns:
        Dict with total, grade, details, recommendation, suggested_style.
    """
    if my_profile is None:
        from .messaging.ai_messages import MY_PROFILE
        my_profile = MY_PROFILE

    if platform == "tinder":
        return _score_tinder_profile(target_profile, my_profile)

    details = {}
    total = 0

    # 1. Desires (0-30)
    my_desires_text = my_profile.get("pratiques", "") or my_profile.get("description", "") or ""
    my_desires = _detect_desires(my_desires_text)
    pts, d = _score_desires(target_profile.get("bio", ""), my_desires)
    total += pts
    details["desires"] = d

    # 2. Completeness (0-20)
    pts, d = _score_completeness(target_profile)
    total += pts
    details["completeness"] = d

    # 3. Activity (0-15)
    pts, d = _score_activity(target_profile)
    total += pts
    details["activity"] = d

    # 4. Type compatibility (0-20)
    my_type = my_profile.get("type", "")
    target_type = target_profile.get("type", "")
    pts, d = _score_type_compat(my_type, target_type)
    total += pts
    details["type_compat"] = d

    # 5. Geography (0-15)
    my_loc = my_profile.get("location", "")
    target_loc = target_profile.get("location", "")
    pts, d = _score_geography(my_loc, target_loc)
    total += pts
    details["geography"] = d

    grade = "A" if total >= 80 else "B" if total >= 60 else "C" if total >= 40 else "D"
    recommendation = "message" if total >= 60 else "like_only" if total >= 40 else "skip"
    suggested = _suggest_style(target_profile, total, details)

    return {
        "total": total,
        "grade": grade,
        "details": details,
        "recommendation": recommendation,
        "suggested_style": suggested,
    }


def _parse_distance_km(distance_text: str) -> int | None:
    """Extract kilometers from a Tinder distance string.

    Examples:
      "5 km away" -> 5
      "less than a mile away" -> 1 (~1.6km, round down)
      "15 miles away" -> 24 (15 * 1.6)
    Returns None if unparseable.
    """
    if not distance_text:
        return None
    s = distance_text.lower().strip()
    m = re.search(r"(\d+)\s*km", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*mile", s)
    if m:
        return int(int(m.group(1)) * 1.6)
    if "less than" in s:
        return 1
    return None


def _score_tinder_passions(target_passions: list[str], my_interests: list[str]) -> tuple[int, dict]:
    """Score passions overlap (0-30 points).

    If we don't have explicit interests, any non-empty passion list gets a
    baseline (profile effort signal).
    """
    target = [p.strip().lower() for p in target_passions or [] if p]
    if not target:
        return 0, {"count": 0, "overlap": [], "points": 0}

    if my_interests:
        mine = [i.strip().lower() for i in my_interests if i]
        overlap = [p for p in target if p in mine]
        points = min(len(overlap) * 10, 30)
        if not overlap:
            points = 5  # they listed passions, we just don't match — still effort
        return points, {"count": len(target), "overlap": overlap, "points": points}

    # No explicit interests on our side: effort signal only
    points = min(10 + (len(target) - 1) * 2, 20)
    return points, {"count": len(target), "overlap": [], "points": points}


def _score_tinder_photos(photo_count: int) -> tuple[int, dict]:
    """Score profile photo investment (0-25 points).

    5 points per photo, capped at 5 photos. Tinder allows up to 9; 5+ is
    a strong completeness signal.
    """
    n = max(0, int(photo_count or 0))
    points = min(n * 5, 25)
    return points, {"photos": n, "points": points}


def _score_tinder_bio(bio: str) -> tuple[int, dict]:
    """Score bio length as an effort proxy (0-15 points)."""
    bio = (bio or "").strip()
    if not bio:
        return 0, {"bio": "missing", "points": 0}
    if len(bio) < 30:
        return 3, {"bio": "minimal", "points": 3}
    if len(bio) < 100:
        return 8, {"bio": "short", "points": 8}
    if len(bio) < 300:
        return 12, {"bio": "good", "points": 12}
    return 15, {"bio": "rich", "points": 15}


def _score_tinder_distance(distance_text: str) -> tuple[int, dict]:
    """Score proximity (0-20 points).

    Tighter radius than Wyylde per T1-B: Siem Reap is small. <5km = 20,
    <15km = 12, <30km = 5, else 0. Unknown = neutral 5.
    """
    km = _parse_distance_km(distance_text)
    if km is None:
        return 5, {"distance": "unknown", "points": 5}
    if km <= 5:
        return 20, {"distance": f"{km}km", "points": 20}
    if km <= 15:
        return 12, {"distance": f"{km}km", "points": 12}
    if km <= 30:
        return 5, {"distance": f"{km}km", "points": 5}
    return 0, {"distance": f"{km}km", "points": 0}


def _score_tinder_age(target_age: str, my_age_range: tuple[int, int] | None) -> tuple[int, dict]:
    """Score age fit (0-10 points).

    If caller doesn't supply an age range, returns neutral 5.
    """
    try:
        age = int(target_age) if target_age else None
    except (ValueError, TypeError):
        age = None
    if age is None or not my_age_range:
        return 5, {"age": "unknown", "points": 5}
    low, high = my_age_range
    if low <= age <= high:
        return 10, {"age": age, "points": 10, "match": "in_range"}
    if low - 5 <= age <= high + 5:
        return 5, {"age": age, "points": 5, "match": "near_range"}
    return 0, {"age": age, "points": 0, "match": "out_of_range"}


def _suggest_tinder_style(target: dict, total: int, details: dict) -> str:
    """Style hint for Tinder: simpler than Wyylde — no desire taxonomy."""
    bio = (target.get("bio", "") or "").lower()
    passions_detail = details.get("passions", {})
    overlap = passions_detail.get("overlap", [])

    fun_words = ["laugh", "humor", "funny", "joke", "fun", "rigol", "drôle", "drole"]
    if any(w in bio for w in fun_words):
        return "humoristique"

    travel_words = ["travel", "voyage", "backpack", "digital nomad", "expat"]
    if any(w in bio for w in travel_words) or "travel" in overlap:
        return "aventurier"

    intellectual_words = ["book", "read", "philosophy", "art", "museum", "film"]
    if any(w in bio for w in intellectual_words):
        return "intellectuel"

    if total >= 75:
        return "romantique"
    return "auto"


def _score_tinder_profile(target: dict, my_profile: dict) -> dict:
    """Tinder-adapted 100-point score.

    Breakdown: passions (30) + photos (25) + distance (20) + bio (15) + age (10).
    """
    details = {}
    total = 0

    my_interests = my_profile.get("interests", []) or my_profile.get("passions", []) or []

    pts, d = _score_tinder_passions(target.get("passions", []) or [], my_interests)
    total += pts
    details["passions"] = d

    pts, d = _score_tinder_photos(target.get("photo_count", 0))
    total += pts
    details["photos"] = d

    pts, d = _score_tinder_distance(target.get("distance", "") or "")
    total += pts
    details["distance"] = d

    pts, d = _score_tinder_bio(target.get("bio", "") or "")
    total += pts
    details["bio"] = d

    my_age_range = my_profile.get("age_range")
    pts, d = _score_tinder_age(target.get("age", "") or "", my_age_range)
    total += pts
    details["age"] = d

    grade = "A" if total >= 80 else "B" if total >= 60 else "C" if total >= 40 else "D"
    recommendation = "message" if total >= 60 else "like_only" if total >= 40 else "skip"
    suggested = _suggest_tinder_style(target, total, details)

    return {
        "total": total,
        "grade": grade,
        "details": details,
        "recommendation": recommendation,
        "suggested_style": suggested,
    }


async def save_score(platform: str, target_name: str, score_result: dict,
                     target_type: str = "") -> None:
    """Persist a score to the database."""
    from .database import get_db
    async with await get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO profile_scores
               (platform, target_name, target_type, score, grade,
                recommendation, suggested_style, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                platform,
                target_name,
                target_type,
                score_result["total"],
                score_result["grade"],
                score_result["recommendation"],
                score_result["suggested_style"],
                json.dumps(score_result["details"]),
            ),
        )
        await db.commit()
