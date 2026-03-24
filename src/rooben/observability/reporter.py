"""WorkflowReporter — generates post-execution summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from rooben.domain import TaskStatus, WorkflowState


@dataclass
class WorkflowReport:
    """Structured workflow execution report."""
    workflow_id: str
    status: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_tokens: int = 0
    total_cost_usd: Decimal = Decimal("0")
    wall_seconds: float = 0.0
    per_agent_tokens: dict[str, int] = field(default_factory=dict)
    per_agent_tasks: dict[str, int] = field(default_factory=dict)
    task_success_rate: float = 0.0
    average_attempts: float = 0.0
    # R-3.5: Workflow-level evaluation metrics
    parallelism_efficiency: float = 0.0  # sum(task_durations) / wall_time
    retry_rate: float = 0.0  # tasks_with_retries / total_tasks
    critical_path_seconds: float = 0.0  # longest sequential chain duration
    per_agent_success_rate: dict[str, float] = field(default_factory=dict)
    per_agent_avg_seconds: dict[str, float] = field(default_factory=dict)


class WorkflowReporter:
    """
    Generates execution reports from workflow state.

    Works with in-memory state — no database required.
    Can be extended with a Postgres pool for production use.
    """

    def __init__(self, cost_per_million_tokens: Decimal = Decimal("3.0")):
        self._cost_rate = cost_per_million_tokens

    def generate_report(
        self,
        state: WorkflowState,
        workflow_id: str,
        wall_seconds: float = 0.0,
    ) -> WorkflowReport:
        """Generate a report from the current workflow state."""
        wf = state.workflows.get(workflow_id)
        if not wf:
            return WorkflowReport(workflow_id=workflow_id, status="unknown")

        tasks = [
            t for t in state.tasks.values()
            if t.workflow_id == workflow_id
        ]

        total_tokens = 0
        per_agent_tokens: dict[str, int] = {}
        per_agent_tasks: dict[str, int] = {}
        per_agent_passed: dict[str, int] = {}
        per_agent_durations: dict[str, list[float]] = {}
        total_attempts = 0
        tasks_with_retries = 0
        total_task_seconds = 0.0

        for task in tasks:
            attempts = max(task.attempt, 1)
            total_attempts += attempts
            if attempts > 1:
                tasks_with_retries += 1

            agent = task.assigned_agent_id or "unassigned"
            per_agent_tasks[agent] = per_agent_tasks.get(agent, 0) + 1

            if task.status == TaskStatus.PASSED:
                per_agent_passed[agent] = per_agent_passed.get(agent, 0) + 1

            if task.result and task.result.token_usage > 0:
                tokens = task.result.token_usage
                total_tokens += tokens
                per_agent_tokens[agent] = per_agent_tokens.get(agent, 0) + tokens

            # Compute task duration from timestamps
            if task.started_at and task.completed_at:
                duration = (task.completed_at - task.started_at).total_seconds()
                total_task_seconds += duration
                per_agent_durations.setdefault(agent, []).append(duration)

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == TaskStatus.PASSED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        success_rate = completed / max(total, 1)
        avg_attempts = total_attempts / max(total, 1)

        cost = Decimal(total_tokens) * self._cost_rate / Decimal("1000000")

        # R-3.5: Parallelism efficiency = sum(task durations) / wall time
        parallelism_efficiency = (
            total_task_seconds / wall_seconds if wall_seconds > 0 else 0.0
        )

        # R-3.5: Retry rate
        retry_rate = tasks_with_retries / max(total, 1)

        # R-3.5: Critical path — longest chain via dependency graph
        critical_path = self._compute_critical_path(tasks, state)

        # R-3.5: Per-agent success rate and avg duration
        per_agent_success_rate: dict[str, float] = {}
        per_agent_avg_seconds: dict[str, float] = {}
        for agent, count in per_agent_tasks.items():
            per_agent_success_rate[agent] = per_agent_passed.get(agent, 0) / max(count, 1)
            durations = per_agent_durations.get(agent, [])
            per_agent_avg_seconds[agent] = (
                sum(durations) / len(durations) if durations else 0.0
            )

        return WorkflowReport(
            workflow_id=workflow_id,
            status=wf.status.value,
            total_tasks=total,
            completed_tasks=completed,
            failed_tasks=failed,
            total_tokens=total_tokens,
            total_cost_usd=cost.quantize(Decimal("0.0001")),
            wall_seconds=wall_seconds,
            per_agent_tokens=per_agent_tokens,
            per_agent_tasks=per_agent_tasks,
            task_success_rate=success_rate,
            average_attempts=avg_attempts,
            parallelism_efficiency=round(parallelism_efficiency, 2),
            retry_rate=round(retry_rate, 3),
            critical_path_seconds=round(critical_path, 1),
            per_agent_success_rate=per_agent_success_rate,
            per_agent_avg_seconds=per_agent_avg_seconds,
        )

    @staticmethod
    def _compute_critical_path(tasks: list, state: WorkflowState) -> float:
        """Compute the longest sequential chain duration via dependency graph."""
        task_map = {t.id: t for t in tasks}

        def _task_duration(t) -> float:
            if t.started_at and t.completed_at:
                return (t.completed_at - t.started_at).total_seconds()
            return 0.0

        # Memoized longest path to each task
        memo: dict[str, float] = {}

        def _longest_path(task_id: str) -> float:
            if task_id in memo:
                return memo[task_id]
            task = task_map.get(task_id)
            if not task:
                return 0.0
            dep_max = 0.0
            for dep_id in task.depends_on:
                dep_max = max(dep_max, _longest_path(dep_id))
            result = dep_max + _task_duration(task)
            memo[task_id] = result
            return result

        if not tasks:
            return 0.0
        return max(_longest_path(t.id) for t in tasks)

    def format_report(self, report: WorkflowReport) -> str:
        """Format a report as human-readable text."""
        lines = [
            f"Workflow Report: {report.workflow_id}",
            f"Status: {report.status}",
            f"Tasks: {report.completed_tasks}/{report.total_tasks} passed, {report.failed_tasks} failed",
            f"Success Rate: {report.task_success_rate:.1%}",
            f"Avg Attempts: {report.average_attempts:.1f}",
            f"Retry Rate: {report.retry_rate:.1%}",
            f"Total Tokens: {report.total_tokens:,}",
            f"Estimated Cost: ${report.total_cost_usd}",
            f"Wall Time: {report.wall_seconds:.1f}s",
            f"Critical Path: {report.critical_path_seconds:.1f}s",
            f"Parallelism Efficiency: {report.parallelism_efficiency:.1f}x",
        ]
        if report.per_agent_tokens:
            lines.append("\nPer-Agent Performance:")
            for agent in sorted(report.per_agent_tokens.keys()):
                tokens = report.per_agent_tokens[agent]
                tasks = report.per_agent_tasks.get(agent, 0)
                sr = report.per_agent_success_rate.get(agent, 0)
                avg_s = report.per_agent_avg_seconds.get(agent, 0)
                lines.append(
                    f"  {agent}: {tokens:,} tokens, {tasks} tasks, "
                    f"{sr:.0%} success, {avg_s:.1f}s avg"
                )
        return "\n".join(lines)
