"""Rate limiter — controls agent spawn frequency to prevent resource exhaustion."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

import structlog

log = structlog.get_logger()


class RateLimiter:
    """
    Token-bucket rate limiter for agent task dispatching.

    Limits how many tasks can be dispatched per agent per time window.
    """

    def __init__(self, max_per_minute: int = 30):
        self._max_per_minute = max_per_minute
        self._timestamps: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire(self, agent_id: str) -> None:
        """Block until the agent is allowed to accept a new task."""
        while True:
            async with self._lock:
                now = time.monotonic()
                window_start = now - 60.0

                # Prune old timestamps
                self._timestamps[agent_id] = [
                    ts for ts in self._timestamps[agent_id] if ts > window_start
                ]

                if len(self._timestamps[agent_id]) < self._max_per_minute:
                    self._timestamps[agent_id].append(now)
                    return

            # Wait before retrying
            await asyncio.sleep(1.0)

    def reset(self, agent_id: str | None = None) -> None:
        if agent_id:
            self._timestamps.pop(agent_id, None)
        else:
            self._timestamps.clear()
