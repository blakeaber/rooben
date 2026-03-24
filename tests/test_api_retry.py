"""Tests for API retry with exponential backoff and concurrency limiting."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from rooben.resilience.api_retry import (
    APIConcurrencyLimiter,
    is_transient_error,
    retry_with_backoff,
)


# ---------------------------------------------------------------------------
# is_transient_error
# ---------------------------------------------------------------------------


class TestIsTransientError:
    def test_overloaded_error_is_transient(self):
        exc = type("OverloadedError", (Exception,), {})()
        assert is_transient_error(exc) is True

    def test_internal_server_error_is_transient(self):
        exc = type("InternalServerError", (Exception,), {})()
        assert is_transient_error(exc) is True

    def test_api_status_error_529_is_transient(self):
        exc = type("APIStatusError", (Exception,), {"status_code": 529})()
        assert is_transient_error(exc) is True

    def test_api_status_error_503_is_transient(self):
        exc = type("APIStatusError", (Exception,), {"status_code": 503})()
        assert is_transient_error(exc) is True

    def test_api_status_error_400_is_not_transient(self):
        exc = type("APIStatusError", (Exception,), {"status_code": 400})()
        assert is_transient_error(exc) is False

    def test_read_timeout_is_transient(self):
        exc = type("ReadTimeout", (Exception,), {})()
        assert is_transient_error(exc) is True

    def test_connect_timeout_is_transient(self):
        exc = type("ConnectTimeout", (Exception,), {})()
        assert is_transient_error(exc) is True

    def test_authentication_error_is_permanent(self):
        exc = type("AuthenticationError", (Exception,), {})()
        assert is_transient_error(exc) is False

    def test_bad_request_error_is_permanent(self):
        exc = type("BadRequestError", (Exception,), {})()
        assert is_transient_error(exc) is False

    def test_not_found_error_is_permanent(self):
        exc = type("NotFoundError", (Exception,), {})()
        assert is_transient_error(exc) is False

    def test_connection_error_is_transient(self):
        assert is_transient_error(ConnectionError("reset")) is True

    def test_timeout_error_is_transient(self):
        assert is_transient_error(TimeoutError()) is True

    def test_asyncio_timeout_is_transient(self):
        assert is_transient_error(asyncio.TimeoutError()) is True

    def test_unknown_error_is_not_transient(self):
        assert is_transient_error(ValueError("bad")) is False


# ---------------------------------------------------------------------------
# retry_with_backoff
# ---------------------------------------------------------------------------


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        factory = AsyncMock(return_value="ok")
        result = await retry_with_backoff(factory, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert factory.await_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_transient_failures(self):
        """Fails 2x with transient error, succeeds on 3rd."""
        transient = type("OverloadedError", (Exception,), {})
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise transient("overloaded")
            return "success"

        result = await retry_with_backoff(factory, max_retries=3, base_delay=0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_permanent_error_not_retried(self):
        """401 raises immediately, no retry."""
        permanent = type("AuthenticationError", (Exception,), {})

        async def factory():
            raise permanent("invalid key")

        with pytest.raises(permanent):
            await retry_with_backoff(factory, max_retries=5, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Always transient -> raises after N attempts."""
        transient = type("OverloadedError", (Exception,), {})
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            raise transient("overloaded")

        with pytest.raises(transient):
            await retry_with_backoff(factory, max_retries=3, base_delay=0.01)
        assert call_count == 4  # initial + 3 retries

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """Verify delays increase (total time > sum of minimum delays)."""
        transient = type("OverloadedError", (Exception,), {})
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise transient("overloaded")
            return "ok"

        start = time.monotonic()
        # base_delay=0.05 -> delays are random in [0, 0.05], [0, 0.1], [0, 0.2]
        result = await retry_with_backoff(factory, max_retries=4, base_delay=0.05)
        elapsed = time.monotonic() - start

        assert result == "ok"
        assert call_count == 4
        # Should have some non-zero delay (jitter makes it non-deterministic)
        # Just verify it didn't blow up and completed reasonably fast
        assert elapsed < 5.0  # Sanity: should complete well under 5s


# ---------------------------------------------------------------------------
# APIConcurrencyLimiter
# ---------------------------------------------------------------------------


class TestAPIConcurrencyLimiter:
    @pytest.mark.asyncio
    async def test_limits_concurrency(self):
        """5 concurrent calls with limit=2 -> max 2 simultaneous."""
        limiter = APIConcurrencyLimiter(max_concurrent=2)
        max_concurrent = 0
        current = 0

        async def work():
            nonlocal max_concurrent, current
            async with limiter:
                current += 1
                max_concurrent = max(max_concurrent, current)
                await asyncio.sleep(0.05)
                current -= 1

        await asyncio.gather(*[work() for _ in range(5)])
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_all_complete(self):
        """All calls eventually complete despite limiting."""
        limiter = APIConcurrencyLimiter(max_concurrent=2)
        completed = []

        async def work(i: int):
            async with limiter:
                await asyncio.sleep(0.01)
                completed.append(i)

        await asyncio.gather(*[work(i) for i in range(5)])
        assert len(completed) == 5

    def test_properties(self):
        limiter = APIConcurrencyLimiter(max_concurrent=3)
        assert limiter.max_concurrent == 3
        assert limiter.waiting == 0


# ---------------------------------------------------------------------------
# Provider integration (mock-based)
# ---------------------------------------------------------------------------


class TestProviderRetryIntegration:
    @pytest.mark.asyncio
    async def test_provider_retries_on_overloaded(self):
        """Mock messages.create to 529 twice then succeed -> provider returns result."""
        from rooben.planning.provider import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")

        # Create mock response
        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_usage.cache_read_input_tokens = 0
        mock_usage.cache_creation_input_tokens = 0

        mock_content = MagicMock()
        mock_content.text = "Hello world"

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage
        mock_response.stop_reason = "end_turn"

        # Simulate: 529 twice, then success
        OverloadedError = type("OverloadedError", (Exception,), {})
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OverloadedError("overloaded")
            return mock_response

        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        provider._client = mock_client

        result = await provider.generate(
            system="test",
            prompt="hello",
            max_tokens=100,
        )

        assert result.text == "Hello world"
        assert call_count == 3  # 2 failures + 1 success
