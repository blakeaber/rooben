"""User preferences and default preset queries."""

from __future__ import annotations

import json

import asyncpg


async def get_preferences(pool: asyncpg.Pool, user_id: str) -> dict:
    """Get user preferences from the users table. Returns {} for anonymous or missing."""
    if not user_id or user_id == "anonymous":
        return {}
    row = await pool.fetchval(
        "SELECT preferences FROM users WHERE id = $1", user_id
    )
    if row is None:
        return {}
    if isinstance(row, str):
        return json.loads(row)
    return dict(row) if hasattr(row, "keys") else row


async def update_preferences(pool: asyncpg.Pool, user_id: str, updates: dict) -> dict:
    """Merge updates into user preferences JSONB column."""
    row = await pool.fetchval(
        """UPDATE users SET preferences = preferences || $2::jsonb, updated_at = now()
           WHERE id = $1
           RETURNING preferences""",
        user_id,
        json.dumps(updates),
    )
    if row is None:
        return {}
    if isinstance(row, str):
        return json.loads(row)
    return dict(row) if hasattr(row, "keys") else row


async def get_default_preset(pool: asyncpg.Pool, user_id: str) -> dict | None:
    """Get the user's default agent preset."""
    row = await pool.fetchrow(
        "SELECT * FROM agent_presets WHERE user_id = $1 AND is_default = true LIMIT 1",
        user_id,
    )
    if not row:
        return None
    d = dict(row)
    for field in ("capabilities",):
        if isinstance(d.get(field), str):
            d[field] = json.loads(d[field])
    if isinstance(d.get("budget"), str):
        d["budget"] = json.loads(d["budget"])
    return d


async def set_default_preset(pool: asyncpg.Pool, user_id: str, preset_id: str) -> bool:
    """Set a preset as default, clearing any other defaults for this user."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE agent_presets SET is_default = false WHERE user_id = $1 AND is_default = true",
                user_id,
            )
            result = await conn.execute(
                "UPDATE agent_presets SET is_default = true WHERE id = $1 AND user_id = $2",
                preset_id,
                user_id,
            )
            return result == "UPDATE 1"
