"""API retry with exponential backoff and concurrency limiting."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable, TypeVar

import structlog

log = structlog.get_logger()

T = TypeVar("T")


def is_transient_error(exc: Exception) -> bool:
    """Classify whether an exception is transient (retryable).

    Transient: 529 OverloadedError, 503 ServiceUnavailable, 500 InternalServerError,
               ReadTimeout, ConnectTimeout, ConnectionError.
    Permanent: 401 AuthenticationError, 400 BadRequestError, 404 NotFoundError,
               PermissionDeniedError, InvalidRequestError.
    """
    exc_type = type(exc).__name__

    # Anthropic SDK error classes
    transient_types = {
        "OverloadedError",
        "InternalServerError",
        "APIStatusError",  # will check status_code below
        "APIConnectionError",
        "APITimeoutError",
    }

    permanent_types = {
        "AuthenticationError",
        "BadRequestError",
        "NotFoundError",
        "PermissionDeniedError",
        "InvalidRequestError",
    }

    if exc_type in permanent_types:
        return False

    if exc_type in transient_types:
        # For APIStatusError, check the status code
        status = getattr(exc, "status_code", None)
        if status is not None:
            return status in (429, 500, 503, 529)
        return True

    # httpx errors
    httpx_transient = {"ReadTimeout", "ConnectTimeout", "ConnectError", "ReadError"}
    if exc_type in httpx_transient:
        return True

    # Generic connection errors
    if isinstance(exc, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True

    return False


async def retry_with_backoff(
    coro_factory: Callable[[], Awaitable[T]],
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
) -> T:
    """Retry transient errors with exponential backoff + jitter.

    Re-raises permanent errors immediately without retry.

    Args:
        coro_factory: Callable that returns a new awaitable on each call.
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1).
        base_delay: Base delay in seconds for first retry.
        max_delay: Maximum delay cap in seconds.

    Returns:
        The result of a successful call.

    Raises:
        The last exception if all retries are exhausted, or a permanent error immediately.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc

            if not is_transient_error(exc):
                raise

            if attempt >= max_retries:
                log.error(
                    "api_retry.exhausted",
                    total_attempts=attempt + 1,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise

            # Exponential backoff with full jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jittered_delay = random.uniform(0, delay)

            log.warning(
                "api_retry.retrying",
                attempt=attempt + 1,
                delay_seconds=round(jittered_delay, 2),
                error_type=type(exc).__name__,
                error=str(exc)[:200],
            )

            await asyncio.sleep(jittered_delay)

    # Should not reach here, but satisfy type checker
    assert last_exc is not None
    raise last_exc


class APIConcurrencyLimiter:
    """asyncio.Semaphore wrapper with observability.

    Limits concurrent API calls to prevent overwhelming the provider.
    Shared across all provider instances via module-level instance.
    """

    def __init__(self, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._waiting = 0

    async def __aenter__(self) -> APIConcurrencyLimiter:
        self._waiting += 1
        if self._semaphore.locked():
            log.debug(
                "api_limiter.queued",
                queue_depth=self._waiting,
            )
        await self._semaphore.acquire()
        self._waiting -= 1
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._semaphore.release()

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def waiting(self) -> int:
        return self._waiting


# Module-level shared instance
_default_limiter: APIConcurrencyLimiter | None = None


def get_default_limiter(max_concurrent: int = 5) -> APIConcurrencyLimiter:
    """Get or create the shared concurrency limiter."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = APIConcurrencyLimiter(max_concurrent)
    return _default_limiter
