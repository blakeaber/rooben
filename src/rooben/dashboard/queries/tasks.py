"""Task queries — detail, feedback, dependencies."""

from __future__ import annotations

import json

import asyncpg


async def get_workflow_tasks(
    pool: asyncpg.Pool, workflow_id: str
) -> list[dict]:
    """Return all tasks for a workflow with feedback summaries."""
    rows = await pool.fetch(
        """
        SELECT t.id, t.title, t.status, t.assigned_agent_id,
               t.workstream_id, t.attempt, t.max_retries,
               t.verification_strategy, t.created_at, t.started_at,
               t.completed_at, t.attempt_feedback, t.result,
               t.error, t.output, t.description
        FROM tasks t
        WHERE t.workflow_id = $1
        ORDER BY t.created_at
        """,
        workflow_id,
    )

    tasks = []
    for r in rows:
        task = dict(r)
        # Parse JSONB fields
        feedback = r["attempt_feedback"]
        if isinstance(feedback, str):
            feedback = json.loads(feedback)
        task["attempt_feedback"] = feedback

        result = r["result"]
        if isinstance(result, str):
            result = json.loads(result)
        task["result"] = result

        # Add dependency list
        deps = await pool.fetch(
            "SELECT depends_on FROM task_dependencies WHERE task_id = $1",
            r["id"],
        )
        task["depends_on"] = [d["depends_on"] for d in deps]

        # Per-task token/cost breakdown from workflow_usage
        usage_rows = await pool.fetch(
            """SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens,
                      COALESCE(SUM(output_tokens), 0) AS output_tokens,
                      COALESCE(SUM(cost_usd), 0) AS cost_usd
               FROM workflow_usage WHERE task_id = $1""",
            r["id"],
        )
        if usage_rows:
            u = usage_rows[0]
            task["token_usage_detailed"] = {
                "input_tokens": int(u["input_tokens"]),
                "output_tokens": int(u["output_tokens"]),
                "cost_usd": float(u["cost_usd"]),
            }
        else:
            task["token_usage_detailed"] = None

        tasks.append(task)

    return tasks


EDITABLE_STATUSES = {"pending", "blocked", "ready"}


async def update_task(
    pool: asyncpg.Pool, task_id: str, updates: dict
) -> dict | None:
    """Update a task. Only pending/blocked/ready tasks can be edited.

    For depends_on: replaces task_dependencies via DELETE + INSERT.
    """
    # Check task exists and is editable
    row = await pool.fetchrow("SELECT status FROM tasks WHERE id = $1", task_id)
    if not row:
        return None
    if row["status"] not in EDITABLE_STATUSES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit task with status '{row['status']}'"
        )

    # Handle dependency replacement separately
    depends_on = updates.pop("depends_on", None)

    # Build SET clause for remaining fields
    allowed = {"assigned_agent_id", "title", "description", "priority"}
    filtered = {k: v for k, v in updates.items() if k in allowed}

    if filtered:
        set_clauses = []
        args = []
        for i, (k, v) in enumerate(filtered.items(), start=2):
            set_clauses.append(f"{k} = ${i}")
            args.append(v)
        set_clauses.append("updated_at = now()")
        query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = $1"
        await pool.execute(query, task_id, *args)

    # Replace dependencies
    if depends_on is not None:
        await pool.execute(
            "DELETE FROM task_dependencies WHERE task_id = $1", task_id
        )
        for dep_id in depends_on:
            await pool.execute(
                "INSERT INTO task_dependencies (task_id, depends_on) VALUES ($1, $2)",
                task_id, dep_id,
            )

    return await get_task(pool, task_id)


async def get_task(pool: asyncpg.Pool, task_id: str) -> dict | None:
    """Return a single task with full detail."""
    row = await pool.fetchrow(
        "SELECT * FROM tasks WHERE id = $1",
        task_id,
    )
    if not row:
        return None

    task = dict(row)

    # Parse JSONB
    for field in ("attempt_feedback", "result", "structured_prompt",
                  "acceptance_criteria_ids", "skeleton_tests"):
        val = task.get(field)
        if isinstance(val, str):
            task[field] = json.loads(val)

    deps = await pool.fetch(
        "SELECT depends_on FROM task_dependencies WHERE task_id = $1",
        task_id,
    )
    task["depends_on"] = [d["depends_on"] for d in deps]

    return task
