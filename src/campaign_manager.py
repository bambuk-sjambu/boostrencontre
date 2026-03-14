"""Campaign manager: create, manage, and track outreach campaigns."""

import json
import logging
from datetime import datetime, timezone

from .database import get_db, dict_factory

logger = logging.getLogger(__name__)

VALID_STATUSES = {"draft", "active", "paused", "completed"}
VALID_CONTACT_STATUSES = {
    "pending", "contacted", "replied", "conversation", "met", "rejected", "skipped"
}


async def create_campaign(
    name: str,
    platform: str,
    filters: dict | None = None,
) -> int:
    """Create a new campaign with targeting criteria.

    Args:
        name: Campaign name.
        platform: Target platform (wyylde, tinder, meetic).
        filters: Dict with optional keys: target_type, age_min, age_max,
                 location, desires (list), style, max_contacts.

    Returns:
        The new campaign id.
    """
    if not name or not platform:
        raise ValueError("name and platform are required")

    filters = filters or {}
    target_type = filters.get("target_type")
    age_min = filters.get("age_min")
    age_max = filters.get("age_max")
    location = filters.get("location")
    desires = filters.get("desires")
    style = filters.get("style", "auto")
    max_contacts = filters.get("max_contacts", 20)

    desires_json = json.dumps(desires) if desires else None

    async with await get_db() as db:
        cursor = await db.execute(
            "INSERT INTO campaigns "
            "(name, platform, target_type, target_age_min, target_age_max, "
            "target_location, target_desires, style, max_contacts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, platform, target_type, age_min, age_max,
             location, desires_json, style, max_contacts),
        )
        await db.commit()
        return cursor.lastrowid


async def get_campaign(campaign_id: int) -> dict | None:
    """Get campaign details with its contacts."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        )
        campaign = await cursor.fetchone()
        if not campaign:
            return None

        # Parse desires JSON
        if campaign.get("target_desires"):
            try:
                campaign["target_desires"] = json.loads(campaign["target_desires"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Fetch contacts
        cursor = await db.execute(
            "SELECT * FROM campaign_contacts WHERE campaign_id = ? "
            "ORDER BY score DESC, id ASC",
            (campaign_id,),
        )
        campaign["contacts"] = await cursor.fetchall()

    return campaign


async def list_campaigns(platform: str | None = None) -> list:
    """List all campaigns, optionally filtered by platform."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        if platform:
            cursor = await db.execute(
                "SELECT * FROM campaigns WHERE platform = ? "
                "ORDER BY created_at DESC",
                (platform,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC"
            )
        campaigns = await cursor.fetchall()

    for c in campaigns:
        if c.get("target_desires"):
            try:
                c["target_desires"] = json.loads(c["target_desires"])
            except (json.JSONDecodeError, TypeError):
                pass
    return campaigns


async def start_campaign(campaign_id: int) -> dict:
    """Start or resume a campaign (set status to active)."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT id, status FROM campaigns WHERE id = ?", (campaign_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {"error": "campaign_not_found"}
        if row["status"] == "completed":
            return {"error": "campaign_completed"}

        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE campaigns SET status = 'active', updated_at = ? WHERE id = ?",
            (now, campaign_id),
        )
        await db.commit()
    return {"status": "active", "campaign_id": campaign_id}


async def pause_campaign(campaign_id: int) -> dict:
    """Pause an active campaign."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT id, status FROM campaigns WHERE id = ?", (campaign_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {"error": "campaign_not_found"}

        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE campaigns SET status = 'paused', updated_at = ? WHERE id = ?",
            (now, campaign_id),
        )
        await db.commit()
    return {"status": "paused", "campaign_id": campaign_id}


async def complete_campaign(campaign_id: int) -> dict:
    """Mark a campaign as completed."""
    async with await get_db() as db:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE campaigns SET status = 'completed', updated_at = ? WHERE id = ?",
            (now, campaign_id),
        )
        await db.commit()
    return {"status": "completed", "campaign_id": campaign_id}


async def delete_campaign(campaign_id: int) -> dict:
    """Delete a campaign and its contacts."""
    async with await get_db() as db:
        await db.execute(
            "DELETE FROM campaign_contacts WHERE campaign_id = ?", (campaign_id,)
        )
        cursor = await db.execute(
            "DELETE FROM campaigns WHERE id = ?", (campaign_id,)
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"error": "campaign_not_found"}
    return {"status": "deleted"}


async def add_contact_to_campaign(
    campaign_id: int,
    contact_name: str,
    contact_type: str | None = None,
    contact_age: str | None = None,
    score: int | None = None,
) -> dict:
    """Add a contact to a campaign. Ignores duplicates."""
    async with await get_db() as db:
        try:
            await db.execute(
                "INSERT INTO campaign_contacts "
                "(campaign_id, contact_name, contact_type, contact_age, score) "
                "VALUES (?, ?, ?, ?, ?)",
                (campaign_id, contact_name, contact_type, contact_age, score),
            )
            await db.commit()
        except Exception as e:
            if "UNIQUE" in str(e):
                return {"status": "duplicate", "contact_name": contact_name}
            raise
    return {"status": "added", "contact_name": contact_name}


async def update_contact_status(
    campaign_id: int,
    contact_name: str,
    status: str,
    **kwargs,
) -> dict:
    """Update contact status and optional fields (message_sent, notes)."""
    if status not in VALID_CONTACT_STATUSES:
        return {"error": f"invalid_status: {status}"}

    updates = ["status = ?"]
    params = [status]

    if status == "contacted":
        updates.append("contacted_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
    elif status == "replied":
        updates.append("replied_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())

    if "message_sent" in kwargs:
        updates.append("message_sent = ?")
        params.append(kwargs["message_sent"])
    if "notes" in kwargs:
        updates.append("notes = ?")
        params.append(kwargs["notes"])

    params.extend([campaign_id, contact_name])

    async with await get_db() as db:
        cursor = await db.execute(
            f"UPDATE campaign_contacts SET {', '.join(updates)} "
            "WHERE campaign_id = ? AND contact_name = ?",
            params,
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"error": "contact_not_found"}

        # Update contacts_done count on the campaign
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM campaign_contacts "
            "WHERE campaign_id = ? AND status != 'pending' AND status != 'skipped'",
            (campaign_id,),
        )
        row = await cursor.fetchone()
        done_count = row[0] if row else 0
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE campaigns SET contacts_done = ?, updated_at = ? WHERE id = ?",
            (done_count, now, campaign_id),
        )
        await db.commit()

    return {"status": "updated", "contact_name": contact_name, "new_status": status}


async def update_contact_status_by_id(
    contact_id: int,
    status: str,
    **kwargs,
) -> dict:
    """Update contact status by contact id."""
    if status not in VALID_CONTACT_STATUSES:
        return {"error": f"invalid_status: {status}"}

    updates = ["status = ?"]
    params = [status]

    if status == "contacted":
        updates.append("contacted_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
    elif status == "replied":
        updates.append("replied_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())

    if "message_sent" in kwargs:
        updates.append("message_sent = ?")
        params.append(kwargs["message_sent"])
    if "notes" in kwargs:
        updates.append("notes = ?")
        params.append(kwargs["notes"])

    params.append(contact_id)

    async with await get_db() as db:
        db.row_factory = dict_factory
        # Get campaign_id before updating
        cursor = await db.execute(
            "SELECT campaign_id FROM campaign_contacts WHERE id = ?", (contact_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {"error": "contact_not_found"}
        campaign_id = row["campaign_id"]

        await db.execute(
            f"UPDATE campaign_contacts SET {', '.join(updates)} WHERE id = ?",
            params,
        )

        # Update contacts_done count
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM campaign_contacts "
            "WHERE campaign_id = ? AND status != 'pending' AND status != 'skipped'",
            (campaign_id,),
        )
        row = await cursor.fetchone()
        done_count = row["cnt"] if row else 0
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE campaigns SET contacts_done = ?, updated_at = ? WHERE id = ?",
            (done_count, now, campaign_id),
        )
        await db.commit()

    return {"status": "updated", "contact_id": contact_id, "new_status": status}


async def get_campaign_stats(campaign_id: int) -> dict:
    """Compute campaign statistics and funnel."""
    async with await get_db() as db:
        db.row_factory = dict_factory
        cursor = await db.execute(
            "SELECT status, COUNT(*) as cnt FROM campaign_contacts "
            "WHERE campaign_id = ? GROUP BY status",
            (campaign_id,),
        )
        rows = await cursor.fetchall()

    counts = {r["status"]: r["cnt"] for r in rows}
    total = sum(counts.values())
    pending = counts.get("pending", 0)
    contacted = counts.get("contacted", 0)
    replied = counts.get("replied", 0)
    conversation = counts.get("conversation", 0)
    met = counts.get("met", 0)
    rejected = counts.get("rejected", 0)
    skipped = counts.get("skipped", 0)

    # Contacted includes all who were contacted (contacted + replied + conversation + met)
    total_contacted = contacted + replied + conversation + met
    total_replied = replied + conversation + met

    response_rate = round(total_replied / total_contacted * 100, 1) if total_contacted > 0 else 0.0
    conversion_rate = round(met / total_contacted * 100, 1) if total_contacted > 0 else 0.0

    def _rate(count: int, base: int) -> str:
        if base == 0:
            return "0%"
        return f"{round(count / base * 100, 1)}%"

    funnel = [
        {"stage": "contacted", "count": total_contacted, "rate": _rate(total_contacted, total_contacted)},
        {"stage": "replied", "count": total_replied, "rate": _rate(total_replied, total_contacted)},
        {"stage": "conversation", "count": conversation + met, "rate": _rate(conversation + met, total_contacted)},
        {"stage": "met", "count": met, "rate": _rate(met, total_contacted)},
    ]

    return {
        "total_contacts": total,
        "pending": pending,
        "contacted": contacted,
        "replied": replied,
        "conversation": conversation,
        "met": met,
        "rejected": rejected,
        "skipped": skipped,
        "response_rate": response_rate,
        "conversion_rate": conversion_rate,
        "funnel": funnel,
    }
