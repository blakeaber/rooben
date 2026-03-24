"""Tests for WS-3.2: Adaptive Replanning (PlanChecker)."""

from __future__ import annotations


from rooben.domain import (
    Task,
    Workflow,
    WorkflowState,
    Workstream,
)
from rooben.planning.checker import PlanChecker
from rooben.spec.models import (
    AgentSpec,
    AgentTransport,
    Deliverable,
    DeliverableType,
    Specification,
)


def _spec(agents: list[str] | None = None) -> Specification:
    agent_specs = []
    for aid in (agents or ["agent-1"]):
        agent_specs.append(AgentSpec(
            id=aid, name=aid, transport=AgentTransport.SUBPROCESS,
            description="test",
        ))
    return Specification(
        id="spec-1", title="Test", goal="Test",
        deliverables=[Deliverable(
            id="D-1", name="Out", deliverable_type=DeliverableType.CODE, description="d",
        )],
        agents=agent_specs,
    )


def _state_with_tasks(tasks: list[Task], workflow_id: str = "wf-1") -> WorkflowState:
    state = WorkflowState()
    state.workflows[workflow_id] = Workflow(
        id=workflow_id, spec_id="spec-1", total_tasks=len(tasks),
    )
    state.workstreams["ws-1"] = Workstream(
        id="ws-1", workflow_id=workflow_id, name="WS", description="d",
    )
    for task in tasks:
        state.tasks[task.id] = task
    return state


class TestPlanChecker:
    def test_valid_plan(self):
        tasks = [
            Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                 title="Task 1", description="d", assigned_agent_id="agent-1"),
            Task(id="t-2", workstream_id="ws-1", workflow_id="wf-1",
                 title="Task 2", description="d", assigned_agent_id="agent-1",
                 depends_on=["t-1"]),
        ]
        state = _state_with_tasks(tasks)
        checker = PlanChecker()
        result = checker.check(state, _spec(), "wf-1")
        assert result.valid
        assert len(result.issues) == 0

    def test_detects_cycle(self):
        tasks = [
            Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                 title="Task A", description="d", assigned_agent_id="agent-1",
                 depends_on=["t-2"]),
            Task(id="t-2", workstream_id="ws-1", workflow_id="wf-1",
                 title="Task B", description="d", assigned_agent_id="agent-1",
                 depends_on=["t-1"]),
        ]
        state = _state_with_tasks(tasks)
        checker = PlanChecker()
        result = checker.check(state, _spec(), "wf-1")
        assert not result.valid
        assert any("cycle" in issue.lower() for issue in result.issues)

    def test_detects_unassigned_task(self):
        tasks = [
            Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                 title="Task 1", description="d"),  # No agent
        ]
        state = _state_with_tasks(tasks)
        checker = PlanChecker()
        result = checker.check(state, _spec(), "wf-1")
        assert not result.valid
        assert any("no assigned agent" in issue.lower() for issue in result.issues)

    def test_detects_unknown_agent(self):
        tasks = [
            Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                 title="Task 1", description="d",
                 assigned_agent_id="unknown-agent"),
        ]
        state = _state_with_tasks(tasks)
        checker = PlanChecker()
        result = checker.check(state, _spec(), "wf-1")
        assert not result.valid
        assert any("unknown agent" in issue.lower() for issue in result.issues)

    def test_detects_invalid_dependency(self):
        tasks = [
            Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                 title="Task 1", description="d", assigned_agent_id="agent-1",
                 depends_on=["nonexistent"]),
        ]
        state = _state_with_tasks(tasks)
        checker = PlanChecker()
        result = checker.check(state, _spec(), "wf-1")
        assert not result.valid
        assert any("unknown task" in issue.lower() for issue in result.issues)

    def test_no_tasks(self):
        state = _state_with_tasks([])
        checker = PlanChecker()
        result = checker.check(state, _spec(), "wf-1")
        assert not result.valid
        assert any("no tasks" in issue.lower() for issue in result.issues)

    def test_three_node_cycle(self):
        tasks = [
            Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                 title="A", description="d", assigned_agent_id="agent-1",
                 depends_on=["t-3"]),
            Task(id="t-2", workstream_id="ws-1", workflow_id="wf-1",
                 title="B", description="d", assigned_agent_id="agent-1",
                 depends_on=["t-1"]),
            Task(id="t-3", workstream_id="ws-1", workflow_id="wf-1",
                 title="C", description="d", assigned_agent_id="agent-1",
                 depends_on=["t-2"]),
        ]
        state = _state_with_tasks(tasks)
        checker = PlanChecker()
        result = checker.check(state, _spec(), "wf-1")
        assert not result.valid
        assert any("cycle" in issue.lower() for issue in result.issues)
