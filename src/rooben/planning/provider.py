"""LLM provider protocol and implementations."""

from __future__ import annotations

import textwrap
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import anthropic

import structlog
from pydantic import BaseModel

from rooben.domain import TokenUsage

log = structlog.get_logger()

# Width for verbose output dividers
_VERBOSE_WIDTH = 88


class GenerationResult(BaseModel):
    """Result of an LLM generation call, including token usage metadata."""
    text: str
    usage: TokenUsage = TokenUsage()
    model: str = ""
    provider: str = ""
    truncated: bool = False


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for text generation."""

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
        """Generate a text completion with token usage tracking."""
        ...

    async def generate_multi(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
    ) -> GenerationResult:
        """Generate from a multi-turn conversation. Default: concatenate to single prompt."""
        ...


class AnthropicProvider:
    """Claude-backed LLM provider."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        timeout: float = 180.0,
        max_api_retries: int = 3,
        concurrency_limit: int = 5,
    ):
        self.model = model
        from rooben.agents.integrations import resolve_credential
        self._api_key = api_key or resolve_credential("ANTHROPIC_API_KEY")
        self._timeout = timeout
        self._max_api_retries = max_api_retries
        self._client: anthropic.AsyncAnthropic | None = None

        from rooben.resilience.api_retry import get_default_limiter
        self._concurrency_limiter = get_default_limiter(concurrency_limit)

    def _is_connection_error(self, exc: Exception) -> bool:
        """Check if exception is a connection-level error (not API-level)."""
        exc_type = type(exc).__name__
        # Connection-level: reset client to get fresh connection pool
        connection_types = {
            "ReadTimeout", "ConnectTimeout", "ConnectError",
            "ReadError", "APIConnectionError", "APITimeoutError",
        }
        if exc_type in connection_types:
            return True
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return True
        return False

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
        import asyncio

        import anthropic
        import httpx

        from rooben.resilience.api_retry import retry_with_backoff

        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key,
                timeout=httpx.Timeout(self._timeout, connect=30.0),
                max_retries=4,
            )
        client = self._client

        try:
            async with self._concurrency_limiter:
                response = await retry_with_backoff(
                    lambda: asyncio.wait_for(
                        client.messages.create(
                            model=self.model,
                            max_tokens=max_tokens,
                            system=system,
                            messages=[{"role": "user", "content": prompt}],
                        ),
                        timeout=self._timeout + 10,
                    ),
                    max_retries=self._max_api_retries,
                )
        except Exception as exc:
            # Only reset client for connection-level errors
            if self._is_connection_error(exc):
                self._client = None
            raise

        usage = TokenUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0),
            cache_creation_tokens=getattr(response.usage, "cache_creation_input_tokens", 0),
        )

        return GenerationResult(
            text=response.content[0].text,
            usage=usage,
            model=self.model,
            provider="anthropic",
            truncated=getattr(response, "stop_reason", None) == "max_tokens",
        )

    async def generate_multi(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
    ) -> GenerationResult:
        """Multi-turn generation with prompt caching on the system prompt."""
        import asyncio

        import anthropic
        import httpx

        from rooben.resilience.api_retry import retry_with_backoff

        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key,
                timeout=httpx.Timeout(self._timeout, connect=30.0),
                max_retries=4,
            )
        client = self._client

        # Enable prompt caching on system prompt
        system_with_cache = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
        ]

        try:
            async with self._concurrency_limiter:
                response = await retry_with_backoff(
                    lambda: asyncio.wait_for(
                        client.messages.create(
                            model=self.model,
                            max_tokens=max_tokens,
                            system=system_with_cache,
                            messages=messages,
                        ),
                        timeout=self._timeout + 10,
                    ),
                    max_retries=self._max_api_retries,
                )
        except Exception as exc:
            if self._is_connection_error(exc):
                self._client = None
            raise

        usage = TokenUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0),
            cache_creation_tokens=getattr(response.usage, "cache_creation_input_tokens", 0),
        )

        return GenerationResult(
            text=response.content[0].text,
            usage=usage,
            model=self.model,
            provider="anthropic",
            truncated=getattr(response, "stop_reason", None) == "max_tokens",
        )


class VerboseProvider:
    """Wraps any LLMProvider to print full request/response details to stderr.

    Usage::

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        verbose  = VerboseProvider(provider)
        # Now use ``verbose`` wherever you'd use ``provider``.
    """

    def __init__(self, inner: LLMProvider):
        self._inner = inner
        self._call_count = 0

    def _write_box(self, header: str, content: str) -> None:
        """Write a bordered box to stderr."""
        import sys
        w = _VERBOSE_WIDTH
        sep = "─" * w
        sys.stderr.write(f"┌{sep}┐\n")
        sys.stderr.write(f"│ {header:<{w - 2}}│\n")
        sys.stderr.write(f"├{sep}┤\n")
        for line in content.splitlines():
            if len(line) <= w - 2:
                sys.stderr.write(f"│ {line:<{w - 2}}│\n")
            else:
                for wrapped in textwrap.wrap(line, width=w - 4):
                    sys.stderr.write(f"│ {wrapped:<{w - 2}}│\n")
        sys.stderr.write(f"└{sep}┘\n\n")

    def _write_result(self, result: GenerationResult, elapsed: float) -> None:
        """Write response box and token usage to stderr."""
        import sys
        header = f"RESPONSE  │  {result.provider}/{result.model}  │  {elapsed:.1f}s"
        self._write_box(header, result.text)
        u = result.usage
        sys.stderr.write(f"  Tokens: {u.input_tokens:,} in / {u.output_tokens:,} out")
        if u.cache_read_tokens:
            sys.stderr.write(f" / {u.cache_read_tokens:,} cache-read")
        if u.cache_creation_tokens:
            sys.stderr.write(f" / {u.cache_creation_tokens:,} cache-write")
        sys.stderr.write(f" = {u.total:,} total\n")
        if result.truncated:
            sys.stderr.write("  ⚠ TRUNCATED (stop_reason=max_tokens)\n")
        sys.stderr.write(f"{'━' * _VERBOSE_WIDTH}\n\n")
        sys.stderr.flush()

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
        import sys

        self._call_count += 1
        w = _VERBOSE_WIDTH

        sys.stderr.write(f"\n{'━' * w}\n")
        sys.stderr.write(f"  LLM CALL #{self._call_count}  │  max_tokens={max_tokens}\n")
        sys.stderr.write(f"{'━' * w}\n\n")
        self._write_box("SYSTEM PROMPT", system)
        self._write_box("USER PROMPT", prompt)
        sys.stderr.flush()

        t0 = time.monotonic()
        result = await self._inner.generate(system=system, prompt=prompt, max_tokens=max_tokens)
        self._write_result(result, time.monotonic() - t0)
        return result

    async def generate_multi(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
    ) -> GenerationResult:
        import sys

        self._call_count += 1
        w = _VERBOSE_WIDTH

        sys.stderr.write(f"\n{'━' * w}\n")
        sys.stderr.write(f"  LLM CALL #{self._call_count}  │  max_tokens={max_tokens}  │  {len(messages)} messages\n")
        sys.stderr.write(f"{'━' * w}\n\n")
        self._write_box("SYSTEM PROMPT", system)

        # Show last user message only (older messages are context)
        last_user = next((m for m in reversed(messages) if m["role"] == "user"), None)
        if last_user:
            content = last_user["content"]
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated for display)"
            self._write_box(f"USER PROMPT (msg {len(messages)}/{len(messages)})", content)
        sys.stderr.flush()

        t0 = time.monotonic()
        result = await self._inner.generate_multi(system=system, messages=messages, max_tokens=max_tokens)
        self._write_result(result, time.monotonic() - t0)
        return result
