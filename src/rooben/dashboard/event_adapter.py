"""Bridge orchestrator events to WebSocket broadcaster + extension listeners.

DB writes for state transitions (task status, workflow counters) are handled
directly by the PostgresStateBackend.  This adapter is now broadcast-only,
with two exceptions:

1. ``llm.usage`` — usage/cost tracking rows are event-specific data not
   covered by the state backend.
2. ``workflow.completed`` — triggers Pro-only side-effects (performance
   snapshots, user outcomes) that operate on the completed state.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, ClassVar

logger = logging.getLogger("rooben.dashboard")


class DashboardEventAdapter:
    """Receives orchestrator events and broadcasts via WebSocket."""

    _event_listeners: ClassVar[list[Callable]] = []

    @classmethod
    def add_event_listener(cls, listener: Callable) -> None:
        """Register a listener called after every event (used by Pro for webhooks/audit)."""
        cls._event_listeners.append(listener)

    def __init__(self, pool: Any, broadcaster: Any) -> None:
        self._pool = pool
        self._broadcaster = broadcaster

    async def handle_event(self, event_type: str, payload: dict) -> None:
        """Route an orchestrator event to WebSocket broadcast + side-effects."""
        handler = getattr(self, f"_handle_{event_type.replace('.', '_')}", None)
        if handler:
            await handler(payload)

        # Always broadcast to connected WebSocket clients
        await self._broadcaster.broadcast({"type": event_type, **payload})

        # Notify extension listeners (webhooks, audit, etc.)
        for listener in self._event_listeners:
            try:
                await listener(event_type, payload)
            except Exception:
                logger.debug("Event listener error", exc_info=True)

    # ------------------------------------------------------------------
    # Handlers that still need the DB pool (non-state-transition writes)
    # ------------------------------------------------------------------

    async def _handle_llm_usage(self, payload: dict) -> None:
        """Insert token/cost usage into workflow_usage table."""
        cost_usd = payload.get("cost_usd", 0) or 0
        if cost_usd == 0:
            input_tokens = payload.get("input_tokens", 0)
            output_tokens = payload.get("output_tokens", 0)
            cost_usd = self._estimate_cost(
                payload.get("model", ""), input_tokens, output_tokens,
            )
        await self._pool.execute(
            """INSERT INTO workflow_usage
                   (workflow_id, task_id, provider, model, input_tokens, output_tokens, cost_usd, source)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            payload["workflow_id"],
            payload.get("task_id"),
            payload["provider"],
            payload["model"],
            payload["input_tokens"],
            payload["output_tokens"],
            cost_usd,
            payload.get("source", "agent"),
        )

    @staticmethod
    def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost from token counts when upstream cost is missing."""
        pricing = {
            "claude-sonnet-4":   (3.0, 15.0),
            "claude-opus-4":     (15.0, 75.0),
            "claude-haiku-3":    (0.80, 4.0),
            "gpt-4o":            (2.50, 10.0),
            "gpt-4o-mini":       (0.15, 0.60),
        }
        model_lower = model.lower()
        rate = None
        for key, value in pricing.items():
            if key in model_lower:
                rate = value
                break
        if rate is None:
            rate = (3.0, 15.0)
        return (input_tokens * rate[0] + output_tokens * rate[1]) / 1_000_000

    async def _handle_workflow_completed(self, payload: dict) -> None:
        """Pro-only side-effects after workflow completion.

        State transition (status update) is already handled by
        PostgresStateBackend — this handler only fires optional
        analytics hooks.
        """
        wf_id = payload.get("workflow_id", "")

        # P13: Record performance snapshot
        try:
            from rooben_pro.intelligence.performance_recorder import record_performance_snapshot
            await record_performance_snapshot(self._pool, wf_id)
        except Exception:
            pass  # Best-effort

        # P15b: Record user outcome
        try:
            wf_row = await self._pool.fetchrow(
                "SELECT user_id FROM workflows WHERE id = $1", wf_id
            )
            if wf_row and wf_row["user_id"] and wf_row["user_id"] != "anonymous":
                task_stats = await self._pool.fetchrow(
                    """SELECT COUNT(*) AS total,
                              COUNT(*) FILTER (WHERE status = 'passed') AS passed
                       FROM tasks WHERE workflow_id = $1""",
                    wf_id,
                )
                total = task_stats["total"] or 0
                passed = task_stats["passed"] or 0
                quality = passed / total if total > 0 else 0
                import uuid as _uuid
                await self._pool.execute(
                    """INSERT INTO user_outcomes
                           (id, user_id, workflow_id, outcome_type, summary, quality_score)
                       VALUES ($1, $2, $3, 'workflow_completion', $4, $5)""",
                    str(_uuid.uuid4()),
                    wf_row["user_id"],
                    wf_id,
                    f"Workflow {payload.get('status', 'completed')}: {passed}/{total} tasks passed",
                    round(quality, 3),
                )
        except Exception:
            pass  # Best-effort

    # Broadcast-only handlers (no DB writes needed — kept as explicit no-ops
    # so handle_event doesn't log "unknown event" warnings for them)
    async def _handle_task_started(self, payload: dict) -> None:
        pass

    async def _handle_task_passed(self, payload: dict) -> None:
        pass

    async def _handle_task_failed(self, payload: dict) -> None:
        pass

    async def _handle_task_cancelled(self, payload: dict) -> None:
        pass

    async def _handle_task_verification_failed(self, payload: dict) -> None:
        pass

    async def _handle_task_progress(self, payload: dict) -> None:
        pass

    async def _handle_workflow_planned(self, payload: dict) -> None:
        """Persist plan quality scores to the workflows table."""
        wf = payload.get("workflow", {})
        workflow_id = wf.get("id")
        if not workflow_id:
            return

        plan_quality = wf.get("plan_quality")
        plan_checker_score = wf.get("plan_checker_score")
        plan_judge_score = wf.get("plan_judge_score")

        if plan_quality is not None or plan_checker_score is not None:
            await self._pool.execute(
                """UPDATE workflows
                   SET plan_quality = $2::jsonb,
                       plan_checker_score = $3,
                       plan_judge_score = $4
                   WHERE id = $1""",
                workflow_id,
                json.dumps(plan_quality) if plan_quality else None,
                plan_checker_score,
                plan_judge_score,
            )

    async def _handle_workflow_spec_generating(self, payload: dict) -> None:
        pass

    async def _handle_workflow_spec_ready(self, payload: dict) -> None:
        pass
