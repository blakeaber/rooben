"""AWS Bedrock LLM provider — access Claude and other models via AWS Bedrock."""

from __future__ import annotations

from typing import Any

import structlog

from rooben.domain import TokenUsage
from rooben.planning.provider import GenerationResult

log = structlog.get_logger()


class BedrockProvider:
    """
    LLM provider using AWS Bedrock's Converse API.

    Supports Claude models on Bedrock at reduced cost vs direct Anthropic API.
    Uses boto3 async client.

    Usage::

        provider = BedrockProvider(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")
        result = await provider.generate(system="You are helpful.", prompt="Hello")

    Requires:
        - ``pip install boto3``
        - AWS credentials configured (env vars, ~/.aws/credentials, or IAM role)
        - Bedrock model access enabled in your AWS account

    Environment variables:
        - AWS_DEFAULT_REGION (default: us-east-1)
        - AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (or use IAM roles)
    """

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        region: str | None = None,
    ):
        self.model_id = model_id
        from rooben.config import get_settings
        self._region = region or get_settings().aws_default_region

    def _get_client(self) -> Any:
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 package required for BedrockProvider. "
                "Install with: pip install boto3"
            )
        return boto3.client("bedrock-runtime", region_name=self._region)

    async def generate(
        self, system: str, prompt: str, max_tokens: int = 4096
    ) -> GenerationResult:
        import asyncio

        client = self._get_client()

        response = await asyncio.to_thread(
            client.converse,
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens},
        )

        return self._parse_response(response)

    async def generate_multi(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
    ) -> GenerationResult:
        import asyncio

        client = self._get_client()

        bedrock_messages = [
            {"role": m["role"], "content": [{"text": m["content"]}]}
            for m in messages
        ]

        response = await asyncio.to_thread(
            client.converse,
            modelId=self.model_id,
            system=[{"text": system}],
            messages=bedrock_messages,
            inferenceConfig={"maxTokens": max_tokens},
        )

        return self._parse_response(response)

    def _parse_response(self, response: dict) -> GenerationResult:
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        text = content[0].get("text", "") if content else ""

        usage_data = response.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("inputTokens", 0),
            output_tokens=usage_data.get("outputTokens", 0),
        )

        # Extract model name from model_id for cleaner display
        model_short = self.model_id.split("/")[-1] if "/" in self.model_id else self.model_id

        return GenerationResult(
            text=text,
            usage=usage,
            model=model_short,
            provider="bedrock",
            truncated=response.get("stopReason") == "max_tokens",
        )
