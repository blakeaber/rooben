"""DiagnosticAnalyzer — categorizes failures and detects error patterns."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from rooben.domain import TaskStatus, WorkflowState


# ─── User-friendly error templates ──────────────────────────────────────────

_FRIENDLY_TEMPLATES: dict[str, dict[str, str]] = {
    "timeout": {
        "title": "Some tasks ran out of time",
        "description": (
            "One or more tasks couldn't finish before the time limit. "
            "This usually means the task was too large or the agent got stuck."
        ),
        "suggestion": "Try breaking large tasks into smaller pieces, or increase the time budget.",
    },
    "verification_failure": {
        "title": "Tasks didn't pass quality checks",
        "description": (
            "The output was generated but didn't meet the acceptance criteria. "
            "The agent may need clearer instructions or more retries."
        ),
        "suggestion": "Review acceptance criteria for clarity. You can also increase the retry limit.",
    },
    "execution_error": {
        "title": "Tasks hit errors during execution",
        "description": (
            "Something went wrong while the agent was working. "
            "This could be a tool failure, permission issue, or unexpected input."
        ),
        "suggestion": "Check the error details below for specifics. Common fixes: verify tool access and input data.",
    },
    "dependency_block": {
        "title": "Tasks were blocked by earlier failures",
        "description": (
            "These tasks couldn't run because a task they depend on failed first. "
            "Fix the upstream failure and they should resolve automatically."
        ),
        "suggestion": "Look at the failed tasks above — fixing those will unblock the dependent tasks.",
    },
}


@dataclass
class UserFriendlyDiagnostic:
    """A single human-readable diagnostic item for the dashboard."""

    category: str
    severity: str  # "error" | "warning" | "info"
    title: str
    description: str
    suggestion: str
    affected_task_count: int
    affected_task_ids: list[str] = field(default_factory=list)


@dataclass
class DiagnosticReport:
    """Structured diagnostic report for failed workflows."""

    workflow_id: str
    failure_categories: dict[str, list[str]] = field(default_factory=dict)
    common_error_patterns: list[tuple[str, int]] = field(default_factory=list)
    agent_failure_rates: dict[str, tuple[int, int]] = field(default_factory=dict)
    recommendation: str = ""


_TIMEOUT_KEYWORDS = ("timeout", "timed out", "exceeded maximum", "budget exceeded")


class DiagnosticAnalyzer:
    """Analyzes workflow failures and produces actionable diagnostics."""

    def analyze(self, state: WorkflowState, workflow_id: str) -> DiagnosticReport:
        """Categorize failures, detect patterns, and generate recommendations."""
        tasks = [
            t for t in state.tasks.values()
            if t.workflow_id == workflow_id
        ]

        categories: dict[str, list[str]] = {
            "execution_error": [],
            "verification_failure": [],
            "timeout": [],
            "dependency_block": [],
            "unknown": [],
        }

        # Per-agent pass/fail counts
        agent_pass: Counter[str] = Counter()
        agent_fail: Counter[str] = Counter()
        error_snippets: list[str] = []

        for task in tasks:
            agent = task.assigned_agent_id or "unassigned"

            if task.status == TaskStatus.PASSED:
                agent_pass[agent] += 1
                continue

            if task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                continue

            # Categorize
            if task.status == TaskStatus.CANCELLED:
                categories["dependency_block"].append(task.id)
                agent_fail[agent] += 1
                continue

            error_text = ""
            if task.result and task.result.error:
                error_text = task.result.error

            if error_text and any(kw in error_text.lower() for kw in _TIMEOUT_KEYWORDS):
                categories["timeout"].append(task.id)
            elif task.attempt_feedback and any(not fb.passed for fb in task.attempt_feedback):
                categories["verification_failure"].append(task.id)
            elif error_text:
                categories["execution_error"].append(task.id)
            else:
                categories["unknown"].append(task.id)

            agent_fail[agent] += 1

            if error_text:
                error_snippets.append(error_text[:100])

        # Detect common error patterns (appearing 2+ times)
        pattern_counts = Counter(error_snippets)
        common_patterns = [
            (pattern, count)
            for pattern, count in pattern_counts.most_common(10)
            if count >= 2
        ]

        # Build agent failure rates
        all_agents = set(agent_pass) | set(agent_fail)
        agent_rates = {
            agent: (agent_pass[agent], agent_fail[agent])
            for agent in sorted(all_agents)
        }

        # Generate recommendation
        recommendation = self._generate_recommendation(categories, common_patterns)

        # Strip empty categories
        categories = {k: v for k, v in categories.items() if v}

        return DiagnosticReport(
            workflow_id=workflow_id,
            failure_categories=categories,
            common_error_patterns=common_patterns,
            agent_failure_rates=agent_rates,
            recommendation=recommendation,
        )

    def _generate_recommendation(
        self,
        categories: dict[str, list[str]],
        common_patterns: list[tuple[str, int]],
    ) -> str:
        parts: list[str] = []

        if categories["timeout"]:
            parts.append(
                f"{len(categories['timeout'])} task(s) timed out. "
                "Consider increasing --wall-time or simplifying task scope."
            )
        if categories["dependency_block"]:
            parts.append(
                f"{len(categories['dependency_block'])} task(s) cancelled due to dependency failures. "
                "Fix upstream tasks first."
            )
        if categories["verification_failure"]:
            parts.append(
                f"{len(categories['verification_failure'])} task(s) failed verification. "
                "Check acceptance criteria clarity or increase max retries."
            )
        if categories["execution_error"]:
            parts.append(
                f"{len(categories['execution_error'])} task(s) hit execution errors."
            )
        if common_patterns:
            top = common_patterns[0]
            parts.append(
                f"Repeated error pattern ({top[1]}x): \"{top[0]}...\""
            )

        return " ".join(parts) if parts else "No specific recommendation."

    def format_user_friendly(self, report: DiagnosticReport) -> list[UserFriendlyDiagnostic]:
        """Convert a DiagnosticReport into user-friendly diagnostic items."""
        items: list[UserFriendlyDiagnostic] = []

        for category, task_ids in report.failure_categories.items():
            template = _FRIENDLY_TEMPLATES.get(category)
            if not template:
                items.append(UserFriendlyDiagnostic(
                    category=category,
                    severity="warning",
                    title=f"{len(task_ids)} task(s) failed",
                    description="An unexpected issue occurred.",
                    suggestion="Check the task details for more information.",
                    affected_task_count=len(task_ids),
                    affected_task_ids=task_ids[:10],
                ))
                continue

            severity = "error" if category in ("execution_error", "timeout") else "warning"
            items.append(UserFriendlyDiagnostic(
                category=category,
                severity=severity,
                title=template["title"],
                description=template["description"],
                suggestion=template["suggestion"],
                affected_task_count=len(task_ids),
                affected_task_ids=task_ids[:10],
            ))

        # Add agent-specific warnings for high failure rates
        for agent, (passed, failed) in report.agent_failure_rates.items():
            total = passed + failed
            if total >= 2 and failed / total > 0.5:
                items.append(UserFriendlyDiagnostic(
                    category="agent_reliability",
                    severity="warning",
                    title=f"Agent \"{agent}\" is struggling",
                    description=(
                        f"This agent failed {failed} out of {total} tasks. "
                        "It may need different tools or a clearer role definition."
                    ),
                    suggestion="Consider reviewing the agent's capabilities and task assignments.",
                    affected_task_count=failed,
                ))

        return items

    def format_report(self, report: DiagnosticReport) -> str:
        """Format a diagnostic report as human-readable text."""
        lines = [
            f"\nDiagnostic Report: {report.workflow_id}",
            "─" * 40,
        ]

        if report.failure_categories:
            lines.append("Failure Categories:")
            for category, task_ids in report.failure_categories.items():
                label = category.replace("_", " ").title()
                lines.append(f"  {label}: {len(task_ids)} task(s)")
                for tid in task_ids[:5]:  # Show max 5 per category
                    lines.append(f"    - {tid}")
                if len(task_ids) > 5:
                    lines.append(f"    ... and {len(task_ids) - 5} more")

        if report.agent_failure_rates:
            lines.append("\nAgent Failure Rates:")
            for agent, (passed, failed) in report.agent_failure_rates.items():
                total = passed + failed
                rate = failed / max(total, 1)
                lines.append(f"  {agent}: {passed}/{total} passed ({rate:.0%} failure rate)")

        if report.common_error_patterns:
            lines.append("\nCommon Error Patterns:")
            for pattern, count in report.common_error_patterns[:5]:
                lines.append(f"  ({count}x) {pattern}")

        if report.recommendation:
            lines.append(f"\nRecommendation: {report.recommendation}")

        return "\n".join(lines)
