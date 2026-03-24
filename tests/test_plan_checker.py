"""Tests for PlanChecker task complexity heuristics."""

from __future__ import annotations


from rooben.domain import Task, WorkflowState, Workflow, Workstream
from rooben.planning.checker import PlanChecker


def _make_state(tasks: list[Task], workflow_id: str = "wf-test") -> WorkflowState:
    """Build a minimal WorkflowState from a list of tasks."""
    state = WorkflowState()
    ws = Workstream(id="ws-1", workflow_id=workflow_id, name="WS", description="")
    for task in tasks:
        state.tasks[task.id] = task
        ws.task_ids.append(task.id)
    state.workstreams["ws-1"] = ws
    state.workflows[workflow_id] = Workflow(
        id=workflow_id, spec_id="spec-1", status="planning",
    )
    return state


class TestTaskComplexityHeuristics:
    def setup_method(self):
        self.checker = PlanChecker()

    def test_short_description_passes(self, sample_spec):
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Simple task", description="Implement a hello endpoint",
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        assert result.valid
        assert result.score == 1.0

    def test_long_description_flagged(self, sample_spec):
        # ~600 tokens = ~2400 chars
        long_desc = "Implement the following module with these requirements. " * 60
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Oversized task", description=long_desc,
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        # Complexity warnings are advisory — plan is still valid
        assert result.valid
        assert result.score < 1.0
        assert any("token" in issue.lower() for issue in result.issues)

    def test_too_many_acceptance_criteria_flagged(self, sample_spec):
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Multi-criteria task", description="Do stuff",
            assigned_agent_id="agent-1",
            acceptance_criteria_ids=["AC-001", "AC-002", "AC-003", "AC-004"],
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        # Complexity warnings are advisory — plan is still valid
        assert result.valid
        assert any("acceptance criteria" in issue.lower() for issue in result.issues)

    def test_three_criteria_passes(self, sample_spec):
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Task", description="Do stuff",
            assigned_agent_id="agent-1",
            acceptance_criteria_ids=["AC-001", "AC-002", "AC-003"],
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        assert result.valid

    def test_many_action_verbs_flagged(self, sample_spec):
        desc = (
            "Design the system architecture, implement the core module, "
            "test all endpoints, and deploy to production."
        )
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Kitchen sink task", description=desc,
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        # Complexity warnings are advisory — plan is still valid
        assert result.valid
        assert any("action verb" in issue.lower() for issue in result.issues)

    def test_two_action_verbs_passes(self, sample_spec):
        desc = "Design the API schema and implement the endpoints."
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Two-verb task", description=desc,
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        assert result.valid

    def test_deliverable_overload_flagged(self, sample_spec):
        desc = (
            "This task covers D-001, D-002, and D-003 deliverables. "
            "Implement all three modules."
        )
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Multi-deliverable task", description=desc,
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        # Complexity warnings are advisory — plan is still valid
        assert result.valid
        assert any("deliverable" in issue.lower() for issue in result.issues)

    def test_two_deliverable_refs_passes(self, sample_spec):
        desc = "This task covers D-001 and D-002."
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Task", description=desc,
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        assert result.valid

    def test_combined_oversized_task_scenario(self, sample_spec):
        """The real-world scenario: a task that is too large on multiple axes."""
        desc = (
            "Design the system architecture with 5 modules including user auth, "
            "data pipeline, API gateway, notification service, and analytics dashboard. "
            "Implement class structures for each module with proper inheritance hierarchies. "
            "Create API interfaces between all modules. Test the integration points. "
            "Document the architecture decisions and deploy the infrastructure. "
            "This covers deliverables D-001, D-002, D-003, and D-004."
        )
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Design System Architecture and Core Components",
            description=desc,
            assigned_agent_id="agent-1",
            acceptance_criteria_ids=["AC-001", "AC-002", "AC-003", "AC-004", "AC-005"],
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        # Complexity warnings are advisory — plan is still valid
        assert result.valid
        # Should flag multiple issues and score low
        assert len(result.issues) >= 2
        assert result.score < 0.8

    def test_score_degrades_more_for_structural_issues(self, sample_spec):
        """Structural issues (missing agent) penalize harder than complexity warnings."""
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Task", description="Do stuff",
            assigned_agent_id=None,  # structural issue
        )
        state = _make_state([task])
        result = self.checker.check(state, sample_spec, "wf-test")
        assert not result.valid
        assert result.score <= 0.75  # structural = -0.25 each
