"""User profile routes: get/update profile, enrich with AI, extract from platform."""

import json
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from openai import AsyncOpenAI
from pathlib import Path

from .. import bot_engine
from ..database import get_db, dict_factory
from ..constants import OPENAI_MODEL, OPENAI_MAX_TOKENS_ENRICH

logger = logging.getLogger(__name__)

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/profile", response_class=HTMLResponse, include_in_schema=False)
async def profile_page(request: Request):
    return templates.TemplateResponse(request, "profile.html")


@router.get("/api/user-profile")
async def get_user_profile():
    """Get the user profile data for the profile page."""
    from ..messaging.ai_messages import MY_PROFILE
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT * FROM activity_log WHERE action IN ('message', 'reply') ORDER BY created_at DESC LIMIT 50"
        )
        messages = await cursor.fetchall()
    return {"profile": MY_PROFILE, "messages_sent": messages}


@router.post("/api/user-profile")
async def update_user_profile(request: Request):
    """Update user profile with identity fields and categories."""
    data = await request.json()
    from ..messaging import ai_messages
    for field in ("pseudo", "type", "age", "location"):
        if field in data and len(str(data[field])) > 100:
            return JSONResponse(status_code=400, content={"error": f"{field}_too_long"})
    if "description" in data and len(str(data["description"])) > 2000:
        return JSONResponse(status_code=400, content={"error": "description_too_long"})
    for field in ("pseudo", "type", "age", "location", "description"):
        if field in data:
            ai_messages.MY_PROFILE[field] = str(data[field]).strip()
    if "categories" in data:
        ai_messages.MY_PROFILE["categories"] = data["categories"]

    async with await get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_profile (id, data) VALUES (1, ?)",
            (json.dumps(ai_messages.MY_PROFILE, ensure_ascii=False),)
        )
        await db.commit()

    return {"status": "saved", "profile": ai_messages.MY_PROFILE}


@router.post("/api/user-profile/enrich")
async def enrich_user_profile(request: Request):
    """Use AI to enrich/fill profile categories from sent messages and current data."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    from ..messaging import ai_messages

    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT message_sent FROM activity_log WHERE action IN ('message', 'reply') AND message_sent IS NOT NULL ORDER BY created_at DESC LIMIT 30"
        )
        rows = await cursor.fetchall()
    sent_texts = "\n".join(r["message_sent"] for r in rows if r["message_sent"])

    current_cats = data.get("categories", {})
    cats_summary = "\n".join(f"- {k}: {v}" for k, v in current_cats.items() if v)

    prompt = f"""Analyse ces informations sur un utilisateur de site de rencontres et enrichis ses categories de profil.

Profil actuel :
- Pseudo : {data.get('pseudo', '')}
- Type : {data.get('type', '')}
- Age : {data.get('age', '')}
- Location : {data.get('location', '')}
- Description : {data.get('description', '')}

Categories deja remplies :
{cats_summary if cats_summary else '(aucune)'}

Messages envoyes par l'utilisateur (pour deduire sa personnalite, ses gouts, etc.) :
\"\"\"{sent_texts[:3000]}\"\"\"

Pour chaque categorie ci-dessous, propose un contenu enrichi (garde ce qui existe deja et ajoute des elements deduits des messages).
Reponds en JSON avec exactement ces cles : passions, pratiques, personnalite, physique, etudes_metier, voyages, musique_culture, sport, humour, valeurs.
Chaque valeur est une chaine de texte courte (1-2 phrases max). Si tu n'as pas d'info, laisse la valeur existante ou vide.
Reponds UNIQUEMENT avec le JSON, rien d'autre."""

    try:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=OPENAI_MAX_TOKENS_ENRICH,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        enriched_cats = json.loads(raw)

        for key, val in enriched_cats.items():
            if key in current_cats:
                if not current_cats[key].strip() and val:
                    current_cats[key] = val
                elif current_cats[key].strip() and val and len(val) > len(current_cats[key]):
                    current_cats[key] = val

        for field in ("pseudo", "type", "age", "location", "description"):
            if field in data:
                ai_messages.MY_PROFILE[field] = data[field]
        ai_messages.MY_PROFILE["categories"] = current_cats

        async with await get_db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO user_profile (id, data) VALUES (1, ?)",
                (json.dumps(ai_messages.MY_PROFILE, ensure_ascii=False),)
            )
            await db.commit()

        return {"status": "enriched", "profile": ai_messages.MY_PROFILE}
    except Exception as e:
        logger.error(f"Error enriching profile: {e}", exc_info=True)
        return {"status": "error", "message": "internal_error"}


@router.get("/api/my-profile/{platform}")
async def my_profile(platform: str):
    """Extract own profile description and sent messages from the platform."""
    session = bot_engine.browser_sessions.get(platform)
    if not session:
        return JSONResponse(status_code=400, content={"error": "not_connected"})
    page = session["platform"].page
    import asyncio as aio

    results = {}

    # Get member ID from settings or DB (configurable, not hardcoded)
    member_id = os.getenv("WYYLDE_MEMBER_ID", "")
    if not member_id:
        async with await get_db() as db:
            db.row_factory = dict_factory
            cursor = await db.execute("SELECT data FROM user_profile WHERE id = 1")
            row = await cursor.fetchone()
            if row:
                profile_data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                member_id = profile_data.get("member_id", "")

    if not member_id:
        return {"error": "no_member_id", "message": "Set WYYLDE_MEMBER_ID env var or add member_id to your profile."}

    await page.goto(f"https://app.wyylde.com/fr-fr/member/{member_id}", timeout=30000, wait_until="domcontentloaded")
    await aio.sleep(4)

    results["profile"] = await page.evaluate("""() => {
        const data = {};
        const nameBtn = document.querySelector('button.max-w-full.font-poppins');
        data.name = nameBtn ? nameBtn.innerText.trim() : '';
        const main = document.querySelector('main, [role="main"]');
        data.fullText = main ? main.innerText.substring(0, 5000) : '';
        if (main) {
            const divs = main.querySelectorAll('p, div, span');
            let texts = [];
            for (const d of divs) {
                const t = d.innerText.trim();
                if (t.length > 30 && t.length < 2000 && !t.includes('Suivre') && !t.includes('Deconnexion') && !t.includes('Parametre')) {
                    texts.push(t);
                }
            }
            data.bioTexts = texts.slice(0, 10);
        }
        return data;
    }""")

    await page.goto("https://app.wyylde.com/fr-fr/mailbox/sent", timeout=30000, wait_until="domcontentloaded")
    await aio.sleep(4)

    results["sent_messages"] = await page.evaluate("""() => {
        const messages = [];
        const main = document.querySelector('main, [role="main"]');
        if (main) {
            messages.push({text: main.innerText.substring(0, 8000), tag: 'MAIN'});
        }
        const links = document.querySelectorAll('a[href*="/mailbox/"], a[href*="/member/"]');
        for (const link of [...links].slice(0, 30)) {
            const t = link.innerText || '';
            if (t.trim().length > 0) {
                messages.push({text: t.trim().substring(0, 300), href: link.href || '', tag: link.tagName});
            }
        }
        return messages;
    }""")

    await page.goto("https://app.wyylde.com/fr-fr", timeout=15000, wait_until="domcontentloaded")

    return results
