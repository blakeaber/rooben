"""Workflow queries — list, detail, status aggregation."""

from __future__ import annotations

import json
from collections import defaultdict

import asyncpg


async def list_workflows(
    pool: asyncpg.Pool,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_context: dict | None = None,
) -> tuple[list[dict], int]:
    """Return paginated workflow list with task counts and cost."""
    conditions = []
    params: list = []
    idx = 1

    if status:
        conditions.append(f"w.status = ${idx}")
        params.append(status)
        idx += 1

    if user_context:
        if user_context.get("org_id"):
            conditions.append(f"w.org_id = ${idx}")
            params.append(user_context["org_id"])
            idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = await pool.fetchrow(
        f"SELECT COUNT(*) AS total FROM workflows w {where}", *params
    )
    total = count_row["total"]

    params.extend([limit, offset])
    rows = await pool.fetch(
        f"""
        SELECT
            w.id, w.spec_id, w.status, w.created_at, w.completed_at,
            w.total_tasks, w.completed_tasks, w.failed_tasks,
            w.replan_count,
            COALESCE(u.total_cost, 0) AS total_cost_usd,
            COALESCE(u.total_tokens, 0) AS total_tokens
        FROM workflows w
        LEFT JOIN LATERAL (
            SELECT
                SUM(cost_usd) AS total_cost,
                SUM(input_tokens + output_tokens) AS total_tokens
            FROM workflow_usage
            WHERE workflow_id = w.id
        ) u ON true
        {where}
        ORDER BY w.created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return [dict(r) for r in rows], total


async def get_workflow(
    pool: asyncpg.Pool, workflow_id: str,
    user_context: dict | None = None,
) -> dict | None:
    """Return full workflow detail with workstreams."""
    wf_row = await pool.fetchrow(
        """
        SELECT
            w.*,
            COALESCE(u.total_cost, 0) AS total_cost_usd,
            COALESCE(u.total_input, 0) AS total_input_tokens,
            COALESCE(u.total_output, 0) AS total_output_tokens
        FROM workflows w
        LEFT JOIN LATERAL (
            SELECT
                SUM(cost_usd) AS total_cost,
                SUM(input_tokens) AS total_input,
                SUM(output_tokens) AS total_output
            FROM workflow_usage
            WHERE workflow_id = w.id
        ) u ON true
        WHERE w.id = $1
        """,
        workflow_id,
    )
    if not wf_row:
        return None

    ws_rows = await pool.fetch(
        "SELECT * FROM workstreams WHERE workflow_id = $1 ORDER BY created_at",
        workflow_id,
    )

    workstreams = []
    for r in ws_rows:
        ws = dict(r)
        if isinstance(ws.get("task_ids"), str):
            ws["task_ids"] = json.loads(ws["task_ids"])
        workstreams.append(ws)

    wf = dict(wf_row)
    if isinstance(wf.get("plan_quality"), str):
        wf["plan_quality"] = json.loads(wf["plan_quality"])
    if isinstance(wf.get("spec_metadata"), str):
        wf["spec_metadata"] = json.loads(wf["spec_metadata"])

    return {
        "workflow": wf,
        "workstreams": workstreams,
    }


async def get_workflow_dag(pool: asyncpg.Pool, workflow_id: str) -> dict:
    """Return nodes and edges for React Flow DAG visualization."""
    tasks = await pool.fetch(
        """
        SELECT t.id, t.title, t.status, t.assigned_agent_id,
               t.workstream_id, t.attempt, t.max_retries,
               t.created_at, t.completed_at
        FROM tasks t
        WHERE t.workflow_id = $1
        ORDER BY t.created_at
        """,
        workflow_id,
    )

    deps = await pool.fetch(
        """
        SELECT td.task_id, td.depends_on
        FROM task_dependencies td
        JOIN tasks t ON td.task_id = t.id
        WHERE t.workflow_id = $1
        """,
        workflow_id,
    )

    workstreams = await pool.fetch(
        "SELECT id, name FROM workstreams WHERE workflow_id = $1 ORDER BY created_at",
        workflow_id,
    )
    ws_map = {r["id"]: r["name"] for r in workstreams}
    ws_order = {r["id"]: i for i, r in enumerate(workstreams)}

    dep_map: dict[str, list[str]] = {}
    for d in deps:
        dep_map.setdefault(d["task_id"], []).append(d["depends_on"])

    waves: dict[str, int] = {}

    def get_wave(task_id: str) -> int:
        if task_id in waves:
            return waves[task_id]
        task_deps = dep_map.get(task_id, [])
        if not task_deps:
            waves[task_id] = 0
            return 0
        wave = max(get_wave(d) for d in task_deps) + 1
        waves[task_id] = wave
        return wave

    for t in tasks:
        get_wave(t["id"])

    # Group tasks by (wave, workstream) cell to prevent overlap
    cell_members: dict[tuple[int, int], list[str]] = defaultdict(list)
    for t in tasks:
        ws_idx = ws_order.get(t["workstream_id"], 0)
        wave = waves.get(t["id"], 0)
        cell_members[(wave, ws_idx)].append(t["id"])

    cell_slot: dict[str, int] = {}
    cell_size: dict[tuple[int, int], int] = {}
    for key, members in cell_members.items():
        cell_size[key] = len(members)
        for i, tid in enumerate(members):
            cell_slot[tid] = i

    SUB_SPACING = 80  # px between stacked nodes within a cell

    nodes = []
    for t in tasks:
        ws_idx = ws_order.get(t["workstream_id"], 0)
        wave = waves.get(t["id"], 0)
        cell_key = (wave, ws_idx)
        n = cell_size[cell_key]
        slot = cell_slot[t["id"]]
        group_offset = (n - 1) * SUB_SPACING
        y = ws_idx * 150 - group_offset / 2 + slot * SUB_SPACING

        nodes.append({
            "id": t["id"],
            "type": "taskNode",
            "position": {"x": wave * 280, "y": y},
            "data": {
                "title": t["title"],
                "status": t["status"],
                "agent": t["assigned_agent_id"],
                "workstream": ws_map.get(t["workstream_id"], ""),
                "attempt": t["attempt"],
                "maxRetries": t["max_retries"],
            },
        })

    edges = [
        {
            "id": f"e-{d['depends_on']}-{d['task_id']}",
            "source": d["depends_on"],
            "target": d["task_id"],
            "animated": True,
        }
        for d in deps
    ]

    return {"nodes": nodes, "edges": edges}


async def get_workflow_timeline(pool: asyncpg.Pool, workflow_id: str) -> list[dict]:
    """Reconstruct timeline events from existing DB data."""
    events: list[dict] = []

    # Workflow creation + plan quality
    wf_row = await pool.fetchrow(
        "SELECT created_at, completed_at, plan_quality FROM workflows WHERE id = $1",
        workflow_id,
    )
    if not wf_row:
        return events

    events.append({
        "type": "workflow_created",
        "category": "planning",
        "title": "Workflow created",
        "timestamp": wf_row["created_at"].isoformat(),
    })

    plan_quality = wf_row["plan_quality"]
    if isinstance(plan_quality, str):
        plan_quality = json.loads(plan_quality)
    if plan_quality:
        checker_score = plan_quality.get("checker", {}).get("score")
        judge_score = plan_quality.get("judge", {}).get("score") if plan_quality.get("judge") else None
        detail_parts = []
        if checker_score is not None:
            detail_parts.append(f"Checker: {checker_score:.2f}")
        if judge_score is not None:
            detail_parts.append(f"Judge: {judge_score:.2f}")
        events.append({
            "type": "plan_validated",
            "category": "planning",
            "title": "Plan validated",
            "detail": ", ".join(detail_parts) if detail_parts else None,
            "timestamp": wf_row["created_at"].isoformat(),
        })

    # Task events
    task_rows = await pool.fetch(
        """SELECT id, title, status, started_at, completed_at, attempt_feedback
           FROM tasks WHERE workflow_id = $1 ORDER BY created_at""",
        workflow_id,
    )

    for t in task_rows:
        if t["started_at"]:
            events.append({
                "type": "task_started",
                "category": "execution",
                "title": f"Started: {t['title']}",
                "timestamp": t["started_at"].isoformat(),
                "task_id": t["id"],
                "status": t["status"],
            })

        # Verification attempts from attempt_feedback
        feedback = t["attempt_feedback"]
        if isinstance(feedback, str):
            feedback = json.loads(feedback)
        if feedback and isinstance(feedback, list):
            for fb in feedback:
                if not isinstance(fb, dict):
                    continue
                # Use a timestamp estimate: started_at + small offset per attempt
                ts = t["started_at"] or t["completed_at"]
                if ts:
                    events.append({
                        "type": "task_verification",
                        "category": "verification",
                        "title": f"{'Passed' if fb.get('passed') else 'Failed'}: {t['title']}",
                        "detail": f"Score: {fb.get('score', 0):.2f}, attempt {fb.get('attempt', 0)}",
                        "timestamp": ts.isoformat(),
                        "task_id": t["id"],
                        "status": "passed" if fb.get("passed") else "failed",
                    })

        if t["completed_at"]:
            events.append({
                "type": "task_completed",
                "category": "execution",
                "title": f"Completed: {t['title']}",
                "timestamp": t["completed_at"].isoformat(),
                "task_id": t["id"],
                "status": t["status"],
            })

    # Workflow completion
    if wf_row["completed_at"]:
        events.append({
            "type": "workflow_completed",
            "category": "completion",
            "title": "Workflow completed",
            "timestamp": wf_row["completed_at"].isoformat(),
        })

    # Sort by timestamp
    events.sort(key=lambda e: e["timestamp"])
    return events
