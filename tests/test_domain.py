"""Tests for domain models and state management."""

from __future__ import annotations

from rooben.domain import (
    Task,
    TaskStatus,
    Workflow,
    WorkflowState,
    WorkflowStatus,
)
from rooben.planning.checker import PlanChecker
from rooben.spec.models import Specification


class TestTask:
    def test_content_hash_deterministic(self):
        t1 = Task(
            id="t-1",
            workstream_id="ws-1",
            workflow_id="wf-1",
            title="Test",
            description="Do stuff",
        )
        t2 = Task(
            id="t-2",  # Different ID, same content
            workstream_id="ws-1",
            workflow_id="wf-1",
            title="Test",
            description="Do stuff",
        )
        assert t1.content_hash() == t2.content_hash()

    def test_is_terminal(self):
        task = Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1", title="T", description="D")
        assert not task.is_terminal

        task.status = TaskStatus.PASSED
        assert task.is_terminal

        task.status = TaskStatus.FAILED
        assert task.is_terminal

        task.status = TaskStatus.IN_PROGRESS
        assert not task.is_terminal


class TestWorkflowState:
    def _make_state(self) -> WorkflowState:
        state = WorkflowState()
        wf = Workflow(id="wf-1", spec_id="spec-1", status=WorkflowStatus.IN_PROGRESS)
        state.workflows["wf-1"] = wf

        t1 = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="First", description="Do first",
        )
        t2 = Task(
            id="t-2", workstream_id="ws-1", workflow_id="wf-1",
            title="Second", description="Do second",
            depends_on=["t-1"],
        )
        state.register_task(t1)
        state.register_task(t2)
        return state

    def test_get_ready_tasks_initial(self):
        state = self._make_state()
        ready = state.get_ready_tasks("wf-1")
        assert len(ready) == 1
        assert ready[0].id == "t-1"

    def test_get_ready_tasks_after_completion(self):
        state = self._make_state()
        state.tasks["t-1"].status = TaskStatus.PASSED
        ready = state.get_ready_tasks("wf-1")
        # t-2 should now be ready (but it's still PENDING)
        assert len(ready) == 1
        assert ready[0].id == "t-2"

    def test_dedup(self):
        state = WorkflowState()
        t1 = Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1", title="Same", description="Same")
        t2 = Task(id="t-2", workstream_id="ws-1", workflow_id="wf-1", title="Same", description="Same")

        result1 = state.register_task(t1)
        result2 = state.register_task(t2)

        assert result1 is not None
        assert result2 is None  # Duplicate
        assert len(state.tasks) == 1

    def test_is_workflow_complete(self):
        state = self._make_state()
        assert not state.is_workflow_complete("wf-1")

        state.tasks["t-1"].status = TaskStatus.PASSED
        state.tasks["t-2"].status = TaskStatus.PASSED
        assert state.is_workflow_complete("wf-1")

    def test_is_workflow_failed(self):
        state = self._make_state()
        state.tasks["t-1"].status = TaskStatus.FAILED
        state.tasks["t-1"].attempt = 3
        state.tasks["t-1"].max_retries = 3
        assert state.is_workflow_failed("wf-1")

    def test_stalled_simple_chain(self):
        """A→B→C: fail A, verify workflow is stalled (B and C stay PENDING)."""
        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id="s-1")
        t_a = Task(id="a", workstream_id="ws-1", workflow_id="wf-1", title="A", description="")
        t_b = Task(id="b", workstream_id="ws-1", workflow_id="wf-1", title="B", description="", depends_on=["a"])
        t_c = Task(id="c", workstream_id="ws-1", workflow_id="wf-1", title="C", description="", depends_on=["b"])
        state.register_task(t_a)
        state.register_task(t_b)
        state.register_task(t_c)

        state.tasks["a"].status = TaskStatus.FAILED
        assert state.is_workflow_stalled("wf-1") is True
        # Pending tasks stay PENDING (not cancelled) — ready for retry
        assert state.tasks["b"].status == TaskStatus.PENDING
        assert state.tasks["c"].status == TaskStatus.PENDING

    def test_stalled_diamond(self):
        """Diamond: A→B, A→C, B→D, C→D. Fail A → stalled."""
        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id="s-1")
        for tid, deps in [("a", []), ("b", ["a"]), ("c", ["a"]), ("d", ["b", "c"])]:
            state.register_task(Task(
                id=tid, workstream_id="ws-1", workflow_id="wf-1",
                title=tid.upper(), description="", depends_on=deps,
            ))
        state.tasks["a"].status = TaskStatus.FAILED
        assert state.is_workflow_stalled("wf-1") is True

    def test_not_stalled_with_independent_ready(self):
        """A→B, C (independent). Fail A → not stalled because C can still run."""
        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id="s-1")
        state.register_task(Task(id="a", workstream_id="ws-1", workflow_id="wf-1", title="A", description=""))
        state.register_task(Task(id="b", workstream_id="ws-1", workflow_id="wf-1", title="B", description="", depends_on=["a"]))
        state.register_task(Task(id="c", workstream_id="ws-1", workflow_id="wf-1", title="C", description=""))

        state.tasks["a"].status = TaskStatus.FAILED
        # C is PENDING with no deps → can still run → not stalled
        assert state.is_workflow_stalled("wf-1") is False

    def test_not_stalled_when_deps_in_progress(self):
        """A→B: A still PENDING → B waiting but not stalled."""
        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id="s-1")
        state.register_task(Task(id="a", workstream_id="ws-1", workflow_id="wf-1", title="A", description=""))
        state.register_task(Task(id="b", workstream_id="ws-1", workflow_id="wf-1", title="B", description="", depends_on=["a"]))

        # A is still PENDING (not failed) → B is waiting, not stalled
        assert state.is_workflow_stalled("wf-1") is False


class TestPlanCheckerComplexityWarnings:
    """Verify complexity warnings don't block valid plans."""

    def _make_spec_and_state(self, description: str = "short") -> tuple[WorkflowState, Specification, str]:
        """Helper to create a minimal spec + state with one task."""
        from rooben.spec.models import (
            AgentSpec, AgentTransport, Deliverable, DeliverableType,
            SuccessCriteria, Specification,
        )
        spec = Specification(
            id="spec-1",
            title="Test",
            goal="Test goal",
            context="Test context",
            agents=[AgentSpec(
                id="agent-1", name="Agent", description="Test agent",
                capabilities=["code"], transport=AgentTransport.LLM,
            )],
            deliverables=[Deliverable(
                id="D-1", name="Feature", description="A feature",
                deliverable_type=DeliverableType.CODE,
            )],
            success_criteria=SuccessCriteria(),
        )
        state = WorkflowState()
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Build feature", description=description,
            assigned_agent_id="agent-1",
        )
        state.register_task(task)
        state.workstreams["ws-1"] = __import__("rooben.domain", fromlist=["Workstream"]).Workstream(
            id="ws-1", workflow_id="wf-1", name="WS", description="", task_ids=["t-1"],
        )
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id="spec-1")
        return state, spec, "wf-1"

    def test_complexity_only_is_valid(self):
        """Plan with only complexity warnings should be valid=True with score < 1.0."""
        # Create a verbose description that triggers complexity heuristics
        verbose = (
            "First, design the API schema. Then implement the endpoint. "
            "Next, build the frontend component. Also, create the database migration. "
            "Finally, write comprehensive tests and deploy to staging. "
            "Configure the CI pipeline. Document all the changes. "
            "Integrate with the existing authentication system. "
            "Refactor the old code paths. Set up monitoring dashboards. "
        ) * 10  # Make it very long to trigger token count warning too
        state, spec, wf_id = self._make_spec_and_state(verbose)
        checker = PlanChecker()
        result = checker.check(state, spec, wf_id)

        # Should be valid (no structural errors) but with warnings
        assert result.valid is True
        assert result.score < 1.0
        assert len(result.issues) > 0
        # All issues should be complexity-related
        for issue in result.issues:
            assert "tokens" in issue.lower() or "verb" in issue.lower() or "deliverable" in issue.lower() or "criteria" in issue.lower()

    def test_structural_error_is_invalid(self):
        """Plan with structural errors should be valid=False."""
        state, spec, wf_id = self._make_spec_and_state("simple task")
        # Remove the agent assignment to trigger a structural error
        state.tasks["t-1"].assigned_agent_id = None
        checker = PlanChecker()
        result = checker.check(state, spec, wf_id)

        assert result.valid is False
