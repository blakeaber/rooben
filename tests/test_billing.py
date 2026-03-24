"""Tests for WS-5.1: Multi-Provider Cost Registry."""

from __future__ import annotations

from decimal import Decimal

import pytest

from rooben.billing.costs import CostRegistry, ModelPricing
from rooben.domain import TokenUsage
from rooben.security.budget import BudgetExceeded, BudgetTracker


class TestCostRegistry:
    def test_anthropic_pricing(self):
        registry = CostRegistry()
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)
        cost = registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage)
        # Input: 1M * $3/M = $3.00
        # Output: 500K * $15/M = $7.50
        assert cost == Decimal("10.500000")

    def test_openai_pricing(self):
        registry = CostRegistry()
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = registry.calculate_cost("openai", "gpt-4o", usage)
        # Input: 1M * $2.50/M = $2.50
        # Output: 1M * $10/M = $10.00
        assert cost == Decimal("12.500000")

    def test_custom_model(self):
        registry = CostRegistry()
        registry.register("custom", "my-model", ModelPricing(
            input_per_million=Decimal("1"),
            output_per_million=Decimal("2"),
        ))
        usage = TokenUsage(input_tokens=100_000, output_tokens=50_000)
        cost = registry.calculate_cost("custom", "my-model", usage)
        # Input: 100K * $1/M = $0.10
        # Output: 50K * $2/M = $0.10
        assert cost == Decimal("0.200000")

    def test_unknown_model_returns_zero(self):
        registry = CostRegistry()
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        cost = registry.calculate_cost("unknown", "nonexistent", usage)
        assert cost == Decimal("0")

    def test_cache_pricing(self):
        registry = CostRegistry()
        usage = TokenUsage(
            input_tokens=0, output_tokens=0,
            cache_read_tokens=1_000_000,
            cache_creation_tokens=500_000,
        )
        cost = registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage)
        # Cache read: 1M * $0.30/M = $0.30
        # Cache write: 500K * $3.75/M = $1.875
        assert cost == Decimal("2.175000")


class TestBudgetTrackerCostEnforcement:
    @pytest.mark.asyncio
    async def test_cost_budget_enforcement(self):
        tracker = BudgetTracker(max_cost_usd=Decimal("1.00"))
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        await tracker.record_llm_usage("anthropic", "model", usage, Decimal("0.50"))
        assert tracker.total_cost_usd == Decimal("0.50")

        with pytest.raises(BudgetExceeded, match="cost_usd"):
            await tracker.record_llm_usage("anthropic", "model", usage, Decimal("0.60"))

    @pytest.mark.asyncio
    async def test_cost_callback_wiring(self):
        tracker = BudgetTracker()
        callback_calls: list[dict] = []

        async def mock_callback(provider, model, usage, cost):
            callback_calls.append({
                "provider": provider, "model": model,
                "tokens": usage.total, "cost": cost,
            })

        tracker.register_cost_callback(mock_callback)
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        await tracker.record_llm_usage("anthropic", "model", usage, Decimal("0.01"))

        assert len(callback_calls) == 1
        assert callback_calls[0]["provider"] == "anthropic"
        assert callback_calls[0]["cost"] == Decimal("0.01")
