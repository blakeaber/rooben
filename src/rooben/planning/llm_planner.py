"""LLM-backed planner — uses a language model to decompose specs into plans."""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Callable
from typing import Any

import structlog

from rooben.domain import Task, TokenUsage, Workflow, WorkflowState, Workstream
from rooben.planning.checker import PlanChecker
from rooben.planning.plan_judge import PlanJudge
from rooben.planning.provider import LLMProvider
from rooben.spec.models import Specification
from rooben.utils import parse_llm_json

log = structlog.get_logger()


class PlanningFailed(Exception):
    """Raised when the planner exhausts all iterations without producing a valid plan."""

    def __init__(
        self,
        message: str,
        checker_score: float | None = None,
        judge_score: float | None = None,
        plan_quality: dict | None = None,
    ):
        super().__init__(message)
        self.checker_score = checker_score
        self.judge_score = judge_score
        self.plan_quality = plan_quality


SYSTEM_PROMPT = """\
You are a planning engine for an autonomous agent orchestration system.

Given a product specification, you decompose it into workstreams and tasks.

Rules:
1. Each workstream groups related tasks (e.g. "Backend API", "Frontend", "Testing").
2. Each task must be small, atomic, and independently verifiable.
3. Tasks must declare dependencies on other tasks by ID.
4. Tasks must be assigned to agents by agent ID from the provided roster.
5. Tasks should include skeleton tests where appropriate.
6. Route tasks to agents whose capabilities best match the work.
7. CRITICAL — respect each agent's max_turns limit. Each tool call (file read,
   file write, fetch, shell command) costs 1 turn. If a task requires more
   actions than the agent's max_turns allows, split it into multiple PARALLEL
   tasks with no dependency between them. For example: if an agent has
   max_turns=40 and a research task requires fetching 50 URLs, split it into
   2 independent tasks of ~25 fetches each that can run concurrently.
   Only add dependencies between split tasks when the second genuinely needs
   the output of the first.
8. OUTPUT SIZE — Keep each task's expected output within the assigned agent's
   capacity. Agents can produce ~25 pages of content per task. For larger
   deliverables, split into chapter-level or section-level tasks with
   dependencies. Never request "50-page" or "100-page" output from a single task.

Output strict JSON matching this schema:
{
  "workstreams": [
    {
      "id": "ws-<uuid-short>",
      "name": "string",
      "description": "string",
      "tasks": [
        {
          "id": "task-<uuid-short>",
          "title": "string",
          "description": "string — detailed instructions for the agent",
          "assigned_agent_id": "string — from the agent roster",
          "depends_on": ["task-id", ...],
          "acceptance_criteria_ids": ["AC-xxx", ...],
          "verification_strategy": "llm_judge | test",
          "skeleton_tests": ["python test code as string", ...]
        }
      ]
    }
  ]
}

Output ONLY the JSON object. No markdown fences, no commentary.
"""


class LLMPlanner:
    """Decomposes a Specification into workstreams and tasks via LLM."""

    def __init__(
        self,
        provider: LLMProvider,
        max_checker_iterations: int = 3,
        judge_provider: LLMProvider | None = None,
    ):
        self._provider = provider
        self._checker = PlanChecker()
        self._judge = PlanJudge(judge_provider or provider)
        self._max_checker_iterations = max_checker_iterations
        # Accumulated token usage from the most recent plan() call
        self.last_usage: TokenUsage = TokenUsage()
        self.last_model: str = ""
        self.last_provider: str = ""
        # Plan quality metadata from most recent plan() call
        self.last_checker_score: float | None = None
        self.last_judge_score: float | None = None
        self.last_plan_quality: dict | None = None

    async def plan(
        self,
        spec: Specification,
        workflow_id: str,
        event_callback: Callable[[str, dict], Any] | None = None,
    ) -> WorkflowState:
        prompt = self._build_prompt(spec)
        log.info("llm_planner.generating", spec_id=spec.id)
        accumulated_usage = TokenUsage()
        judge_result = None

        await self._emit(event_callback, "planning.started", {
            "workflow_id": workflow_id,
            "max_iterations": self._max_checker_iterations,
        })

        for iteration in range(self._max_checker_iterations):
            await self._emit(event_callback, "planning.generating", {
                "workflow_id": workflow_id,
                "iteration": iteration + 1,
                "is_retry": iteration > 0,
            })

            gen_result = await self._provider.generate(
                system=SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=16384,
            )
            accumulated_usage = accumulated_usage + gen_result.usage

            plan_data = self._parse_response(gen_result.text)
            state = self._build_state(plan_data, spec, workflow_id)

            # Validate plan — structural checks
            await self._emit(event_callback, "planning.checking", {
                "workflow_id": workflow_id,
                "iteration": iteration + 1,
            })

            check = self._checker.check(state, spec, workflow_id)
            if not check.valid:
                log.warning(
                    "llm_planner.check_failed",
                    iteration=iteration + 1,
                    issues=check.issues,
                )
                await self._emit(event_callback, "planning.iteration_complete", {
                    "workflow_id": workflow_id,
                    "iteration": iteration + 1,
                    "outcome": "checker_failed",
                    "issues_count": len(check.issues),
                })
                prompt = (
                    prompt
                    + "\n\n## Plan Checker Feedback (fix these issues)\n"
                    + "\n".join(f"- {issue}" for issue in check.issues)
                    + "\n\nPlease regenerate the plan fixing the above issues."
                )
                continue

            # Structural checks passed — run LLM plan judge
            await self._emit(event_callback, "planning.judging", {
                "workflow_id": workflow_id,
                "iteration": iteration + 1,
                "checker_score": check.score,
            })

            judge_result = await self._judge.judge(state, spec, workflow_id)
            accumulated_usage = accumulated_usage + judge_result.usage

            if judge_result.approved:
                log.info(
                    "llm_planner.complete",
                    workstreams=len(state.workstreams),
                    tasks=len(state.tasks),
                    checker_iterations=iteration + 1,
                    tokens=accumulated_usage.total,
                )
                self.last_usage = accumulated_usage
                self.last_model = gen_result.model
                self.last_provider = gen_result.provider
                self.last_checker_score = check.score
                self.last_judge_score = judge_result.score
                self.last_plan_quality = {
                    "checker": {
                        "score": check.score,
                        "valid": check.valid,
                        "issues": check.issues,
                    },
                    "judge": {
                        "score": judge_result.score,
                        "approved": judge_result.approved,
                        "issues": [
                            {
                                "task_id": i.task_id,
                                "severity": i.severity,
                                "reason": i.reason,
                                "suggestion": i.suggestion,
                            }
                            for i in judge_result.issues
                        ],
                    },
                }
                return state

            # Judge rejected — re-prompt with judge feedback
            judge_feedback = "\n".join(
                f"- [{issue.severity.upper()}] Task {issue.task_id}: {issue.reason} "
                f"→ {issue.suggestion}"
                for issue in judge_result.issues
            )
            log.warning(
                "llm_planner.judge_rejected",
                iteration=iteration + 1,
                issue_count=len(judge_result.issues),
            )
            await self._emit(event_callback, "planning.iteration_complete", {
                "workflow_id": workflow_id,
                "iteration": iteration + 1,
                "outcome": "judge_rejected",
                "issues_count": len(judge_result.issues),
            })
            prompt = (
                prompt
                + "\n\n## Plan Quality Judge Feedback (fix these issues)\n"
                + judge_feedback
                + "\n\nDecompose oversized tasks into smaller, atomic tasks. "
                "Each task should be completable by one agent in a single execution."
            )

        # All iterations exhausted — fail cleanly
        log.error("llm_planner.checker_exhausted", iterations=self._max_checker_iterations)
        self.last_usage = accumulated_usage
        self.last_model = gen_result.model
        self.last_provider = gen_result.provider
        self.last_checker_score = check.score
        self.last_judge_score = judge_result.score if judge_result is not None else None
        judge_dict = None
        if judge_result is not None:
            judge_dict = {
                "score": judge_result.score,
                "approved": judge_result.approved,
                "issues": [
                    {
                        "task_id": i.task_id,
                        "severity": i.severity,
                        "reason": i.reason,
                        "suggestion": i.suggestion,
                    }
                    for i in judge_result.issues
                ],
            }
        self.last_plan_quality = {
            "checker": {
                "score": check.score,
                "valid": check.valid,
                "issues": check.issues,
            },
            "judge": judge_dict,
        }
        raise PlanningFailed(
            f"Plan validation failed after {self._max_checker_iterations} iterations",
            checker_score=check.score,
            judge_score=judge_result.score if judge_result else None,
            plan_quality=self.last_plan_quality,
        )

    @staticmethod
    async def _emit(
        callback: Callable[[str, dict], Any] | None,
        event_type: str,
        payload: dict,
    ) -> None:
        if callback is None:
            return
        result = callback(event_type, payload)
        if inspect.isawaitable(result):
            await result

    def _build_prompt(self, spec: Specification) -> str:
        agent_roster = "\n".join(
            f"- {a.id}: {a.name} — {a.description} "
            f"(capabilities: {', '.join(a.capabilities)}, "
            f"integrations: {a.integrations or ['none']}, "
            f"max_turns: {a.max_turns})"
            for a in spec.agents
        )
        deliverables = "\n".join(
            f"- {d.id}: {d.name} ({d.deliverable_type.value}) — {d.description}"
            for d in spec.deliverables
        )
        criteria = "\n".join(
            f"- {ac.id}: {ac.description} (verify: {ac.verification}, priority: {ac.priority.value})"
            for ac in spec.success_criteria.acceptance_criteria
        )
        constraints = "\n".join(
            f"- {c.id}: [{c.category.value}] {c.description} ({'hard' if c.hard else 'soft'})"
            for c in spec.constraints
        )
        test_reqs = "\n".join(
            f"- {t.id}: {t.description} ({t.test_type.value})"
            + (f"\n  Skeleton:\n  {t.skeleton}" if t.skeleton else "")
            for t in spec.success_criteria.test_requirements
        )
        hints = "\n".join(
            f"- {h.name}: {h.description}"
            + (f" (suggested agent: {h.suggested_agent_id})" if h.suggested_agent_id else "")
            + (f" (after: {', '.join(h.depends_on)})" if h.depends_on else "")
            for h in spec.workflow_hints
        )

        return f"""\
# Specification: {spec.title}

## Goal
{spec.goal}

## Context
{spec.context}

## Deliverables
{deliverables}

## Acceptance Criteria
{criteria}

## Test Requirements
{test_reqs}

## Constraints
{constraints}

## Agent Roster
{agent_roster}

## Workflow Hints
{hints or "(none)"}

## Notes
{spec.notes or "(none)"}

Decompose this into workstreams and tasks. Assign each task to the most capable agent.
Ensure tasks are small, verifiable, and correctly ordered by dependencies.
Include skeleton tests where appropriate (pytest for backend, playwright-style for frontend/UX).
"""

    def _parse_response(self, raw: str) -> dict:
        data = parse_llm_json(raw)
        if data is None:
            log.error("llm_planner.parse_failed", raw=raw[:500])
            raise ValueError("LLM returned invalid JSON")
        return data

    def _build_state(
        self, plan_data: dict, spec: Specification, workflow_id: str
    ) -> WorkflowState:
        state = WorkflowState()
        valid_agent_ids = {a.id for a in spec.agents}

        workflow = Workflow(
            id=workflow_id,
            spec_id=spec.id,
            status="planning",
            spec_content_hash=spec.content_hash(),
        )

        # Workflow-unique suffix to prevent task ID collisions across retries.
        # The LLM generates human-readable IDs like "task-spec-frameworks-1"
        # which collide when the same spec is retried.
        wf_suffix = workflow_id.split("-")[-1][:6]  # e.g. "233026" from "wf-233026f5"

        # First pass: collect all LLM-generated task IDs and build remap table
        id_remap: dict[str, str] = {}
        for ws_data in plan_data.get("workstreams", []):
            for task_data in ws_data.get("tasks", []):
                raw_id = task_data.get("id", f"task-{uuid.uuid4().hex[:8]}")
                scoped_id = f"{raw_id}-{wf_suffix}"
                id_remap[raw_id] = scoped_id

        # Second pass: build state with remapped IDs and dependencies
        for ws_data in plan_data.get("workstreams", []):
            raw_ws_id = ws_data.get("id", f"ws-{uuid.uuid4().hex[:8]}")
            ws_id = f"{raw_ws_id}-{wf_suffix}"
            ws = Workstream(
                id=ws_id,
                workflow_id=workflow_id,
                name=ws_data["name"],
                description=ws_data.get("description", ""),
            )

            for task_data in ws_data.get("tasks", []):
                raw_id = task_data.get("id", f"task-{uuid.uuid4().hex[:8]}")
                task_id = id_remap.get(raw_id, raw_id)
                agent_id = task_data.get("assigned_agent_id")

                if agent_id and agent_id not in valid_agent_ids:
                    log.warning(
                        "llm_planner.invalid_agent",
                        task_id=task_id,
                        agent_id=agent_id,
                    )
                    agent_id = spec.agents[0].id

                # Remap dependency references to scoped IDs
                raw_deps = task_data.get("depends_on", [])
                scoped_deps = [id_remap.get(d, d) for d in raw_deps]

                task = Task(
                    id=task_id,
                    workstream_id=ws_id,
                    workflow_id=workflow_id,
                    title=task_data["title"],
                    description=task_data.get("description", ""),
                    assigned_agent_id=agent_id,
                    depends_on=scoped_deps,
                    acceptance_criteria_ids=task_data.get("acceptance_criteria_ids", []),
                    verification_strategy=task_data.get("verification_strategy", "llm_judge"),
                    skeleton_tests=task_data.get("skeleton_tests", []),
                )

                registered = state.register_task(task)
                if registered:
                    ws.task_ids.append(task_id)
                    workflow.total_tasks += 1

            state.workstreams[ws_id] = ws
            workflow.workstream_ids.append(ws_id)

        state.workflows[workflow_id] = workflow
        return state
