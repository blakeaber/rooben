"""Tests for WS-4.2: Observability (WorkflowReporter)."""

from __future__ import annotations

from decimal import Decimal

from rooben.domain import (
    Task,
    TaskResult,
    TaskStatus,
    Workflow,
    WorkflowState,
    WorkflowStatus,
    Workstream,
)
from rooben.observability.reporter import WorkflowReporter


def _make_state() -> WorkflowState:
    state = WorkflowState()
    state.workflows["wf-1"] = Workflow(
        id="wf-1", spec_id="spec-1", status=WorkflowStatus.COMPLETED,
        total_tasks=5, completed_tasks=4, failed_tasks=1,
    )
    state.workstreams["ws-1"] = Workstream(
        id="ws-1", workflow_id="wf-1", name="WS", description="d",
    )
    # 4 passed tasks, 1 failed
    for i in range(4):
        state.tasks[f"t-{i}"] = Task(
            id=f"t-{i}", workstream_id="ws-1", workflow_id="wf-1",
            title=f"Task {i}", description="d",
            status=TaskStatus.PASSED,
            assigned_agent_id="agent-a" if i < 2 else "agent-b",
            result=TaskResult(output="done", token_usage=1000 * (i + 1)),
        )
    state.tasks["t-4"] = Task(
        id="t-4", workstream_id="ws-1", workflow_id="wf-1",
        title="Failed Task", description="d",
        status=TaskStatus.FAILED,
        assigned_agent_id="agent-b",
        result=TaskResult(output="", error="Error", token_usage=500),
    )
    return state


class TestWorkflowReporter:
    def test_report_generation(self):
        state = _make_state()
        reporter = WorkflowReporter(cost_per_million_tokens=Decimal("3.0"))
        report = reporter.generate_report(state, "wf-1", wall_seconds=10.5)

        assert report.workflow_id == "wf-1"
        assert report.status == "completed"
        assert report.total_tasks == 5
        assert report.completed_tasks == 4
        assert report.failed_tasks == 1
        assert report.total_tokens == 10500  # 1000+2000+3000+4000+500
        assert report.wall_seconds == 10.5

    def test_cost_calculation(self):
        state = _make_state()
        reporter = WorkflowReporter(cost_per_million_tokens=Decimal("3.0"))
        report = reporter.generate_report(state, "wf-1")

        # 10500 tokens * $3/million = $0.0315
        expected = Decimal("10500") * Decimal("3.0") / Decimal("1000000")
        assert report.total_cost_usd == expected.quantize(Decimal("0.0001"))

    def test_per_agent_breakdown(self):
        state = _make_state()
        reporter = WorkflowReporter()
        report = reporter.generate_report(state, "wf-1")

        assert "agent-a" in report.per_agent_tokens
        assert "agent-b" in report.per_agent_tokens
        # agent-a: task 0 (1000) + task 1 (2000) = 3000
        assert report.per_agent_tokens["agent-a"] == 3000
        # agent-b: task 2 (3000) + task 3 (4000) + task 4 (500) = 7500
        assert report.per_agent_tokens["agent-b"] == 7500

    def test_format_report(self):
        state = _make_state()
        reporter = WorkflowReporter()
        report = reporter.generate_report(state, "wf-1", wall_seconds=5.0)
        formatted = reporter.format_report(report)
        assert "wf-1" in formatted
        assert "4/5 passed" in formatted
        assert "agent-a" in formatted

    def test_success_rate(self):
        state = _make_state()
        reporter = WorkflowReporter()
        report = reporter.generate_report(state, "wf-1")
        assert report.task_success_rate == 0.8  # 4/5
