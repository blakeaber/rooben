"""User roles CRUD queries."""

from __future__ import annotations

import asyncpg


async def list_roles(pool: asyncpg.Pool, user_id: str) -> list[dict]:
    """List all roles for a user."""
    rows = await pool.fetch(
        "SELECT * FROM user_roles WHERE user_id = $1 ORDER BY created_at DESC",
        user_id,
    )
    return [dict(r) for r in rows]


async def get_active_role(pool: asyncpg.Pool, user_id: str) -> dict | None:
    """Get the active role for planner injection."""
    row = await pool.fetchrow(
        "SELECT * FROM user_roles WHERE user_id = $1 AND is_active = true LIMIT 1",
        user_id,
    )
    return dict(row) if row else None


async def create_role(pool: asyncpg.Pool, data: dict) -> dict:
    """Create a new role."""
    row = await pool.fetchrow(
        """INSERT INTO user_roles (id, user_id, title, department, context, is_active)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING *""",
        data["id"], data["user_id"], data["title"],
        data.get("department", ""), data.get("context", ""),
        data.get("is_active", True),
    )
    return dict(row)


async def update_role(
    pool: asyncpg.Pool, role_id: str, user_id: str, updates: dict
) -> dict | None:
    """Update a role."""
    allowed = {"title", "department", "context", "is_active"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        row = await pool.fetchrow(
            "SELECT * FROM user_roles WHERE id = $1 AND user_id = $2",
            role_id, user_id,
        )
        return dict(row) if row else None

    set_clauses = []
    args = []
    for i, (k, v) in enumerate(filtered.items(), start=3):
        set_clauses.append(f"{k} = ${i}")
        args.append(v)

    set_clauses.append("updated_at = now()")
    query = f"UPDATE user_roles SET {', '.join(set_clauses)} WHERE id = $1 AND user_id = $2 RETURNING *"
    row = await pool.fetchrow(query, role_id, user_id, *args)
    return dict(row) if row else None


async def delete_role(pool: asyncpg.Pool, role_id: str, user_id: str) -> bool:
    """Delete a role."""
    result = await pool.execute(
        "DELETE FROM user_roles WHERE id = $1 AND user_id = $2",
        role_id, user_id,
    )
    return result == "DELETE 1"
