"""Budget tracking — prevents runaway resource consumption."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import structlog

from rooben.domain import TokenUsage

log = structlog.get_logger()


class BudgetExceeded(Exception):
    """Raised when a budget limit is hit."""

    def __init__(self, resource: str, limit: int | float, current: int | float):
        self.resource = resource
        self.limit = limit
        self.current = current
        super().__init__(f"Budget exceeded for {resource}: {current}/{limit}")


@dataclass
class BudgetTracker:
    """
    Tracks resource consumption against configured limits.

    Thread-safe via asyncio.Lock.
    """

    max_total_tokens: int | None = None
    max_total_tasks: int | None = None
    max_wall_seconds: int | None = None
    max_concurrent_agents: int = 5
    max_cost_usd: Decimal | None = None

    # Counters
    tokens_used: int = field(default=0, init=False)
    tasks_completed: int = field(default=0, init=False)
    total_cost_usd: Decimal = field(default=Decimal("0"), init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    # Per-agent token tracking
    _agent_tokens: dict[str, int] = field(default_factory=dict, init=False)
    _task_tokens: list[int] = field(default_factory=list, init=False)

    # Cost callbacks (e.g. Stripe billing)
    _cost_callbacks: list[Callable] = field(default_factory=list, init=False)

    async def record_tokens(self, count: int, agent_id: str | None = None) -> None:
        async with self._lock:
            self.tokens_used += count
            self._task_tokens.append(count)
            if agent_id:
                self._agent_tokens[agent_id] = self._agent_tokens.get(agent_id, 0) + count
            if self.max_total_tokens and self.tokens_used > self.max_total_tokens:
                raise BudgetExceeded("tokens", self.max_total_tokens, self.tokens_used)

    async def record_task_completion(self) -> None:
        async with self._lock:
            self.tasks_completed += 1
            if self.max_total_tasks and self.tasks_completed > self.max_total_tasks:
                raise BudgetExceeded("tasks", self.max_total_tasks, self.tasks_completed)

    def check_wall_time(self, elapsed: float) -> None:
        """Raise BudgetExceeded if elapsed seconds exceed wall time limit."""
        if self.max_wall_seconds and elapsed > self.max_wall_seconds:
            raise BudgetExceeded("wall_seconds", self.max_wall_seconds, int(elapsed))

    def get_agent_semaphore(self) -> asyncio.Semaphore:
        return asyncio.Semaphore(self.max_concurrent_agents)

    def register_cost_callback(self, callback: Callable) -> None:
        """Register a callback invoked on each record_llm_usage call."""
        self._cost_callbacks.append(callback)

    async def record_llm_usage(
        self, provider: str, model: str, usage: TokenUsage, cost: Decimal,
    ) -> None:
        """Record LLM usage with cost tracking and callbacks."""
        async with self._lock:
            self.total_cost_usd += cost
            if self.max_cost_usd and self.total_cost_usd > self.max_cost_usd:
                raise BudgetExceeded(
                    "cost_usd",
                    float(self.max_cost_usd),
                    float(self.total_cost_usd),
                )

        for callback in self._cost_callbacks:
            await callback(provider, model, usage, cost)

    def summary(self) -> dict[str, Any]:
        task_tokens = self._task_tokens
        return {
            "tokens_used": self.tokens_used,
            "max_tokens": self.max_total_tokens,
            "tasks_completed": self.tasks_completed,
            "max_tasks": self.max_total_tasks,
            "total_cost_usd": str(self.total_cost_usd),
            "per_agent_tokens": dict(self._agent_tokens),
            "per_task_stats": {
                "count": len(task_tokens),
                "avg": sum(task_tokens) / len(task_tokens) if task_tokens else 0,
                "min": min(task_tokens) if task_tokens else 0,
                "max": max(task_tokens) if task_tokens else 0,
            },
        }
