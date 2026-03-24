"""Circuit breaker — stops dispatching when failures indicate a systemic problem."""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from typing import Literal

import structlog

log = structlog.get_logger()


class CircuitBreaker:
    """
    Three-state circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED.

    Opens when:
    - consecutive_failures >= max_failures, OR
    - any single error hash appears >= max_identical times.

    Transitions OPEN → HALF_OPEN after cooldown_seconds.
    HALF_OPEN → CLOSED on success, OPEN on failure.
    """

    def __init__(
        self,
        max_failures: int = 3,
        max_identical: int = 5,
        cooldown_seconds: float = 60.0,
    ):
        self._max_failures = max_failures
        self._max_identical = max_identical
        self._cooldown_seconds = cooldown_seconds

        self._consecutive_failures: int = 0
        self._error_hashes: Counter[str] = Counter()
        self._state: Literal["closed", "open", "half_open"] = "closed"
        self._opened_at: float = 0.0

    @property
    def state(self) -> Literal["closed", "open", "half_open"]:
        # Auto-transition OPEN → HALF_OPEN after cooldown
        if self._state == "open" and self._cooldown_elapsed():
            self._state = "half_open"
            log.info("circuit_breaker.half_open")
        return self._state

    def can_proceed(self) -> bool:
        """Return True if tasks may be dispatched."""
        s = self.state  # triggers auto-transition
        return s in ("closed", "half_open")

    def record_success(self) -> None:
        """Record a successful task execution."""
        if self._state == "half_open":
            log.info("circuit_breaker.closed_after_half_open")
        self._consecutive_failures = 0
        self._state = "closed"

    def record_failure(self, error_msg: str) -> None:
        """Record a failed task execution. May trip the breaker."""
        self._consecutive_failures += 1
        h = self._error_hash(error_msg)
        self._error_hashes[h] += 1

        if self._state == "half_open":
            self._trip("failure in half_open state")
            return

        if self._consecutive_failures >= self._max_failures:
            self._trip(
                f"consecutive failures ({self._consecutive_failures}) "
                f">= {self._max_failures}"
            )
            return

        most_common = self._error_hashes.most_common(1)
        if most_common and most_common[0][1] >= self._max_identical:
            self._trip(
                f"identical error repeated {most_common[0][1]} times "
                f">= {self._max_identical}"
            )

    def reset(self) -> None:
        """Fully reset the breaker to closed state."""
        self._consecutive_failures = 0
        self._error_hashes.clear()
        self._state = "closed"
        self._opened_at = 0.0

    def _trip(self, reason: str) -> None:
        self._state = "open"
        self._opened_at = time.monotonic()
        log.warning("circuit_breaker.opened", reason=reason)

    def _cooldown_elapsed(self) -> bool:
        return (time.monotonic() - self._opened_at) >= self._cooldown_seconds

    @staticmethod
    def _error_hash(msg: str) -> str:
        """Hash an error message for dedup counting."""
        return hashlib.md5(msg.encode()).hexdigest()[:12]
