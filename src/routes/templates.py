"""Message template CRUD routes."""

import logging

from fastapi import APIRouter, Request

from ..database import get_db, dict_factory

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/templates")
async def get_templates(desire: str = ""):
    """Get message templates, optionally filtered by desire."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        if desire:
            cursor = await db.execute(
                "SELECT id, desire, label, content FROM message_templates WHERE desire = ? ORDER BY id",
                (desire,)
            )
        else:
            cursor = await db.execute(
                "SELECT id, desire, label, content FROM message_templates ORDER BY desire, id"
            )
        return {"templates": await cursor.fetchall()}


@router.post("/templates")
async def save_template(request: Request):
    """Create or update a message template."""
    data = await request.json()
    desire = str(data.get("desire", "")).strip()[:100]
    label = str(data.get("label", "")).strip()[:200]
    content = str(data.get("content", "")).strip()[:2000]
    template_id = data.get("id")
    if not desire or not label or not content:
        return {"error": "missing_fields", "message": "desire, label et content sont requis."}
    async with await get_db() as db:
        if template_id:
            await db.execute(
                "UPDATE message_templates SET desire=?, label=?, content=? WHERE id=?",
                (desire, label, content, template_id)
            )
        else:
            await db.execute(
                "INSERT INTO message_templates (desire, label, content) VALUES (?, ?, ?)",
                (desire, label, content)
            )
        await db.commit()
    return {"status": "ok"}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int):
    """Delete a message template."""
    async with await get_db() as db:
        await db.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
        await db.commit()
    return {"status": "ok"}
