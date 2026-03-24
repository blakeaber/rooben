"""Filesystem state backend — stores state as JSON files."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from rooben.domain import Task, Workflow, WorkflowState

log = structlog.get_logger()


class FilesystemBackend:
    """
    Stores workflow state as JSON files on disk.

    Layout:
      <base_dir>/
        <workflow_id>/
          state.json      — full WorkflowState snapshot
    """

    def __init__(self, base_dir: str = ".rooben/state"):
        self._base_dir = Path(base_dir)

    async def initialize(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        log.info("filesystem_backend.initialized", path=str(self._base_dir))

    async def save_state(self, state: WorkflowState) -> None:
        for wf_id in state.workflows:
            wf_dir = self._base_dir / wf_id
            wf_dir.mkdir(parents=True, exist_ok=True)
            state_file = wf_dir / "state.json"
            data = state.model_dump(mode="json")
            # Atomic write via temp file + rename
            tmp = state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            tmp.rename(state_file)
        log.debug("filesystem_backend.saved", workflows=list(state.workflows.keys()))

    async def load_state(self, workflow_id: str) -> WorkflowState | None:
        state_file = self._base_dir / workflow_id / "state.json"
        if not state_file.exists():
            return None
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return WorkflowState.model_validate(data)

    async def update_task(self, task: Task) -> None:
        state = await self.load_state(task.workflow_id)
        if state:
            state.tasks[task.id] = task
            await self.save_state(state)

    async def update_workflow(self, workflow: Workflow) -> None:
        state = await self.load_state(workflow.id)
        if state:
            state.workflows[workflow.id] = workflow
            await self.save_state(state)

    async def close(self) -> None:
        pass
