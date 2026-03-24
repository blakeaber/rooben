"""User outcomes queries."""

from __future__ import annotations

import asyncpg


async def list_outcomes(
    pool: asyncpg.Pool,
    user_id: str,
    goal_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List outcomes for a user, optionally filtered by goal."""
    if goal_id:
        rows = await pool.fetch(
            """SELECT * FROM user_outcomes
               WHERE user_id = $1 AND goal_id = $2
               ORDER BY created_at DESC LIMIT $3""",
            user_id, goal_id, limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT * FROM user_outcomes
               WHERE user_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            user_id, limit,
        )
    return [dict(r) for r in rows]


async def create_outcome(pool: asyncpg.Pool, data: dict) -> dict:
    """Create a new outcome record."""
    row = await pool.fetchrow(
        """INSERT INTO user_outcomes (id, user_id, workflow_id, goal_id, outcome_type, summary, quality_score)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING *""",
        data["id"], data["user_id"], data["workflow_id"],
        data.get("goal_id"), data.get("outcome_type", "workflow_completion"),
        data.get("summary", ""), data.get("quality_score", 0),
    )
    return dict(row)


async def get_goal_progress(pool: asyncpg.Pool, goal_id: str) -> dict:
    """Get progress stats for a goal based on its outcomes."""
    row = await pool.fetchrow(
        """SELECT COUNT(*) AS total_outcomes,
                  AVG(quality_score) AS avg_quality,
                  MAX(created_at) AS last_outcome_at
           FROM user_outcomes WHERE goal_id = $1""",
        goal_id,
    )
    return {
        "total_outcomes": row["total_outcomes"] or 0,
        "avg_quality": float(row["avg_quality"]) if row["avg_quality"] else 0,
        "last_outcome_at": row["last_outcome_at"],
    }
