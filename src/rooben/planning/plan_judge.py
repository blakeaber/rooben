"""LLM-based plan quality judge — catches semantic issues that heuristics miss."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from rooben.domain import TokenUsage, WorkflowState
from rooben.planning.provider import LLMProvider
from rooben.spec.models import Specification
from rooben.utils import parse_llm_json

log = structlog.get_logger()

JUDGE_SYSTEM_PROMPT = """\
You are a plan quality judge for an autonomous agent orchestration system.

You evaluate whether a proposed task plan can be successfully executed by AI agents.
Each task will be executed by a single agent in a single context window (~200k tokens).

Evaluate each task on these criteria:

1. **Atomicity** — Can one agent complete this in a single execution? Flag tasks whose \
descriptions contain multiple independent work items (e.g., "Design X AND implement Y AND test Z").

2. **Scope proportionality** — Does any single task account for a disproportionate share of \
the total work? Tasks that try to accomplish too much will produce vague, incomplete output.

3. **Redundancy** — Are any tasks duplicative of each other?

4. **Feasibility** — Can each task's acceptance criteria realistically be verified from the output?

Output strict JSON:
{
  "score": 0.0-1.0,
  "approved": true/false,
  "issues": [
    {
      "task_id": "task-xxx",
      "severity": "high" | "medium" | "low",
      "reason": "string — why this task is problematic",
      "suggestion": "string — how to fix it (e.g., decompose into X and Y)"
    }
  ]
}

Score guidelines:
- 1.0: All tasks are atomic, well-scoped, non-redundant, and feasible
- 0.7-0.9: Minor issues (low/medium severity) but executable
- 0.4-0.6: Significant issues — some tasks need decomposition
- 0.0-0.3: Plan is fundamentally flawed — most tasks are non-atomic or infeasible

Output ONLY the JSON object. No markdown fences, no commentary.
Approve the plan if there are no high-severity issues.
"""


@dataclass
class PlanIssue:
    """A single issue found by the plan judge."""
    task_id: str
    severity: str  # "high", "medium", "low"
    reason: str
    suggestion: str


@dataclass
class PlanJudgeResult:
    """Result of LLM plan quality evaluation."""
    approved: bool
    score: float = 1.0  # 0.0–1.0, like VerificationResult.score
    issues: list[PlanIssue] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


class PlanJudge:
    """Evaluates plan quality using an LLM to catch semantic issues."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def judge(
        self,
        state: WorkflowState,
        spec: Specification,
        workflow_id: str,
    ) -> PlanJudgeResult:
        tasks = [t for t in state.tasks.values() if t.workflow_id == workflow_id]
        if not tasks:
            return PlanJudgeResult(approved=True, score=1.0)

        prompt = self._build_prompt(tasks, spec)
        log.info("plan_judge.evaluating", task_count=len(tasks))

        gen_result = await self._provider.generate(
            system=JUDGE_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=4096,
        )

        data = parse_llm_json(gen_result.text)
        if data is None:
            log.warning("plan_judge.parse_failed", raw=gen_result.text[:300])
            return PlanJudgeResult(approved=True, score=1.0, usage=gen_result.usage)

        issues = [
            PlanIssue(
                task_id=issue.get("task_id", "unknown"),
                severity=issue.get("severity", "medium"),
                reason=issue.get("reason", ""),
                suggestion=issue.get("suggestion", ""),
            )
            for issue in data.get("issues", [])
        ]

        approved = data.get("approved", len([i for i in issues if i.severity == "high"]) == 0)
        score = max(0.0, min(1.0, float(data.get("score", 1.0 if approved else 0.0))))

        log.info(
            "plan_judge.result",
            approved=approved,
            score=score,
            issue_count=len(issues),
            high_severity=len([i for i in issues if i.severity == "high"]),
        )

        return PlanJudgeResult(
            approved=approved,
            score=score,
            issues=issues,
            usage=gen_result.usage,
        )

    def _build_prompt(self, tasks: list, spec: Specification) -> str:
        task_descriptions = []
        for task in tasks:
            criteria_ids = getattr(task, "acceptance_criteria_ids", []) or []
            task_descriptions.append(
                f"### {task.id}: {task.title}\n"
                f"Agent: {task.assigned_agent_id}\n"
                f"Description: {task.description}\n"
                f"Depends on: {', '.join(task.depends_on) or 'none'}\n"
                f"Acceptance criteria IDs: {', '.join(criteria_ids) or 'none'}\n"
            )

        deliverables = "\n".join(
            f"- {d.id}: {d.name} — {d.description}"
            for d in spec.deliverables
        )

        return (
            f"# Specification: {spec.title}\n\n"
            f"## Goal\n{spec.goal}\n\n"
            f"## Deliverables\n{deliverables}\n\n"
            f"## Proposed Tasks ({len(tasks)} total)\n\n"
            + "\n".join(task_descriptions)
        )
