"""Waitlist endpoint for Rooben early-access signups."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps

router = APIRouter(prefix="/api", tags=["waitlist"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FALLBACK_FILE = Path.home() / ".rooben" / "waitlist.json"


class WaitlistRequest(BaseModel):
    email: str
    name: str = ""
    referral_source: str = ""


class WaitlistResponse(BaseModel):
    ok: bool
    position: int


@router.post("/waitlist", response_model=WaitlistResponse)
async def join_waitlist(body: WaitlistRequest) -> WaitlistResponse:
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email address")

    deps = get_deps()
    now = datetime.now(timezone.utc).isoformat()
    name = body.name.strip()
    referral_source = body.referral_source.strip()

    # Try DB first
    if deps.pool:
        # Create table if not exists (idempotent)
        await deps.pool.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                referral_source TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        try:
            row = await deps.pool.fetchrow(
                "INSERT INTO waitlist (email, name, referral_source) VALUES ($1, $2, $3) "
                "ON CONFLICT (email) DO NOTHING RETURNING id",
                email, name, referral_source,
            )
            if row:
                position = row["id"]
            else:
                # Already exists
                position = await deps.pool.fetchval(
                    "SELECT id FROM waitlist WHERE email = $1", email
                )
        except Exception:
            raise HTTPException(status_code=500, detail="Database error")
    else:
        # Fallback: JSON file
        FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict] = []
        if FALLBACK_FILE.exists():
            entries = json.loads(FALLBACK_FILE.read_text())

        existing = next((e for e in entries if e["email"] == email), None)
        if existing:
            position = existing["position"]
        else:
            position = len(entries) + 1
            entries.append({
                "email": email,
                "name": name,
                "referral_source": referral_source,
                "position": position,
                "created_at": now,
            })
            FALLBACK_FILE.write_text(json.dumps(entries, indent=2))

    return WaitlistResponse(ok=True, position=position)


@router.get("/waitlist/count")
async def waitlist_count():
    """Return the current waitlist signup count."""
    deps = get_deps()

    if deps.pool:
        try:
            count = await deps.pool.fetchval("SELECT count(*) FROM waitlist")
            return {"count": count or 0}
        except Exception:
            return {"count": 0}
    else:
        # JSON fallback
        if FALLBACK_FILE.exists():
            entries = json.loads(FALLBACK_FILE.read_text())
            return {"count": len(entries)}
        return {"count": 0}
