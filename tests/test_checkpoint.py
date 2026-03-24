"""Tests for WS-2.3: Checkpoint & Resume."""

from __future__ import annotations

import tempfile

import pytest

from rooben.domain import (
    Task,
    TaskResult,
    TaskStatus,
    Workflow,
    WorkflowState,
    Workstream,
)
from rooben.resilience.checkpoint import CheckpointManager
from rooben.state.filesystem import FilesystemBackend


def _make_state(n_tasks: int = 5, completed: int = 0) -> WorkflowState:
    """Create a WorkflowState with n tasks, first `completed` marked PASSED."""
    state = WorkflowState()
    wf = Workflow(id="wf-1", spec_id="spec-1", total_tasks=n_tasks)
    wf.completed_tasks = completed
    state.workflows["wf-1"] = wf

    ws = Workstream(id="ws-1", workflow_id="wf-1", name="WS", description="d")
    state.workstreams["ws-1"] = ws

    for i in range(n_tasks):
        task = Task(
            id=f"task-{i}",
            workstream_id="ws-1",
            workflow_id="wf-1",
            title=f"Task {i}",
            description="d",
        )
        if i < completed:
            task.status = TaskStatus.PASSED
            task.result = TaskResult(output=f"done {i}")
        state.tasks[task.id] = task

    return state


class TestCheckpointManager:
    @pytest.mark.asyncio
    async def test_checkpoint_at_interval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()
            mgr = CheckpointManager(backend=backend, interval=5)

            state = _make_state(10, completed=5)
            created = await mgr.maybe_checkpoint(state, "wf-1", 5)
            assert created
            assert mgr.checkpoint_count["wf-1"] == 1

    @pytest.mark.asyncio
    async def test_no_checkpoint_below_interval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()
            mgr = CheckpointManager(backend=backend, interval=5)

            state = _make_state(10, completed=3)
            created = await mgr.maybe_checkpoint(state, "wf-1", 3)
            assert not created
            assert mgr.checkpoint_count == {}

    @pytest.mark.asyncio
    async def test_rollback_restores_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()
            mgr = CheckpointManager(backend=backend, interval=5)

            # Checkpoint at 5 completed
            state = _make_state(10, completed=5)
            await mgr.force_checkpoint(state, "wf-1")

            # Now modify state (simulate failure at task 8)
            state.tasks["task-5"].status = TaskStatus.FAILED
            state.tasks["task-6"].status = TaskStatus.IN_PROGRESS

            # Rollback
            restored = await mgr.rollback("wf-1")
            assert restored is not None

            # Completed tasks should still be PASSED
            for i in range(5):
                assert restored.tasks[f"task-{i}"].status == TaskStatus.PASSED

            # Non-terminal tasks should be reset to PENDING
            for i in range(5, 10):
                assert restored.tasks[f"task-{i}"].status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_rollback_returns_none_when_no_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()
            mgr = CheckpointManager(backend=backend, interval=5)

            result = await mgr.rollback("wf-nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_force_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()
            mgr = CheckpointManager(backend=backend, interval=100)  # High interval

            state = _make_state(5, completed=1)
            # Force should work regardless of interval
            await mgr.force_checkpoint(state, "wf-1")
            assert mgr.checkpoint_count["wf-1"] == 1
