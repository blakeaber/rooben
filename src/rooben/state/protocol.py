"""State backend protocol."""

from __future__ import annotations

from typing import Protocol

from rooben.domain import Task, Workflow, WorkflowState


class StateBackend(Protocol):
    """Persistent storage for workflow orchestration state."""

    async def initialize(self) -> None:
        """Set up storage (create tables, directories, etc.)."""
        ...

    async def save_state(self, state: WorkflowState) -> None:
        """Persist the full workflow state atomically."""
        ...

    async def load_state(self, workflow_id: str) -> WorkflowState | None:
        """Load state for a specific root workflow. Returns None if not found."""
        ...

    async def update_task(self, task: Task) -> None:
        """Update a single task's state (optimized path for frequent updates)."""
        ...

    async def update_workflow(self, workflow: Workflow) -> None:
        """Update a single workflow's state."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
