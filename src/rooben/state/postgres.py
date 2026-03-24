"""PostgreSQL state backend — single source of truth for dashboard mode."""

from __future__ import annotations

import json
from typing import Any

import structlog

from rooben.domain import (
    Task,
    TaskResult,
    TaskStatus,
    Workflow,
    WorkflowState,
    WorkflowStatus,
    Workstream,
    WorkstreamStatus,
)

log = structlog.get_logger()


class PostgresStateBackend:
    """
    Stores workflow state directly in PostgreSQL.

    Used by the dashboard to eliminate the dual-write divergence between
    filesystem state and the DB projection via events.  Every state mutation
    goes straight to PG, making it the single source of truth.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def initialize(self) -> None:
        # Tables are created by init.sql — nothing to do here.
        log.info("postgres_backend.initialized")

    async def save_state(self, state: WorkflowState) -> None:
        """Full-state snapshot — upsert all workflows, workstreams, tasks."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for wf in state.workflows.values():
                    await self._upsert_workflow(conn, wf)
                for ws in state.workstreams.values():
                    await self._upsert_workstream(conn, ws)
                for task in state.tasks.values():
                    await self._upsert_task(conn, task)
                    # Upsert dependencies
                    for dep_id in task.depends_on:
                        await conn.execute(
                            """INSERT INTO task_dependencies (task_id, depends_on)
                               VALUES ($1, $2)
                               ON CONFLICT DO NOTHING""",
                            task.id, dep_id,
                        )
        log.debug("postgres_backend.saved", workflows=list(state.workflows.keys()))

    async def load_state(self, workflow_id: str) -> WorkflowState | None:
        """Reconstruct WorkflowState from PG tables."""
        wf_row = await self._pool.fetchrow(
            "SELECT * FROM workflows WHERE id = $1", workflow_id,
        )
        if not wf_row:
            return None

        state = WorkflowState()

        # Workflow
        wf = Workflow(
            id=wf_row["id"],
            spec_id=wf_row["spec_id"] or "",
            status=WorkflowStatus(wf_row["status"]),
            total_tasks=wf_row["total_tasks"],
            completed_tasks=wf_row["completed_tasks"],
            failed_tasks=wf_row["failed_tasks"],
            replan_count=wf_row["replan_count"],
            created_at=wf_row["created_at"],
            completed_at=wf_row["completed_at"],
        )
        state.workflows[wf.id] = wf

        # Workstreams
        ws_rows = await self._pool.fetch(
            "SELECT * FROM workstreams WHERE workflow_id = $1", workflow_id,
        )
        for ws_row in ws_rows:
            task_ids = ws_row["task_ids"]
            if isinstance(task_ids, str):
                task_ids = json.loads(task_ids)
            ws = Workstream(
                id=ws_row["id"],
                workflow_id=ws_row["workflow_id"],
                name=ws_row["name"],
                description=ws_row["description"],
                status=WorkstreamStatus(ws_row["status"]),
                task_ids=task_ids or [],
                created_at=ws_row["created_at"],
            )
            state.workstreams[ws.id] = ws
            if ws.id not in wf.workstream_ids:
                wf.workstream_ids.append(ws.id)

        # Tasks
        task_rows = await self._pool.fetch(
            "SELECT * FROM tasks WHERE workflow_id = $1", workflow_id,
        )
        for t_row in task_rows:
            # Parse result JSONB
            result_data = t_row.get("result")
            task_result = None
            if result_data:
                if isinstance(result_data, str):
                    result_data = json.loads(result_data)
                task_result = TaskResult.model_validate(result_data)

            # Parse attempt_feedback JSONB
            feedback_data = t_row.get("attempt_feedback", [])
            if isinstance(feedback_data, str):
                feedback_data = json.loads(feedback_data)

            # Parse structured_prompt JSONB
            structured_prompt_data = t_row.get("structured_prompt")
            if isinstance(structured_prompt_data, str):
                structured_prompt_data = json.loads(structured_prompt_data)

            # Fetch dependencies
            dep_rows = await self._pool.fetch(
                "SELECT depends_on FROM task_dependencies WHERE task_id = $1",
                t_row["id"],
            )
            depends_on = [r["depends_on"] for r in dep_rows]

            from rooben.domain import StructuredTaskPrompt, VerificationFeedback

            task = Task(
                id=t_row["id"],
                workstream_id=t_row["workstream_id"],
                workflow_id=t_row["workflow_id"],
                title=t_row["title"],
                description=t_row["description"],
                structured_prompt=(
                    StructuredTaskPrompt.model_validate(structured_prompt_data)
                    if structured_prompt_data else None
                ),
                status=TaskStatus(t_row["status"]),
                assigned_agent_id=t_row["assigned_agent_id"],
                depends_on=depends_on,
                verification_strategy=t_row.get("verification_strategy", "llm_judge"),
                result=task_result,
                attempt=t_row["attempt"],
                max_retries=t_row["max_retries"],
                created_at=t_row["created_at"],
                started_at=t_row.get("started_at"),
                completed_at=t_row.get("completed_at"),
                attempt_feedback=[
                    VerificationFeedback.model_validate(fb) for fb in (feedback_data or [])
                ],
            )
            state.tasks[task.id] = task

        return state

    async def update_task(self, task: Task) -> None:
        """Single-task optimized update — called frequently during execution."""
        result_json = None
        if task.result:
            result_json = task.result.model_dump_json()

        feedback_json = json.dumps([fb.model_dump() for fb in task.attempt_feedback])

        await self._pool.execute(
            """UPDATE tasks
               SET status = $2, attempt = $3, started_at = $4,
                   completed_at = $5, error = $6, output = $7,
                   result = $8::jsonb, attempt_feedback = $9::jsonb,
                   updated_at = now()
               WHERE id = $1""",
            task.id,
            task.status.value,
            task.attempt,
            task.started_at,
            task.completed_at,
            task.result.error if task.result else None,
            (task.result.output or "")[:500] if task.result else None,
            result_json,
            feedback_json,
        )

    async def update_workflow(self, workflow: Workflow) -> None:
        """Single-workflow optimized update."""
        await self._pool.execute(
            """UPDATE workflows
               SET status = $2, completed_tasks = $3, failed_tasks = $4,
                   completed_at = $5, total_tasks = $6
               WHERE id = $1""",
            workflow.id,
            workflow.status.value,
            workflow.completed_tasks,
            workflow.failed_tasks,
            workflow.completed_at,
            workflow.total_tasks,
        )

    async def close(self) -> None:
        # Pool lifecycle is managed by the dashboard app, not the backend.
        pass

    # ------------------------------------------------------------------
    # Internal upsert helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _upsert_workflow(conn: Any, wf: Workflow) -> None:
        await conn.execute(
            """INSERT INTO workflows (id, spec_id, status, total_tasks,
                                      completed_tasks, failed_tasks, replan_count,
                                      created_at, completed_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (id) DO UPDATE
               SET spec_id = $2, status = $3, total_tasks = $4,
                   completed_tasks = $5, failed_tasks = $6, replan_count = $7,
                   completed_at = $9""",
            wf.id, wf.spec_id, wf.status.value, wf.total_tasks,
            wf.completed_tasks, wf.failed_tasks, wf.replan_count,
            wf.created_at, wf.completed_at,
        )

    @staticmethod
    async def _upsert_workstream(conn: Any, ws: Workstream) -> None:
        await conn.execute(
            """INSERT INTO workstreams (id, workflow_id, name, description, status, task_ids)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb)
               ON CONFLICT (id) DO UPDATE
               SET workflow_id = $2, name = $3, description = $4, status = $5,
                   task_ids = $6::jsonb, updated_at = now()""",
            ws.id, ws.workflow_id, ws.name, ws.description,
            ws.status.value, json.dumps(ws.task_ids),
        )

    @staticmethod
    async def _upsert_task(conn: Any, task: Task) -> None:
        result_json = None
        if task.result:
            result_json = task.result.model_dump_json()

        feedback_json = json.dumps([fb.model_dump() for fb in task.attempt_feedback])

        structured_prompt_json = None
        if task.structured_prompt:
            structured_prompt_json = task.structured_prompt.model_dump_json()

        await conn.execute(
            """INSERT INTO tasks (id, workflow_id, workstream_id, title, description,
                                  structured_prompt, status, assigned_agent_id,
                                  verification_strategy, attempt, max_retries,
                                  priority, created_at, started_at, completed_at,
                                  error, output, result, attempt_feedback)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12,
                       $13, $14, $15, $16, $17, $18::jsonb, $19::jsonb)
               ON CONFLICT (id) DO UPDATE
               SET status = $7, assigned_agent_id = $8, attempt = $10,
                   started_at = $14, completed_at = $15, error = $16,
                   output = $17, result = $18::jsonb, attempt_feedback = $19::jsonb,
                   updated_at = now()""",
            task.id, task.workflow_id, task.workstream_id,
            task.title, task.description,
            structured_prompt_json,
            task.status.value, task.assigned_agent_id,
            task.verification_strategy, task.attempt, task.max_retries,
            getattr(task, "priority", 0),
            task.created_at, task.started_at, task.completed_at,
            task.result.error if task.result else None,
            (task.result.output or "")[:500] if task.result else None,
            result_json, feedback_json,
        )
