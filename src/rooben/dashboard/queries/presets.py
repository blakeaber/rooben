"""Agent preset CRUD queries."""

from __future__ import annotations

import json

import asyncpg

async def list_presets(pool: asyncpg.Pool, user_context: dict | None = None) -> list[dict]:
    """List all agent presets."""
    rows = await pool.fetch(
        "SELECT * FROM agent_presets ORDER BY name"
    )
    result = []
    for r in rows:
        d = dict(r)
        for field in ("capabilities",):
            if isinstance(d.get(field), str):
                d[field] = json.loads(d[field])
        if isinstance(d.get("budget"), str):
            d["budget"] = json.loads(d["budget"])
        result.append(d)
    return result


async def get_preset(pool: asyncpg.Pool, preset_id: str) -> dict | None:
    """Get a single preset by ID."""
    row = await pool.fetchrow(
        "SELECT * FROM agent_presets WHERE id = $1", preset_id
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


async def create_preset(pool: asyncpg.Pool, data: dict) -> dict:
    """Create a new preset."""
    capabilities = data.get("capabilities", [])
    if isinstance(capabilities, list):
        capabilities = json.dumps(capabilities)
    budget = data.get("budget")
    if isinstance(budget, dict):
        budget = json.dumps(budget)

    row = await pool.fetchrow(
        """INSERT INTO agent_presets
           (id, name, description, integration, prompt_template, model_override,
            capabilities, max_context_tokens, budget, user_id, is_default)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9::jsonb, $10, $11)
           RETURNING *""",
        data["id"],
        data["name"],
        data.get("description", ""),
        data.get("integration"),
        data.get("prompt_template", ""),
        data.get("model_override", ""),
        capabilities if isinstance(capabilities, str) else json.dumps(capabilities),
        data.get("max_context_tokens", 200000),
        budget,
        data.get("user_id"),
        data.get("is_default", False),
    )
    d = dict(row)
    for field in ("capabilities",):
        if isinstance(d.get(field), str):
            d[field] = json.loads(d[field])
    if isinstance(d.get("budget"), str):
        d["budget"] = json.loads(d["budget"])
    return d


async def update_preset(pool: asyncpg.Pool, preset_id: str, updates: dict) -> dict | None:
    """Update a preset."""
    allowed = {
        "name", "description", "integration", "prompt_template", "model_override",
        "capabilities", "max_context_tokens", "budget", "is_default",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return await get_preset(pool, preset_id)

    # Serialize JSONB fields
    if "capabilities" in filtered and isinstance(filtered["capabilities"], list):
        filtered["capabilities"] = json.dumps(filtered["capabilities"])
    if "budget" in filtered and isinstance(filtered["budget"], (dict, type(None))):
        filtered["budget"] = json.dumps(filtered["budget"]) if filtered["budget"] else None

    set_clauses = []
    args = []
    for i, (k, v) in enumerate(filtered.items(), start=2):
        if k in ("capabilities",):
            set_clauses.append(f"{k} = ${i}::jsonb")
        elif k == "budget":
            set_clauses.append(f"{k} = ${i}::jsonb")
        else:
            set_clauses.append(f"{k} = ${i}")
        args.append(v)

    set_clauses.append("updated_at = now()")
    query = f"UPDATE agent_presets SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *"
    row = await pool.fetchrow(query, preset_id, *args)
    if not row:
        return None
    d = dict(row)
    for field in ("capabilities",):
        if isinstance(d.get(field), str):
            d[field] = json.loads(d[field])
    if isinstance(d.get("budget"), str):
        d["budget"] = json.loads(d["budget"])
    return d


async def delete_preset(pool: asyncpg.Pool, preset_id: str) -> bool:
    """Delete a preset by ID."""
    result = await pool.execute(
        "DELETE FROM agent_presets WHERE id = $1", preset_id
    )
    return result == "DELETE 1"
