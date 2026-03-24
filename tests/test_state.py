"""Tests for state backends."""

from __future__ import annotations

import tempfile

import pytest

from rooben.domain import Task, TaskStatus, Workflow, WorkflowState, WorkflowStatus, Workstream
from rooben.state.filesystem import FilesystemBackend


class TestFilesystemBackend:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()

            state = WorkflowState()
            wf = Workflow(id="wf-1", spec_id="spec-1", status=WorkflowStatus.IN_PROGRESS)
            state.workflows["wf-1"] = wf
            ws = Workstream(id="ws-1", workflow_id="wf-1", name="Test", description="Test WS")
            state.workstreams["ws-1"] = ws
            task = Task(
                id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                title="Test Task", description="Do test",
            )
            state.register_task(task)

            await backend.save_state(state)
            loaded = await backend.load_state("wf-1")

            assert loaded is not None
            assert "wf-1" in loaded.workflows
            assert "t-1" in loaded.tasks
            assert loaded.tasks["t-1"].title == "Test Task"

    @pytest.mark.asyncio
    async def test_update_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()

            state = WorkflowState()
            wf = Workflow(id="wf-1", spec_id="spec-1")
            state.workflows["wf-1"] = wf
            task = Task(
                id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                title="Task", description="Desc",
            )
            state.register_task(task)
            await backend.save_state(state)

            # Update the task
            task.status = TaskStatus.PASSED
            await backend.update_task(task)

            loaded = await backend.load_state("wf-1")
            assert loaded is not None
            assert loaded.tasks["t-1"].status == TaskStatus.PASSED

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(base_dir=tmpdir)
            await backend.initialize()
            result = await backend.load_state("does-not-exist")
            assert result is None
