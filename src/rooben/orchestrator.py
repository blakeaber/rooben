"""
Orchestrator — the central execution engine.

Responsibilities:
1. Accept a Specification and produce a plan via the Planner.
2. Execute tasks in dependency order using registered agents.
3. Verify task outputs before marking complete.
4. Persist state to the configured backend after every transition.
5. Enforce budgets, rate limits, and concurrency controls.
6. Loop until the specification is satisfied or budget is exhausted.
"""

from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from rooben.agents.protocol import AgentProtocol

import structlog

from rooben.agents.registry import AgentRegistry
from rooben.domain import (
    Task,
    TaskResult,
    TaskStatus,
    TokenUsage,
    VerificationFeedback,
    WorkflowState,
    WorkflowStatus,
)
from rooben.billing.costs import CostRegistry
from rooben.context.builder import ContextBuilder
from rooben.context.codebase_index import CodebaseIndex
from rooben.memory.learning_store import LearningStore
from rooben.memory.protocol import LearningStoreProtocol
from rooben.observability.diagnostics import DiagnosticAnalyzer, DiagnosticReport
from rooben.observability.reporter import WorkflowReport, WorkflowReporter
from rooben.planning.llm_planner import PlanningFailed
from rooben.planning.planner import Planner
from rooben.resilience.checkpoint import CheckpointManager
from rooben.resilience.circuit_breaker import CircuitBreaker
from rooben.security.budget import BudgetExceeded, BudgetTracker
from rooben.security.rate_limiter import RateLimiter
from rooben.security.sanitizer import OutputSanitizer
from rooben.spec.models import (
    GlobalBudget,
    Specification,
)
from rooben.state.protocol import StateBackend
from rooben.verification.verifier import Verifier

log = structlog.get_logger()

EventPayload = dict[str, Any]


class Orchestrator:
    """
    Drives spec → plan → execute → verify → done.

    Usage:
        orchestrator = Orchestrator(planner, agents, backend, verifier)
        result = await orchestrator.run(spec)
    """

    def __init__(
        self,
        planner: Planner,
        agent_registry: AgentRegistry,
        backend: StateBackend,
        verifier: Verifier,
        budget: GlobalBudget | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        checkpoint_interval: int = 5,
        learning_store: LearningStoreProtocol | None = None,
        reporter: WorkflowReporter | None = None,
        cost_registry: CostRegistry | None = None,
        context_builder: ContextBuilder | None = None,
        codebase_index: CodebaseIndex | None = None,
        event_callback: Callable[[str, EventPayload], Any] | None = None,
    ):
        self._planner = planner
        self._agents = agent_registry
        self._backend = backend
        self._verifier = verifier
        self._sanitizer = OutputSanitizer()
        self._rate_limiter = RateLimiter()
        self._learning_store = learning_store or LearningStore()
        self._reporter = reporter or WorkflowReporter()
        self._cost_registry = cost_registry or CostRegistry()
        self._context_builder = context_builder or ContextBuilder()
        self._codebase_index = codebase_index
        self._event_callback = event_callback
        self._workspace_dir: str | None = None

        # Budget tracking
        gb = budget or GlobalBudget()
        self._budget = BudgetTracker(
            max_total_tokens=gb.max_total_tokens,
            max_total_tasks=gb.max_total_tasks,
            max_wall_seconds=gb.max_wall_seconds,
            max_concurrent_agents=gb.max_concurrent_agents,
        )
        self._global_semaphore = self._budget.get_agent_semaphore()

        # Resilience
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._checkpoint_mgr = CheckpointManager(
            backend=backend, interval=checkpoint_interval,
        )

        self._cancel_event = asyncio.Event()
        self._state = WorkflowState()
        self._start_time: float = 0.0
        self._last_report: WorkflowReport | None = None
        self._last_diagnostic: DiagnosticReport | None = None
        self._project_id: str | None = None
        self._criteria_map: dict[str, str] = {}

    def cancel(self) -> None:
        """Signal the orchestrator to cancel the current workflow."""
        self._cancel_event.set()

    @property
    def last_report(self) -> WorkflowReport | None:
        """The most recent workflow execution report."""
        return self._last_report

    @property
    def last_diagnostic(self) -> DiagnosticReport | None:
        """The most recent diagnostic report (only set when >40% tasks fail)."""
        return self._last_diagnostic

    async def run(
        self, spec: Specification, workflow_id: str | None = None,
    ) -> WorkflowState:
        """Execute a specification end-to-end. Returns final state."""
        self._project_id = spec.id
        self._workspace_dir = getattr(spec, 'workspace_dir', None)
        self._start_time = time.monotonic()
        await self._backend.initialize()

        workflow_id = workflow_id or f"wf-{uuid.uuid4().hex[:8]}"
        log.info("orchestrator.starting", spec_id=spec.id, workflow_id=workflow_id)

        try:
            # Phase 1: Plan
            planned = await self._plan_phase(spec, workflow_id)
            if not planned:
                return self._state

            # Build acceptance criteria map for agent prompts and verification
            if spec.success_criteria and spec.success_criteria.acceptance_criteria:
                self._criteria_map = {
                    ac.id: ac.description
                    for ac in spec.success_criteria.acceptance_criteria
                }
                if hasattr(self._verifier, 'set_criteria_map'):
                    self._verifier.set_criteria_map(self._criteria_map)

            # Phase 2: Execute
            await self._execute_workflow(workflow_id)

            # Phase 3: Finalize
            report = await self._finalize_phase(workflow_id)

            # Phase 4: Learn & register
            await self._learning_phase(workflow_id, spec)

            wf = self._state.workflows[workflow_id]
            log.info(
                "orchestrator.finished",
                status=wf.status.value,
                completed=wf.completed_tasks,
                failed=wf.failed_tasks,
                total=wf.total_tasks,
                budget=self._budget.summary(),
                cost_usd=str(report.total_cost_usd),
            )

        except BudgetExceeded as exc:
            log.error("orchestrator.budget_exceeded", error=str(exc))
            wf = self._state.workflows.get(workflow_id)
            if wf:
                wf.status = WorkflowStatus.FAILED
                await self._backend.save_state(self._state)
            raise

        finally:
            await self._backend.close()

        return self._state

    async def resume(self, workflow_id: str) -> WorkflowState:
        """Resume an incomplete workflow from persisted state."""
        self._start_time = time.monotonic()
        await self._backend.initialize()

        try:
            state = await self._backend.load_state(workflow_id)
            if not state:
                raise ValueError(f"Workflow {workflow_id} not found in backend")

            self._state = state
            wf = self._state.workflows.get(workflow_id)
            if not wf:
                raise ValueError(f"Workflow {workflow_id} not found in state")

            # Validate agent registry covers all assigned agents
            for task in self._state.tasks.values():
                if task.workflow_id == workflow_id and task.assigned_agent_id:
                    if not self._agents.get(task.assigned_agent_id):
                        raise ValueError(
                            f"Agent {task.assigned_agent_id} required by task "
                            f"{task.id} not found in registry"
                        )

            log.info(
                "orchestrator.resuming",
                workflow_id=workflow_id,
                completed=wf.completed_tasks,
                failed=wf.failed_tasks,
                total=wf.total_tasks,
            )

            wf.status = WorkflowStatus.IN_PROGRESS
            await self._backend.save_state(self._state)

            await self._execute_workflow(workflow_id)

            await self._finalize_phase(workflow_id)

            wf = self._state.workflows[workflow_id]
            log.info(
                "orchestrator.resume_finished",
                status=wf.status.value,
                completed=wf.completed_tasks,
                failed=wf.failed_tasks,
                total=wf.total_tasks,
                budget=self._budget.summary(),
            )

        except BudgetExceeded as exc:
            log.error("orchestrator.budget_exceeded", error=str(exc))
            wf = self._state.workflows.get(workflow_id)
            if wf:
                wf.status = WorkflowStatus.FAILED
                await self._backend.save_state(self._state)
            raise

        finally:
            await self._backend.close()

        return self._state

    # ------------------------------------------------------------------
    # Workflow phases
    # ------------------------------------------------------------------

    async def _plan_phase(
        self, spec: Specification, workflow_id: str,
    ) -> bool:
        """Run the planner to decompose the spec into a task DAG.

        Returns True if planning succeeded, False if it failed.
        """
        try:
            self._state = await self._planner.plan(
                spec, workflow_id, event_callback=self._event_callback,
            )
        except PlanningFailed as exc:
            log.error("orchestrator.planning_failed", error=str(exc))
            await self._emit_event("workflow.completed", {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(exc),
                "completed_tasks": 0,
                "failed_tasks": 0,
                "total_tasks": 0,
            })
            from rooben.domain import Workflow
            wf = Workflow(id=workflow_id, spec_id=spec.id, status=WorkflowStatus.FAILED)
            self._state = WorkflowState()
            self._state.workflows[workflow_id] = wf
            return False

        wf = self._state.workflows[workflow_id]
        wf.status = WorkflowStatus.IN_PROGRESS
        await self._backend.save_state(self._state)

        await self._emit_planner_usage(workflow_id)

        await self._emit_event("workflow.planned", {
            "workflow": {
                "id": workflow_id,
                "spec_id": spec.id,
                "title": spec.title,
                "status": "in_progress",
                "total_tasks": wf.total_tasks,
                "plan_checker_score": getattr(self._planner, "last_checker_score", None),
                "plan_judge_score": getattr(self._planner, "last_judge_score", None),
                "plan_quality": getattr(self._planner, "last_plan_quality", None),
            },
            "agents": [a.model_dump() for a in spec.agents],
            "spec_yaml": spec.model_dump_json(indent=2),
            "spec_metadata": {
                "title": spec.title,
                "goal": spec.goal,
                "context": spec.context,
                "deliverables": [d.model_dump() for d in spec.deliverables],
                "agents": [{"id": a.id, "name": a.name, "description": a.description} for a in spec.agents],
                "constraints": [c.model_dump() for c in spec.constraints],
                "acceptance_criteria": [
                    ac.model_dump() for ac in spec.success_criteria.acceptance_criteria
                ],
                "global_budget": spec.global_budget.model_dump() if spec.global_budget else None,
            },
            "workstreams": [
                {
                    "id": ws.id,
                    "name": ws.name,
                    "description": getattr(ws, "description", ""),
                    "status": ws.status.value if hasattr(ws.status, "value") else str(ws.status),
                    "task_ids": list(ws.task_ids) if hasattr(ws, "task_ids") else [],
                }
                for ws in self._state.workstreams.values()
                if ws.workflow_id == workflow_id
            ],
            "tasks": [
                {
                    "id": t.id,
                    "workstream_id": getattr(t, "workstream_id", None),
                    "title": t.title,
                    "description": t.description,
                    "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                    "assigned_agent_id": t.assigned_agent_id,
                    "max_retries": t.max_retries,
                    "priority": getattr(t, "priority", 0),
                    "depends_on": list(t.depends_on),
                }
                for t in self._state.tasks.values()
                if t.workflow_id == workflow_id
            ],
        })
        return True

    async def _finalize_phase(self, workflow_id: str) -> WorkflowReport:
        """Mark workflow complete, generate report and diagnostics."""
        wf = self._state.workflows[workflow_id]
        if self._state.is_workflow_complete(workflow_id) and not self._state.is_workflow_failed(workflow_id):
            wf.status = WorkflowStatus.COMPLETED
        else:
            wf.status = WorkflowStatus.FAILED
        wf.completed_at = datetime.utcnow()
        await self._backend.save_state(self._state)

        await self._emit_event("workflow.completed", {
            "workflow_id": workflow_id,
            "status": wf.status.value,
            "completed_tasks": wf.completed_tasks,
            "failed_tasks": wf.failed_tasks,
            "total_tasks": wf.total_tasks,
        })

        elapsed = time.monotonic() - self._start_time
        report = self._reporter.generate_report(
            self._state, workflow_id, wall_seconds=elapsed,
        )
        self._last_report = report

        if wf.total_tasks > 0 and wf.failed_tasks / wf.total_tasks > 0.4:
            diagnostic = DiagnosticAnalyzer().analyze(self._state, workflow_id)
            self._last_diagnostic = diagnostic
            log.warning(
                "orchestrator.high_failure_rate",
                workflow_id=workflow_id,
                recommendation=diagnostic.recommendation,
            )

        return report

    async def _learning_phase(
        self, workflow_id: str, spec: Specification,
    ) -> None:
        """Post-workflow phase: auto-register any agents discovered during the run."""
        try:
            self._auto_register_agents(spec)
        except Exception as exc:
            log.warning("orchestrator.agent_auto_register_failed", error=str(exc))

    async def _execute_workflow(self, workflow_id: str) -> None:
        """Execute all tasks in a workflow, respecting dependencies."""
        while not self._state.is_workflow_complete(workflow_id):
            self._check_wall_time()

            # Cancellation check
            if self._cancel_event.is_set():
                log.info("orchestrator.cancelled", workflow_id=workflow_id)
                for t in self._state.tasks.values():
                    if t.workflow_id == workflow_id and not t.is_terminal:
                        t.status = TaskStatus.SKIPPED
                        self._state.tasks[t.id] = t
                wf = self._state.workflows.get(workflow_id)
                if wf:
                    wf.status = WorkflowStatus.CANCELLED
                    wf.completed_at = datetime.utcnow()
                await self._backend.save_state(self._state)
                await self._emit_event("workflow.completed", {
                    "workflow_id": workflow_id,
                    "status": "cancelled",
                    "completed_tasks": wf.completed_tasks if wf else 0,
                    "failed_tasks": wf.failed_tasks if wf else 0,
                    "total_tasks": wf.total_tasks if wf else 0,
                })
                break

            # Circuit breaker check
            if not self._circuit_breaker.can_proceed():
                log.warning(
                    "orchestrator.circuit_open",
                    workflow_id=workflow_id,
                    state=self._circuit_breaker.state,
                )
                await self._checkpoint_mgr.force_checkpoint(
                    self._state, workflow_id,
                )
                # Fail remaining tasks
                for t in self._state.tasks.values():
                    if t.workflow_id == workflow_id and not t.is_terminal:
                        t.status = TaskStatus.FAILED
                        t.result = TaskResult(error="Circuit breaker open")
                        self._state.tasks[t.id] = t
                break

            ready_tasks = self._state.get_ready_tasks(workflow_id)
            if not ready_tasks:
                # No ready tasks — check if workflow is stalled (all pending
                # tasks blocked by failures). Leave them PENDING for retry.
                if self._state.is_workflow_stalled(workflow_id):
                    log.info("orchestrator.stalled", workflow_id=workflow_id)
                    break
                await asyncio.sleep(0.5)
                continue

            # Dispatch ready tasks concurrently
            coros = [self._dispatch_task(task) for task in ready_tasks]
            results = await asyncio.gather(*coros, return_exceptions=True)

            # Propagate budget exceptions from concurrent tasks
            for result in results:
                if isinstance(result, BudgetExceeded):
                    raise result

            await self._backend.save_state(self._state)

            # Periodic checkpoint
            wf = self._state.workflows.get(workflow_id)
            if wf:
                await self._checkpoint_mgr.maybe_checkpoint(
                    self._state, workflow_id, wf.completed_tasks,
                )

    async def _dispatch_task(self, task: Task) -> None:
        """Dispatch a single task to its assigned agent."""
        agent_id = task.assigned_agent_id
        if not agent_id:
            log.error("orchestrator.no_agent", task_id=task.id)
            task.status = TaskStatus.FAILED
            task.result = TaskResult(error="No agent assigned")
            await self._update_task(task)
            return

        agent = self._agents.get(agent_id)
        if not agent:
            log.error("orchestrator.agent_not_found", agent_id=agent_id, task_id=task.id)
            task.status = TaskStatus.FAILED
            task.result = TaskResult(error=f"Agent {agent_id} not found in registry")
            await self._update_task(task)
            return

        # Acquire semaphores: global + per-agent
        agent_semaphore = self._agents.get_semaphore(agent_id)

        async with self._global_semaphore:
            async with agent_semaphore:
                await self._rate_limiter.acquire(agent_id)
                await self._execute_task(task, agent)

    async def _execute_task(self, task: Task, agent: AgentProtocol) -> None:
        """Execute a task, verify output, handle retries."""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        task.attempt += 1
        await self._update_task(task)

        await self._emit_event("task.started", {
            "task_id": task.id,
            "workflow_id": task.workflow_id,
            "attempt": task.attempt,
            "agent_id": task.assigned_agent_id,
        })

        log.info(
            "orchestrator.task_started",
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            attempt=task.attempt,
        )

        # Query codebase index for relevant files
        codebase_ctx = None
        if self._codebase_index:
            keywords = task.title.split() + task.description.split()[:20]
            codebase_ctx = self._codebase_index.query(keywords, budget_tokens=1000)
            codebase_ctx = codebase_ctx or None

        task.enriched_prompt = self._context_builder.build(
            task, state=self._state,
            codebase_context=codebase_ctx,
            workspace_dir=self._workspace_dir,
            criteria_map=self._criteria_map,
        )

        # Execute
        log.debug("orchestrator.task_executing", task_id=task.id)
        await self._emit_event("task.progress", {
            "task_id": task.id,
            "workflow_id": task.workflow_id,
            "phase": "executing",
            "attempt": task.attempt,
        })
        result = await agent.execute(task)
        log.debug("orchestrator.task_agent_done", task_id=task.id, has_error=bool(result.error), output_len=len(result.output))

        # Sanitize output
        result.output = self._sanitizer.sanitize(result.output)
        for name in list(result.artifacts):
            result.artifacts[name] = self._sanitizer.sanitize(result.artifacts[name])

        # Track tokens and cost (WS-1.1, WS-5.1)
        if result.token_usage > 0:
            await self._budget.record_tokens(result.token_usage, agent_id=task.assigned_agent_id)
        if result.token_usage_detailed:
            try:
                # Extract actual provider/model from agent
                provider_name = "anthropic"
                model_name = "default"
                if hasattr(agent, '_provider'):
                    p = agent._provider
                    # Unwrap VerboseProvider
                    if hasattr(p, '_inner'):
                        p = p._inner
                    model_name = getattr(p, 'model', 'default')
                    provider_name = getattr(p, '_provider_name', 'anthropic')
                    # Infer provider name from class if not explicitly set
                    if provider_name == 'anthropic':
                        cls_name = type(p).__name__.lower()
                        if 'openai' in cls_name:
                            provider_name = 'openai'

                cost = self._cost_registry.calculate_cost(
                    provider_name, model_name, result.token_usage_detailed,
                )
                await self._budget.record_llm_usage(
                    provider_name, model_name, result.token_usage_detailed, cost,
                )
                usage = result.token_usage_detailed
                await self._emit_event("llm.usage", {
                    "workflow_id": task.workflow_id,
                    "task_id": task.id,
                    "provider": provider_name,
                    "model": model_name,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_usd": float(cost),
                    "source": "agent",
                })
            except Exception:
                log.debug("orchestrator.cost_tracking_failed", exc_info=True)

        if result.error:
            log.warning(
                "orchestrator.task_error",
                task_id=task.id,
                error=result.error[:200],
            )
            # Record feedback so every attempt is visible in the inspector
            error_feedback = VerificationFeedback(
                attempt=task.attempt,
                verifier_type="agent_error",
                passed=False,
                score=0.0,
                feedback=result.error or "unknown error",
            )
            task.attempt_feedback.append(error_feedback)
            await self._emit_event("task.verification_failed", {
                "task_id": task.id,
                "workflow_id": task.workflow_id,
                "attempt": task.attempt,
                "feedback": error_feedback.model_dump(),
            })

            if task.attempt < task.max_retries:
                task.status = TaskStatus.PENDING  # Will be retried
                task.result = result
                await self._update_task(task)
                return
            else:
                task.status = TaskStatus.FAILED
                task.result = result
                task.completed_at = datetime.utcnow()
                await self._update_task(task)
                await self._update_workflow_counters(task, failed=True)
                self._circuit_breaker.record_failure(result.error or "unknown error")
                await self._emit_event("task.failed", {
                    "task_id": task.id,
                    "workflow_id": task.workflow_id,
                    "error": result.error or "unknown error",
                    "result": result.model_dump() if result else None,
                    "attempt_feedback": [fb.model_dump() for fb in task.attempt_feedback],
                })
                return

        # Verify
        task.status = TaskStatus.VERIFYING
        task.result = result
        await self._update_task(task)

        await self._emit_event("task.progress", {
            "task_id": task.id,
            "workflow_id": task.workflow_id,
            "phase": "verifying",
            "attempt": task.attempt,
        })
        log.debug("orchestrator.task_verifying", task_id=task.id)
        verification = await self._verifier.verify(task, result)
        log.debug("orchestrator.task_verified", task_id=task.id, passed=verification.passed)

        # Emit verifier token usage
        await self._emit_verifier_usage(task, verification)

        if verification.passed:
            # Store passed verification feedback (P6.5 — 1a)
            passed_feedback = VerificationFeedback(
                attempt=task.attempt,
                verifier_type=task.verification_strategy,
                passed=True,
                score=verification.score,
                feedback=verification.feedback,
                suggested_improvements=verification.suggested_improvements,
                test_results=verification.test_results,
            )
            task.attempt_feedback.append(passed_feedback)

            task.status = TaskStatus.PASSED
            task.completed_at = datetime.utcnow()
            await self._update_task(task)
            await self._update_workflow_counters(task, failed=False)
            self._circuit_breaker.record_success()
            await self._budget.record_task_completion()

            await self._emit_event("task.passed", {
                "task_id": task.id,
                "workflow_id": task.workflow_id,
                "output": (result.output or "")[:500],
                "score": verification.score,
                "result": result.model_dump() if result else None,
                "attempt_feedback": [fb.model_dump() for fb in task.attempt_feedback],
            })

            log.info(
                "orchestrator.task_passed",
                task_id=task.id,
                score=verification.score,
            )
        else:
            log.warning(
                "orchestrator.task_verification_failed",
                task_id=task.id,
                feedback=verification.feedback[:200],
            )
            # Store verification feedback for retry context (WS-1.2)
            feedback = VerificationFeedback(
                attempt=task.attempt,
                verifier_type=task.verification_strategy,
                passed=False,
                score=verification.score,
                feedback=verification.feedback,
                suggested_improvements=verification.suggested_improvements,
                test_results=verification.test_results,
            )
            task.attempt_feedback.append(feedback)

            # Emit intermediate verification failure for DB tracking (P6.5 — 1c)
            await self._emit_event("task.verification_failed", {
                "task_id": task.id,
                "workflow_id": task.workflow_id,
                "attempt": task.attempt,
                "feedback": feedback.model_dump(),
            })

            if task.attempt < task.max_retries:
                task.status = TaskStatus.PENDING
                await self._update_task(task)
                await self._emit_event("task.progress", {
                    "task_id": task.id,
                    "workflow_id": task.workflow_id,
                    "phase": "retrying",
                    "attempt": task.attempt,
                })
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                await self._update_task(task)
                await self._update_workflow_counters(task, failed=True)
                self._circuit_breaker.record_failure(verification.feedback[:200])
                await self._emit_event("task.failed", {
                    "task_id": task.id,
                    "workflow_id": task.workflow_id,
                    "error": verification.feedback[:200],
                    "result": result.model_dump() if result else None,
                    "attempt_feedback": [fb.model_dump() for fb in task.attempt_feedback],
                })

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    async def _update_task(self, task: Task) -> None:
        """Update task in state (in-memory + backend), then derive workstream status."""
        self._state.tasks[task.id] = task
        await self._backend.update_task(task)
        await self._derive_workstream_status(task)

    async def _derive_workstream_status(self, task: Task) -> None:
        """Derive workstream status from the statuses of its member tasks."""
        from rooben.domain import WorkstreamStatus

        ws_id = task.workstream_id
        if not ws_id:
            return
        ws = self._state.workstreams.get(ws_id)
        if not ws:
            return

        member_tasks = [
            self._state.tasks[tid]
            for tid in ws.task_ids
            if tid in self._state.tasks
        ]
        if not member_tasks:
            return

        statuses = {t.status for t in member_tasks}
        terminal = {TaskStatus.PASSED, TaskStatus.FAILED, TaskStatus.SKIPPED, TaskStatus.CANCELLED}

        if all(s in terminal for s in statuses):
            if TaskStatus.FAILED in statuses:
                new_status = WorkstreamStatus.FAILED
            elif TaskStatus.CANCELLED in statuses and TaskStatus.PASSED not in statuses:
                new_status = WorkstreamStatus.CANCELLED
            else:
                new_status = WorkstreamStatus.COMPLETED
        elif TaskStatus.IN_PROGRESS in statuses or TaskStatus.VERIFYING in statuses:
            new_status = WorkstreamStatus.IN_PROGRESS
        else:
            new_status = WorkstreamStatus.PENDING

        if ws.status != new_status:
            ws.status = new_status
            self._state.workstreams[ws_id] = ws
            await self._backend.save_state(self._state)

    async def _update_workflow_counters(self, task: Task, failed: bool) -> None:
        """Update workflow completion counters (in-memory + backend)."""
        wf = self._state.workflows.get(task.workflow_id)
        if wf:
            if failed:
                wf.failed_tasks += 1
            else:
                wf.completed_tasks += 1
            await self._backend.update_workflow(wf)

    async def _emit_event(self, event_type: str, payload: dict) -> None:
        """Emit an event via the callback (handles sync/async callbacks)."""
        if self._event_callback is None:
            return
        result = self._event_callback(event_type, payload)
        if inspect.isawaitable(result):
            await result

    async def _emit_planner_usage(self, workflow_id: str) -> None:
        """Emit llm.usage event for planner token consumption."""
        planner = self._planner
        usage = getattr(planner, "last_usage", None)
        if not usage or not isinstance(usage, TokenUsage) or usage.total == 0:
            return
        model = getattr(planner, "last_model", "") or "unknown"
        provider = getattr(planner, "last_provider", "") or "anthropic"
        try:
            cost = self._cost_registry.calculate_cost(provider, model, usage)
            await self._emit_event("llm.usage", {
                "workflow_id": workflow_id,
                "task_id": None,
                "provider": provider,
                "model": model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": float(cost),
                "source": "planner",
            })
        except Exception:
            log.debug("cost_tracking_failed", exc_info=True)

    async def _emit_verifier_usage(self, task: Task, verification: Any) -> None:
        """Emit llm.usage event for verifier token consumption."""
        usage = getattr(verification, "token_usage", None)
        if not usage or not isinstance(usage, TokenUsage) or usage.total == 0:
            return
        model = getattr(verification, "model", "") or "unknown"
        provider = getattr(verification, "provider", "") or "anthropic"
        try:
            cost = self._cost_registry.calculate_cost(provider, model, usage)
            await self._emit_event("llm.usage", {
                "workflow_id": task.workflow_id,
                "task_id": task.id,
                "provider": provider,
                "model": model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": float(cost),
                "source": "verifier",
            })
        except Exception:
            log.debug("cost_tracking_failed", exc_info=True)

    def _auto_register_agents(self, spec: Specification) -> None:
        """Serialize on-the-fly agents as extension manifests for future reuse."""
        from pathlib import Path
        import yaml

        for agent in spec.agents:
            agent_dir = Path(f".rooben/extensions/agents/{agent.id}")
            manifest_path = agent_dir / "rooben-extension.yaml"

            # Skip if already registered
            if manifest_path.exists():
                continue

            # Only register agents that have meaningful capabilities
            if not agent.capabilities or len(agent.capabilities) < 2:
                continue

            agent_dir.mkdir(parents=True, exist_ok=True)

            manifest = {
                "schema_version": 1,
                "name": agent.id,
                "type": "agent",
                "version": "1.0.0",
                "author": "auto-registered",
                "description": agent.description,
                "tags": agent.capabilities[:5],
                "domain_tags": [],
                "category": "user",
                "transport": agent.transport.value if hasattr(agent.transport, 'value') else str(agent.transport),
                "capabilities": agent.capabilities,
                "integration": getattr(agent, 'integration', '') or '',
                "max_concurrency": agent.max_concurrency,
                "max_context_tokens": agent.max_context_tokens,
                "is_default": False,
            }

            with open(manifest_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

            log.info("orchestrator.agent_auto_registered", agent_id=agent.id)

    def _check_wall_time(self) -> None:
        """Raise BudgetExceeded if wall time limit is hit."""
        elapsed = time.monotonic() - self._start_time
        self._budget.check_wall_time(elapsed)
