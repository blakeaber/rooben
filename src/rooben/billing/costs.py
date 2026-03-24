"""CostRegistry — built-in pricing for LLM providers."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from rooben.domain import TokenUsage


class ModelPricing(BaseModel):
    """Pricing per million tokens for a specific model."""
    input_per_million: Decimal
    output_per_million: Decimal
    cache_read_per_million: Decimal = Decimal("0")
    cache_write_per_million: Decimal = Decimal("0")


class CostRegistry:
    """
    Registry of model pricing. Ships with built-in pricing for
    Anthropic and OpenAI models. Custom pricing can be registered.
    """

    def __init__(self) -> None:
        self._pricing: dict[str, ModelPricing] = {}
        self._register_defaults()

    def register(self, provider: str, model: str, pricing: ModelPricing) -> None:
        """Register pricing for a provider/model combination."""
        key = f"{provider}:{model}"
        self._pricing[key] = pricing

    def calculate_cost(
        self, provider: str, model: str, usage: TokenUsage
    ) -> Decimal:
        """Calculate cost in USD for the given usage."""
        pricing = self.get_pricing(provider, model)
        if not pricing:
            return Decimal("0")

        million = Decimal("1000000")
        cost = (
            Decimal(usage.input_tokens) * pricing.input_per_million / million
            + Decimal(usage.output_tokens) * pricing.output_per_million / million
            + Decimal(usage.cache_read_tokens) * pricing.cache_read_per_million / million
            + Decimal(usage.cache_creation_tokens) * pricing.cache_write_per_million / million
        )
        return cost.quantize(Decimal("0.000001"))

    def get_pricing(self, provider: str, model: str) -> ModelPricing | None:
        """Get pricing for a specific provider/model."""
        key = f"{provider}:{model}"
        if key in self._pricing:
            return self._pricing[key]
        # Try partial match (model only)
        for k, v in self._pricing.items():
            if k.endswith(f":{model}"):
                return v
        return None

    def _register_defaults(self) -> None:
        """Register built-in pricing for common models."""
        # Anthropic models
        self.register("anthropic", "claude-sonnet-4-20250514", ModelPricing(
            input_per_million=Decimal("3"),
            output_per_million=Decimal("15"),
            cache_read_per_million=Decimal("0.30"),
            cache_write_per_million=Decimal("3.75"),
        ))
        self.register("anthropic", "claude-opus-4-20250514", ModelPricing(
            input_per_million=Decimal("15"),
            output_per_million=Decimal("75"),
            cache_read_per_million=Decimal("1.50"),
            cache_write_per_million=Decimal("18.75"),
        ))
        self.register("anthropic", "claude-haiku-3-5-20241022", ModelPricing(
            input_per_million=Decimal("0.80"),
            output_per_million=Decimal("4"),
            cache_read_per_million=Decimal("0.08"),
            cache_write_per_million=Decimal("1"),
        ))

        # OpenAI models
        self.register("openai", "gpt-4o", ModelPricing(
            input_per_million=Decimal("2.50"),
            output_per_million=Decimal("10"),
        ))
        self.register("openai", "gpt-4o-mini", ModelPricing(
            input_per_million=Decimal("0.15"),
            output_per_million=Decimal("0.60"),
        ))
        self.register("openai", "o3", ModelPricing(
            input_per_million=Decimal("10"),
            output_per_million=Decimal("40"),
        ))

        # AWS Bedrock models (same underlying models, ~20% discount via Bedrock)
        self.register("bedrock", "us.anthropic.claude-sonnet-4-20250514-v1:0", ModelPricing(
            input_per_million=Decimal("3"),
            output_per_million=Decimal("15"),
        ))
        self.register("bedrock", "us.anthropic.claude-haiku-3-5-20241022-v1:0", ModelPricing(
            input_per_million=Decimal("0.80"),
            output_per_million=Decimal("4"),
        ))

        # Ollama / local models (zero cost — running locally)
        self.register("ollama", "llama3.1", ModelPricing(
            input_per_million=Decimal("0"),
            output_per_million=Decimal("0"),
        ))
        self.register("ollama", "mistral", ModelPricing(
            input_per_million=Decimal("0"),
            output_per_million=Decimal("0"),
        ))
