"""Checkpoint manager — periodic state snapshots for rollback."""

from __future__ import annotations

import structlog

from rooben.domain import TaskStatus, WorkflowState
from rooben.state.protocol import StateBackend

log = structlog.get_logger()


class CheckpointManager:
    """
    Periodically snapshots workflow state for rollback capability.

    Checkpoints are stored as full WorkflowState snapshots in the backend.
    """

    def __init__(self, backend: StateBackend, interval: int = 5):
        self._backend = backend
        self._interval = interval
        self._checkpoints: dict[str, list[WorkflowState]] = {}  # workflow_id -> snapshots

    async def maybe_checkpoint(
        self, state: WorkflowState, workflow_id: str, completed_count: int
    ) -> bool:
        """Create a checkpoint if completed_count hits the interval. Returns True if created."""
        if self._interval <= 0 or completed_count == 0:
            return False
        if completed_count % self._interval != 0:
            return False

        await self._save_checkpoint(state, workflow_id)
        return True

    async def force_checkpoint(self, state: WorkflowState, workflow_id: str) -> None:
        """Create a checkpoint unconditionally (e.g. before circuit breaker pause)."""
        await self._save_checkpoint(state, workflow_id)

    async def rollback(self, workflow_id: str) -> WorkflowState | None:
        """Rollback to the most recent checkpoint. Returns restored state or None."""
        checkpoints = self._checkpoints.get(workflow_id, [])
        if not checkpoints:
            log.warning("checkpoint.no_checkpoints", workflow_id=workflow_id)
            return None

        snapshot = checkpoints[-1]
        # Reset non-terminal tasks to PENDING so they can be re-dispatched
        for task in snapshot.tasks.values():
            if task.workflow_id == workflow_id and not task.is_terminal:
                task.status = TaskStatus.PENDING

        log.info(
            "checkpoint.rollback",
            workflow_id=workflow_id,
            checkpoint_index=len(checkpoints) - 1,
        )
        return snapshot

    @property
    def checkpoint_count(self) -> dict[str, int]:
        """Return count of checkpoints per workflow."""
        return {wf_id: len(cps) for wf_id, cps in self._checkpoints.items()}

    async def _save_checkpoint(self, state: WorkflowState, workflow_id: str) -> None:
        # Deep copy via serialization round-trip
        snapshot = WorkflowState.model_validate(state.model_dump())
        if workflow_id not in self._checkpoints:
            self._checkpoints[workflow_id] = []
        self._checkpoints[workflow_id].append(snapshot)

        # Also persist to backend
        await self._backend.save_state(state)
        log.info(
            "checkpoint.created",
            workflow_id=workflow_id,
            checkpoint_number=len(self._checkpoints[workflow_id]),
        )
