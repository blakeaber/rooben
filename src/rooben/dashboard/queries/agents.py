"""Agent queries — spec introspection + performance aggregation."""

from __future__ import annotations

import json

import asyncpg


async def agent_performance(pool: asyncpg.Pool) -> list[dict]:
    """Aggregate agent metrics across all workflows."""
    rows = await pool.fetch(
        """
        SELECT
            t.assigned_agent_id AS agent_id,
            COUNT(*) AS total_tasks,
            COUNT(*) FILTER (WHERE t.status = 'passed') AS passed,
            COUNT(*) FILTER (WHERE t.status = 'failed') AS failed,
            ROUND(
                COUNT(*) FILTER (WHERE t.status = 'passed')::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            ) AS success_rate,
            ROUND(AVG(t.attempt)::numeric, 1) AS avg_attempts,
            COALESCE(SUM(u.tokens), 0) AS total_tokens,
            COALESCE(
                ROUND((SUM(u.tokens)::numeric / NULLIF(COUNT(*), 0)), 0),
                0
            ) AS avg_tokens_per_task
        FROM tasks t
        LEFT JOIN LATERAL (
            SELECT SUM(input_tokens + output_tokens) AS tokens
            FROM workflow_usage
            WHERE task_id = t.id
        ) u ON true
        WHERE t.assigned_agent_id IS NOT NULL
          AND t.status IN ('passed', 'failed')
        GROUP BY t.assigned_agent_id
        ORDER BY total_tasks DESC
        """
    )
    return [dict(r) for r in rows]


async def list_agents(pool: asyncpg.Pool) -> list[dict]:
    """All agents with spec + aggregated task stats."""
    rows = await pool.fetch(
        """
        SELECT
            a.*,
            COALESCE(s.total_tasks, 0) AS total_tasks,
            COALESCE(s.passed, 0) AS passed,
            COALESCE(s.failed, 0) AS failed,
            COALESCE(s.success_rate, 0) AS success_rate,
            COALESCE(s.avg_attempts, 0) AS avg_attempts
        FROM agents a
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) AS total_tasks,
                COUNT(*) FILTER (WHERE t.status = 'passed') AS passed,
                COUNT(*) FILTER (WHERE t.status = 'failed') AS failed,
                ROUND(
                    COUNT(*) FILTER (WHERE t.status = 'passed')::numeric
                    / NULLIF(COUNT(*), 0) * 100, 1
                ) AS success_rate,
                ROUND(AVG(t.attempt)::numeric, 1) AS avg_attempts
            FROM tasks t
            WHERE t.assigned_agent_id = a.id
              AND t.status IN ('passed', 'failed')
        ) s ON true
        ORDER BY a.name
        """
    )
    result = []
    for r in rows:
        d = dict(r)
        # Parse JSONB fields
        for field in ("capabilities", "mcp_servers"):
            if isinstance(d.get(field), str):
                d[field] = json.loads(d[field])
        if isinstance(d.get("budget"), str):
            d["budget"] = json.loads(d["budget"])
        result.append(d)
    return result


async def get_agent(pool: asyncpg.Pool, agent_id: str) -> dict | None:
    """Single agent detail with performance + recent tasks."""
    row = await pool.fetchrow("SELECT * FROM agents WHERE id = $1", agent_id)
    if not row:
        return None

    agent = dict(row)
    for field in ("capabilities", "mcp_servers"):
        if isinstance(agent.get(field), str):
            agent[field] = json.loads(agent[field])
    if isinstance(agent.get("budget"), str):
        agent["budget"] = json.loads(agent["budget"])

    # Performance stats
    stats = await pool.fetchrow(
        """
        SELECT
            COUNT(*) AS total_tasks,
            COUNT(*) FILTER (WHERE status = 'passed') AS passed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed,
            ROUND(
                COUNT(*) FILTER (WHERE status = 'passed')::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            ) AS success_rate,
            ROUND(AVG(attempt)::numeric, 1) AS avg_attempts
        FROM tasks
        WHERE assigned_agent_id = $1
          AND status IN ('passed', 'failed')
        """,
        agent_id,
    )
    agent["stats"] = dict(stats) if stats else {}

    # Recent tasks
    recent = await pool.fetch(
        """
        SELECT id, title, status, workflow_id, attempt, error,
               started_at, completed_at
        FROM tasks
        WHERE assigned_agent_id = $1
        ORDER BY COALESCE(completed_at, started_at, created_at) DESC
        LIMIT 20
        """,
        agent_id,
    )
    agent["recent_tasks"] = [dict(r) for r in recent]

    return agent


async def update_agent(
    pool: asyncpg.Pool, agent_id: str, updates: dict
) -> dict | None:
    """Update agent config fields. Returns updated agent or None if not found."""
    allowed = {"integration", "prompt_template", "model_override"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return None

    set_clauses = []
    args = []
    for i, (k, v) in enumerate(filtered.items(), start=2):
        set_clauses.append(f"{k} = ${i}")
        args.append(v)

    set_clauses.append("updated_at = now()")
    query = f"UPDATE agents SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *"
    row = await pool.fetchrow(query, agent_id, *args)
    if not row:
        return None

    d = dict(row)
    for field in ("capabilities", "mcp_servers"):
        if isinstance(d.get(field), str):
            d[field] = json.loads(d[field])
    if isinstance(d.get("budget"), str):
        d["budget"] = json.loads(d["budget"])
    return d


async def get_workflow_agents(pool: asyncpg.Pool, workflow_id: str) -> list[dict]:
    """Agents used in a specific workflow."""
    rows = await pool.fetch(
        """
        SELECT a.*
        FROM agents a
        JOIN workflow_agents wa ON wa.agent_id = a.id
        WHERE wa.workflow_id = $1
        ORDER BY a.name
        """,
        workflow_id,
    )
    result = []
    for r in rows:
        d = dict(r)
        for field in ("capabilities", "mcp_servers"):
            if isinstance(d.get(field), str):
                d[field] = json.loads(d[field])
        if isinstance(d.get("budget"), str):
            d["budget"] = json.loads(d["budget"])
        result.append(d)
    return result
