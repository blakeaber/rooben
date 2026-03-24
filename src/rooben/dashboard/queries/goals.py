"""User goals CRUD queries."""

from __future__ import annotations

import json

import asyncpg


async def list_goals(
    pool: asyncpg.Pool, user_id: str, status: str | None = None
) -> list[dict]:
    """List goals for a user, optionally filtered by status."""
    if status:
        rows = await pool.fetch(
            """SELECT * FROM user_goals
               WHERE user_id = $1 AND status = $2
               ORDER BY created_at DESC""",
            user_id, status,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM user_goals WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("tags"), str):
            d["tags"] = json.loads(d["tags"])
        result.append(d)
    return result


async def get_goal(pool: asyncpg.Pool, goal_id: str, user_id: str) -> dict | None:
    """Get a single goal with outcome count."""
    row = await pool.fetchrow(
        """SELECT g.*,
                  (SELECT COUNT(*) FROM user_outcomes WHERE goal_id = g.id) AS outcome_count
           FROM user_goals g
           WHERE g.id = $1 AND g.user_id = $2""",
        goal_id, user_id,
    )
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("tags"), str):
        d["tags"] = json.loads(d["tags"])
    return d


async def create_goal(pool: asyncpg.Pool, data: dict) -> dict:
    """Create a new goal."""
    tags = data.get("tags", [])
    if isinstance(tags, list):
        tags = json.dumps(tags)
    row = await pool.fetchrow(
        """INSERT INTO user_goals (id, user_id, title, description, status, target_date, tags)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
           RETURNING *""",
        data["id"], data["user_id"], data["title"],
        data.get("description", ""), data.get("status", "active"),
        data.get("target_date"), tags,
    )
    d = dict(row)
    if isinstance(d.get("tags"), str):
        d["tags"] = json.loads(d["tags"])
    return d


async def update_goal(
    pool: asyncpg.Pool, goal_id: str, user_id: str, updates: dict
) -> dict | None:
    """Update a goal."""
    allowed = {"title", "description", "status", "target_date", "tags"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return await get_goal(pool, goal_id, user_id)

    if "tags" in filtered and isinstance(filtered["tags"], list):
        filtered["tags"] = json.dumps(filtered["tags"])

    set_clauses = []
    args = []
    for i, (k, v) in enumerate(filtered.items(), start=3):
        if k == "tags":
            set_clauses.append(f"{k} = ${i}::jsonb")
        else:
            set_clauses.append(f"{k} = ${i}")
        args.append(v)

    set_clauses.append("updated_at = now()")
    query = f"UPDATE user_goals SET {', '.join(set_clauses)} WHERE id = $1 AND user_id = $2 RETURNING *"
    row = await pool.fetchrow(query, goal_id, user_id, *args)
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("tags"), str):
        d["tags"] = json.loads(d["tags"])
    return d


async def delete_goal(pool: asyncpg.Pool, goal_id: str, user_id: str) -> bool:
    """Delete a goal."""
    result = await pool.execute(
        "DELETE FROM user_goals WHERE id = $1 AND user_id = $2",
        goal_id, user_id,
    )
    return result == "DELETE 1"
