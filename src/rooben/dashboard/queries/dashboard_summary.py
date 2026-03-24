"""Personal dashboard aggregation query."""

from __future__ import annotations

import asyncpg


async def get_user_dashboard(pool: asyncpg.Pool, user_id: str) -> dict:
    """Aggregate personal dashboard data for a user.

    In OSS (anonymous) mode, returns unscoped counts across all workflows.
    """
    is_anonymous = not user_id or user_id == "anonymous"

    if not pool:
        return {
            "workflows": {"total": 0, "completed": 0, "failed": 0, "in_progress": 0},
            "goals": {"active": 0, "completed": 0},
            "total_cost_usd": 0,
            "success_rate": 0,
            "recent_outcomes": [],
            "suggested_actions": [],
        }

    # Workflow counts — unscoped for anonymous, scoped for authenticated users
    if is_anonymous:
        wf_row = await pool.fetchrow(
            """SELECT
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                   COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                   COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress
               FROM workflows""",
        )
    else:
        wf_row = await pool.fetchrow(
            """SELECT
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                   COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                   COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress
               FROM workflows WHERE user_id = $1""",
            user_id,
        )

    # Goal counts
    if is_anonymous:
        goal_row = await pool.fetchrow(
            """SELECT
                   COUNT(*) FILTER (WHERE status = 'active') AS active,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed
               FROM user_goals""",
        )
    else:
        goal_row = await pool.fetchrow(
            """SELECT
                   COUNT(*) FILTER (WHERE status = 'active') AS active,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed
               FROM user_goals WHERE user_id = $1""",
            user_id,
        )

    # Total cost
    if is_anonymous:
        cost = await pool.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM workflow_usage",
        )
    else:
        cost = await pool.fetchval(
            """SELECT COALESCE(SUM(wu.cost_usd), 0)
               FROM workflow_usage wu
               JOIN workflows w ON w.id = wu.workflow_id
               WHERE w.user_id = $1""",
            user_id,
        )

    # Success rate from outcomes
    if is_anonymous:
        outcome_row = await pool.fetchrow(
            """SELECT COUNT(*) AS total,
                      AVG(quality_score) AS avg_quality
               FROM user_outcomes""",
        )
    else:
        outcome_row = await pool.fetchrow(
            """SELECT COUNT(*) AS total,
                      AVG(quality_score) AS avg_quality
               FROM user_outcomes WHERE user_id = $1""",
            user_id,
        )

    # Recent outcomes
    if is_anonymous:
        recent = await pool.fetch(
            """SELECT * FROM user_outcomes
               ORDER BY created_at DESC LIMIT 5""",
        )
    else:
        recent = await pool.fetch(
            """SELECT * FROM user_outcomes
               WHERE user_id = $1
               ORDER BY created_at DESC LIMIT 5""",
            user_id,
        )

    # Suggested actions (simple heuristics)
    suggested = []
    active_goals = goal_row["active"] if goal_row else 0
    if active_goals == 0:
        suggested.append("Set your first goal to track progress")
    total_wf = wf_row["total"] if wf_row else 0
    if total_wf == 0:
        suggested.append("Run your first workflow")
    failed_wf = wf_row["failed"] if wf_row else 0
    if failed_wf > 0 and total_wf > 0 and failed_wf / total_wf > 0.3:
        suggested.append("Review failed workflows for common issues")

    return {
        "workflows": {
            "total": wf_row["total"] if wf_row else 0,
            "completed": wf_row["completed"] if wf_row else 0,
            "failed": wf_row["failed"] if wf_row else 0,
            "in_progress": wf_row["in_progress"] if wf_row else 0,
        },
        "goals": {
            "active": goal_row["active"] if goal_row else 0,
            "completed": goal_row["completed"] if goal_row else 0,
        },
        "total_cost_usd": float(cost) if cost else 0,
        "success_rate": float(outcome_row["avg_quality"]) if outcome_row and outcome_row["avg_quality"] else 0,
        "recent_outcomes": [dict(r) for r in recent],
        "suggested_actions": suggested,
    }
