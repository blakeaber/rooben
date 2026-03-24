"""Workflow lifecycle endpoints: status, cancel, retry, SSE."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps
from rooben.dashboard.workflow_registry import get_registry

router = APIRouter()


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    progress: dict
    is_live: bool


class CancelResponse(BaseModel):
    workflow_id: str
    status: str


class RetryRequest(BaseModel):
    replan: bool = False


@router.get("/api/workflows/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """Live status from registry (if running) or DB."""
    registry = get_registry()
    running = registry.get(workflow_id)

    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    row = await deps.pool.fetchrow(
        """SELECT status, total_tasks, completed_tasks, failed_tasks
           FROM workflows WHERE id = $1""",
        workflow_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=row["status"],
        progress={
            "completed": row["completed_tasks"],
            "failed": row["failed_tasks"],
            "total": row["total_tasks"],
        },
        is_live=running is not None,
    )


@router.post("/api/workflows/{workflow_id}/cancel", response_model=CancelResponse)
async def cancel_workflow(workflow_id: str) -> CancelResponse:
    """Cancel a running workflow.

    If the workflow has an active orchestrator, signal it to cancel.
    If not (orphaned/crashed), update the DB directly so the workflow
    doesn't stay stuck in 'in_progress' forever.
    """
    registry = get_registry()
    running = registry.get(workflow_id)

    if running and running.orchestrator:
        running.orchestrator.cancel()

    deps = get_deps()
    if deps.pool:
        result = await deps.pool.execute(
            """UPDATE workflows SET status = 'cancelled', completed_at = now()
               WHERE id = $1 AND status NOT IN ('completed', 'failed', 'cancelled')""",
            workflow_id,
        )
        # If no rows updated and no running orchestrator, the workflow is already terminal
        if not running and result == "UPDATE 0":
            raise HTTPException(status_code=409, detail="Workflow is already in a terminal state")

    return CancelResponse(workflow_id=workflow_id, status="cancelled")


@router.post("/api/workflows/{workflow_id}/retry")
async def retry_workflow(workflow_id: str, body: RetryRequest = RetryRequest()) -> dict:
    """Retry a workflow.

    replan=false (default): Reset failed tasks to PENDING, resume same workflow.
        Passed tasks are preserved; only failed tasks re-execute.
    replan=true: Create a new workflow from the original spec (full restart).
    """
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    if body.replan:
        # Full restart: new workflow from original spec
        row = await deps.pool.fetchrow(
            "SELECT spec_yaml, spec_metadata FROM workflows WHERE id = $1",
            workflow_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Workflow not found")

        metadata = json.loads(row["spec_metadata"]) if row["spec_metadata"] else {}
        description = metadata.get("goal", metadata.get("title", "Retry workflow"))

        from rooben.dashboard.workflow_launcher import launch_workflow
        new_id = await launch_workflow(description=description, spec_yaml=row["spec_yaml"])
        return {"workflow_id": new_id, "status": "started", "replan": True}

    # Partial retry: reset failed tasks to PENDING, resume same workflow.
    # Verify workflow exists and is in a retryable state
    wf_row = await deps.pool.fetchrow(
        "SELECT id, status FROM workflows WHERE id = $1", workflow_id,
    )
    if not wf_row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf_row["status"] not in ("failed", "completed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry workflow in '{wf_row['status']}' state",
        )

    # Prevent duplicate retries if already running
    registry = get_registry()
    if registry.get(workflow_id) is not None:
        raise HTTPException(status_code=409, detail="Workflow is already running")
    # Reset failed/cancelled tasks to PENDING
    result = await deps.pool.fetch(
        """UPDATE tasks SET status = 'pending', attempt = 0,
                            error = NULL, result = NULL
           WHERE workflow_id = $1 AND status IN ('failed', 'cancelled')
           RETURNING id""",
        workflow_id,
    )
    reset_ids = [r["id"] for r in result]

    # Also check for already-pending tasks (e.g., from removed cascade cancel)
    pending_count = await deps.pool.fetchval(
        "SELECT COUNT(*) FROM tasks WHERE workflow_id = $1 AND status = 'pending'",
        workflow_id,
    )
    if not reset_ids and not pending_count:
        raise HTTPException(status_code=400, detail="No retryable tasks found")

    await deps.pool.execute(
        """UPDATE workflows SET status = 'in_progress', failed_tasks = 0,
                                completed_at = NULL
           WHERE id = $1""",
        workflow_id,
    )

    from rooben.dashboard.workflow_launcher import resume_workflow
    await resume_workflow(workflow_id)

    return {"workflow_id": workflow_id, "status": "resuming", "reset_tasks": reset_ids}


class DeleteResponse(BaseModel):
    workflow_id: str
    status: str
    workspace_cleaned: bool


@router.delete("/api/workflows/{workflow_id}", response_model=DeleteResponse)
async def delete_workflow(workflow_id: str) -> DeleteResponse:
    """Delete a workflow and clean up its workspace."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    # Look up workspace_dir before deleting
    row = await deps.pool.fetchrow(
        "SELECT status, workspace_dir FROM workflows WHERE id = $1",
        workflow_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Don't delete running workflows
    if row["status"] in ("planning", "in_progress"):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a running workflow. Cancel it first.",
        )

    # Clean up workspace directory
    workspace_cleaned = False
    if row["workspace_dir"]:
        storage = deps.workspace_storage
        try:
            await storage.cleanup(row["workspace_dir"])
            workspace_cleaned = True
        except Exception:
            pass  # Non-fatal — DB records still get deleted

    # Delete DB records (tasks, workstreams, workflow)
    await deps.pool.execute(
        "DELETE FROM tasks WHERE workflow_id = $1", workflow_id
    )
    await deps.pool.execute(
        "DELETE FROM workstreams WHERE workflow_id = $1", workflow_id
    )
    await deps.pool.execute(
        "DELETE FROM workflows WHERE id = $1", workflow_id
    )

    return DeleteResponse(
        workflow_id=workflow_id,
        status="deleted",
        workspace_cleaned=workspace_cleaned,
    )


@router.get("/api/workflows/{workflow_id}/events")
async def workflow_events_sse(workflow_id: str):
    """SSE stream of events for a specific workflow."""
    try:
        from sse_starlette.sse import EventSourceResponse
    except ImportError:
        raise HTTPException(status_code=501, detail="sse-starlette not installed")

    from rooben.dashboard.routes.events import broadcaster

    async def event_generator():
        async for event in broadcaster.subscribe(workflow_id):
            yield {
                "event": event.get("type", "message"),
                "data": json.dumps(event, default=str),
            }

    return EventSourceResponse(event_generator())
