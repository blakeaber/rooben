"""Task API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps
from rooben.dashboard.queries import tasks as task_queries

router = APIRouter(tags=["tasks"])


class UpdateTaskRequest(BaseModel):
    assigned_agent_id: str | None = None
    title: str | None = None
    description: str | None = None
    depends_on: list[str] | None = None
    priority: int | None = None


@router.get("/api/workflows/{workflow_id}/tasks")
async def get_workflow_tasks(workflow_id: str):
    deps = get_deps()
    tasks = await task_queries.get_workflow_tasks(deps.pool, workflow_id)
    return {"tasks": tasks}


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    deps = get_deps()
    task = await task_queries.get_task(deps.pool, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}


@router.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, req: UpdateTaskRequest):
    """Update a task (only pending/blocked/ready tasks can be edited)."""
    deps = get_deps()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await task_queries.update_task(deps.pool, task_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"updated": True, **result}
