"""Ollama LLM provider — local model inference via Ollama's OpenAI-compatible API."""

from __future__ import annotations

from rooben.planning.openai_provider import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    """
    LLM provider for locally-running Ollama models.

    Ollama exposes an OpenAI-compatible API at http://localhost:11434/v1.
    This is a thin wrapper that sets the defaults.

    Usage::

        provider = OllamaProvider(model="llama3.1")
        result = await provider.generate(system="You are helpful.", prompt="Hello")

    Requires:
        - Ollama installed and running: https://ollama.ai
        - Model pulled: ``ollama pull llama3.1``
    """

    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",  # Ollama doesn't require a real key
    ):
        super().__init__(model=model, api_key=api_key, base_url=base_url)

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096):
        result = await super().generate(system, prompt, max_tokens)
        result.provider = "ollama"
        return result

    async def generate_multi(self, system: str, messages: list[dict[str, str]], max_tokens: int = 4096):
        result = await super().generate_multi(system, messages, max_tokens)
        result.provider = "ollama"
        return result
