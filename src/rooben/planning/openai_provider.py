"""OpenAI LLM provider — compatible with OpenAI API and compatible endpoints."""

from __future__ import annotations


import structlog

from rooben.domain import TokenUsage
from rooben.planning.provider import GenerationResult

log = structlog.get_logger()


class OpenAIProvider:
    """
    LLM provider using the OpenAI API.

    Supports OpenAI, Azure OpenAI, and any OpenAI-compatible endpoint
    (vLLM, Ollama, etc.) via the base_url parameter.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model
        from rooben.agents.integrations import resolve_credential
        self._api_key = api_key or resolve_credential("OPENAI_API_KEY")
        self._base_url = base_url

    async def generate(
        self, system: str, prompt: str, max_tokens: int = 4096
    ) -> GenerationResult:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required for OpenAIProvider. "
                "Install with: pip install openai"
            )

        client_kwargs: dict = {"api_key": self._api_key}
        if self._base_url:
            client_kwargs["base_url"] = self._base_url

        client = AsyncOpenAI(**client_kwargs)

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
        )

        text = response.choices[0].message.content or ""
        usage = TokenUsage(
            input_tokens=getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
            output_tokens=getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        )

        return GenerationResult(
            text=text,
            usage=usage,
            model=self.model,
            provider="openai",
        )

    async def generate_multi(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
    ) -> GenerationResult:
        """Multi-turn generation with proper message structure."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required for OpenAIProvider. "
                "Install with: pip install openai"
            )

        client_kwargs: dict = {"api_key": self._api_key}
        if self._base_url:
            client_kwargs["base_url"] = self._base_url

        client = AsyncOpenAI(**client_kwargs)

        all_messages = [{"role": "system", "content": system}] + messages
        response = await client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            max_tokens=max_tokens,
        )

        text = response.choices[0].message.content or ""
        usage = TokenUsage(
            input_tokens=getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
            output_tokens=getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        )

        return GenerationResult(
            text=text,
            usage=usage,
            model=self.model,
            provider="openai",
        )
