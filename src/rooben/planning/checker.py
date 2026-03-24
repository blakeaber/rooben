"""Plan checker — validates planner output for correctness."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from rooben.domain import WorkflowState
from rooben.spec.models import Specification


# Action verbs that indicate distinct work items
_ACTION_VERBS = re.compile(
    r"\b(design|implement|build|create|develop|test|deploy|document|"
    r"integrate|configure|set up|write|refactor|migrate)\b",
    re.IGNORECASE,
)

# Rough token estimate: ~4 chars per token
_CHARS_PER_TOKEN = 4
_MAX_DESCRIPTION_TOKENS = 500
_MAX_ACCEPTANCE_CRITERIA = 3
_MAX_ACTION_VERBS = 3
_MAX_DELIVERABLE_REFS = 2


@dataclass
class CheckResult:
    """Result of validating a plan."""
    valid: bool
    score: float = 1.0  # 0.0–1.0, like VerificationResult.score
    issues: list[str] = field(default_factory=list)


class PlanChecker:
    """
    Deterministic plan validation.

    Checks:
    1. All deliverables have at least one task covering them
    2. No dependency cycles
    3. No unassigned tasks (all have assigned_agent_id)
    4. All dependency references are valid task IDs
    5. All agent IDs exist in the spec
    6. Task complexity heuristics (description length, criteria count, action verbs, deliverable refs)
    """

    def check(
        self,
        state: WorkflowState,
        spec: Specification,
        workflow_id: str,
    ) -> CheckResult:
        issues: list[str] = []

        tasks = [t for t in state.tasks.values() if t.workflow_id == workflow_id]

        if not tasks:
            issues.append("Plan has no tasks")
            return CheckResult(valid=False, issues=issues)

        # 1. Unassigned tasks
        for task in tasks:
            if not task.assigned_agent_id:
                issues.append(f"Task '{task.title}' ({task.id}) has no assigned agent")

        # 2. Invalid agent IDs
        agent_ids = {a.id for a in spec.agents}
        for task in tasks:
            if task.assigned_agent_id and task.assigned_agent_id not in agent_ids:
                issues.append(
                    f"Task '{task.title}' assigned to unknown agent "
                    f"'{task.assigned_agent_id}'"
                )

        # 3. Invalid dependency references
        task_ids = {t.id for t in tasks}
        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id not in task_ids:
                    issues.append(
                        f"Task '{task.title}' depends on unknown task '{dep_id}'"
                    )

        # 4. Cycle detection via topological sort
        cycle = self._detect_cycle(tasks)
        if cycle:
            issues.append(f"Dependency cycle detected: {' → '.join(cycle)}")

        # 5. Deliverable coverage (advisory — not a hard failure)
        # Skip this check if spec has no acceptance_criteria_ids to match

        # 6. Task complexity heuristics
        agents_by_id = {a.id: a for a in spec.agents}
        complexity_issues = self._check_task_complexity(tasks, agents_by_id)
        issues.extend(complexity_issues)

        # Compute score: 1.0 = perfect, deduct per issue, floor at 0.0
        # Structural issues (checks 1-4) are more severe than complexity warnings
        structural_count = len(issues) - len(complexity_issues)
        score = max(0.0, 1.0 - (structural_count * 0.25) - (len(complexity_issues) * 0.1))

        return CheckResult(valid=structural_count == 0, score=score, issues=issues)

    def _check_task_complexity(self, tasks: list, agents_by_id: dict | None = None) -> list[str]:
        """Flag tasks that are likely too large to execute atomically."""
        from rooben.agents.heuristics import CHARS_PER_PAGE, estimate_requested_output_chars

        issues: list[str] = []
        agents_by_id = agents_by_id or {}

        for task in tasks:
            desc = task.description or ""

            # 6a. Description token count
            estimated_tokens = len(desc) // _CHARS_PER_TOKEN
            if estimated_tokens > _MAX_DESCRIPTION_TOKENS:
                issues.append(
                    f"Task '{task.title}' ({task.id}) description is ~{estimated_tokens} tokens "
                    f"(>{_MAX_DESCRIPTION_TOKENS}); consider decomposing into smaller tasks"
                )

            # 6b. Acceptance criteria count
            criteria_count = len(getattr(task, "acceptance_criteria_ids", []) or [])
            if criteria_count > _MAX_ACCEPTANCE_CRITERIA:
                issues.append(
                    f"Task '{task.title}' ({task.id}) has {criteria_count} acceptance criteria "
                    f"(>{_MAX_ACCEPTANCE_CRITERIA}); consider splitting"
                )

            # 6c. Action verb density — multiple distinct verbs suggest non-atomic scope
            verbs = set(v.lower() for v in _ACTION_VERBS.findall(desc))
            if len(verbs) >= _MAX_ACTION_VERBS:
                issues.append(
                    f"Task '{task.title}' ({task.id}) contains {len(verbs)} action verbs "
                    f"({', '.join(sorted(verbs))}); likely non-atomic — decompose further"
                )

            # 6d. Deliverable overload
            # Use a separate check for deliverable ID references in description
            deliverable_id_matches = re.findall(r"\bD-\d+\b", desc)
            if len(set(deliverable_id_matches)) > _MAX_DELIVERABLE_REFS:
                issues.append(
                    f"Task '{task.title}' ({task.id}) references {len(set(deliverable_id_matches))} "
                    f"deliverables (>{_MAX_DELIVERABLE_REFS}); should be split per deliverable"
                )

            # 6e. Output feasibility — flag tasks requesting output beyond agent capacity
            agent = agents_by_id.get(task.assigned_agent_id)
            if agent:
                agent_max_tokens = (
                    agent.budget.max_tokens
                    if agent.budget and agent.budget.max_tokens
                    else 16384
                )
                max_output_chars = agent_max_tokens * _CHARS_PER_TOKEN
                estimated_output = estimate_requested_output_chars(desc)
                if estimated_output > max_output_chars:
                    issues.append(
                        f"Task '{task.title}' ({task.id}) requests "
                        f"~{estimated_output // CHARS_PER_PAGE} pages of output but "
                        f"agent '{agent.id}' can produce ~{max_output_chars // CHARS_PER_PAGE} pages "
                        f"per task (max_tokens={agent_max_tokens}). Split into smaller sections."
                    )

        return issues

    def _detect_cycle(self, tasks: list) -> list[str] | None:
        """Detect cycles via DFS-based topological sort. Returns cycle path or None."""
        graph: dict[str, list[str]] = defaultdict(list)
        task_names: dict[str, str] = {}

        for task in tasks:
            task_names[task.id] = task.title
            for dep_id in task.depends_on:
                graph[dep_id].append(task.id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {t.id: WHITE for t in tasks}
        parent: dict[str, str | None] = {t.id: None for t in tasks}

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            for neighbor in graph.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    # Found cycle — reconstruct path
                    cycle = [task_names.get(neighbor, neighbor)]
                    cur = node
                    while cur != neighbor:
                        cycle.append(task_names.get(cur, cur))
                        cur = parent.get(cur, neighbor)
                    cycle.append(task_names.get(neighbor, neighbor))
                    cycle.reverse()
                    return cycle
                if color[neighbor] == WHITE:
                    parent[neighbor] = node
                    result = dfs(neighbor)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for task in tasks:
            if color[task.id] == WHITE:
                result = dfs(task.id)
                if result:
                    return result
        return None
