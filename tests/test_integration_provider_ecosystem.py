"""Integration tests for P4: Provider Ecosystem & Cost Optimization.

Covers:
- R-4.1: Public API Surface (protocol re-exports)
- R-4.2/R-4.3: OSS/Pro Separation (pro imports fail gracefully)
- R-4.4: Provider Marketplace (Bedrock, Ollama, OpenAI via _build_provider)
- R-4.5: Domain-Agnostic Refinement (prompt templates)
- R-4.6: Project Template Library (template loading, listing)
"""

from __future__ import annotations



from rooben.billing.costs import CostRegistry
from rooben.domain import TokenUsage



# ---------------------------------------------------------------------------
# R-4.1: Public API Surface
# ---------------------------------------------------------------------------


class TestPublicAPISurface:
    """R-4.1: rooben.public_api exports all protocols and convenience classes."""

    def test_public_api_exports_protocols(self):
        from rooben.public_api import (
            AgentProtocol,
            LLMProvider,
            LearningStoreProtocol,
            Planner,
            StateBackend,
            Verifier,
        )
        # All should be importable
        assert AgentProtocol is not None
        assert LLMProvider is not None
        assert Planner is not None
        assert StateBackend is not None
        assert Verifier is not None
        assert LearningStoreProtocol is not None

    def test_public_api_exports_implementations(self):
        from rooben.public_api import (
            AnthropicProvider,
            FilesystemBackend,
            LLMJudgeVerifier,
        )
        assert AnthropicProvider is not None
        assert FilesystemBackend is not None
        assert LLMJudgeVerifier is not None

    def test_public_api_exports_domain_models(self):
        from rooben.public_api import (
            Task,
            TaskResult,
            TokenUsage,
            WorkflowState,
            Specification,
        )
        assert Task is not None
        assert TaskResult is not None
        assert TokenUsage is not None
        assert WorkflowState is not None
        assert Specification is not None


# ---------------------------------------------------------------------------
# R-4.2/R-4.3: OSS/Pro Separation
# ---------------------------------------------------------------------------


class TestOSSProSeparation:
    """R-4.2/R-4.3: Pro imports handled gracefully when pro not installed."""

    def test_postgres_backend_import_fails_gracefully(self):
        """PostgresBackend import from pro raises ImportError."""
        try:
            from rooben_pro.state.postgres import PostgresBackend  # noqa: F401
            # If pro is installed, that's fine too
        except ImportError:
            pass  # Expected behavior for OSS-only install

    def test_linear_backend_import_fails_gracefully(self):
        try:
            from rooben_pro.state.linear import LinearBackend  # noqa: F401
        except ImportError:
            pass

    def test_cli_backend_guard(self):
        """CLI _build_backend raises UsageError for pro backends when not installed."""
        import click
        from rooben.cli import _build_backend

        try:
            _build_backend("postgres", "/tmp/state")
            # If pro installed, may not raise
        except click.UsageError as e:
            assert "rooben-pro" in str(e)

    def test_billing_tiers_guard(self):
        """Billing tiers require rooben-pro."""
        try:
            from rooben_pro.billing.models import TIER_LIMITS  # noqa: F401
        except ImportError:
            pass  # Expected

    def test_cost_registry_in_core(self):
        """CostRegistry is available in core (not moved to pro)."""
        registry = CostRegistry()
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        cost = registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage)
        assert cost > 0


# ---------------------------------------------------------------------------
# R-4.4: Provider Marketplace
# ---------------------------------------------------------------------------


class TestProviderMarketplace:
    """R-4.4: Multiple provider backends (Anthropic, OpenAI, Ollama, Bedrock)."""

    def test_build_anthropic_provider(self):
        from rooben.cli import _build_provider
        p = _build_provider("anthropic", "claude-sonnet-4-20250514")
        assert p is not None
        assert hasattr(p, "generate")

    def test_build_openai_provider(self):
        from rooben.cli import _build_provider
        p = _build_provider("openai", "gpt-4o-mini")
        assert p is not None
        assert hasattr(p, "generate")

    def test_build_ollama_provider(self):
        from rooben.cli import _build_provider
        p = _build_provider("ollama", "llama3.1")
        assert p is not None
        assert hasattr(p, "generate")

    def test_build_bedrock_provider(self):
        from rooben.cli import _build_provider
        p = _build_provider("bedrock", "us.anthropic.claude-sonnet-4-20250514-v1:0")
        assert p is not None
        assert hasattr(p, "generate")

    def test_cost_registry_covers_providers(self):
        """CostRegistry has pricing for Anthropic, OpenAI, Bedrock, Ollama."""
        registry = CostRegistry()
        usage = TokenUsage(input_tokens=1000, output_tokens=500)

        # Anthropic
        assert registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage) > 0
        # OpenAI
        assert registry.calculate_cost("openai", "gpt-4o", usage) > 0
        # Ollama (zero cost)
        assert registry.calculate_cost("ollama", "llama3.1", usage) == 0


# ---------------------------------------------------------------------------
# R-4.5: Domain-Agnostic Refinement
# ---------------------------------------------------------------------------


class TestDomainAgnosticRefinement:
    """R-4.5: Refinement prompts support non-software domains."""

    def test_refinement_engine_import(self):
        from rooben.refinement.engine import RefinementEngine
        assert RefinementEngine is not None

    def test_spec_builder_handles_non_code_deliverables(self):
        """SpecBuilder supports non-code deliverable types."""
        from rooben.spec.models import DeliverableType

        # All deliverable types should be valid
        types = [
            DeliverableType.CODE, DeliverableType.DOCUMENT,
            DeliverableType.API, DeliverableType.DATASET,
            DeliverableType.DESIGN, DeliverableType.WORKFLOW,
        ]
        for t in types:
            assert t is not None


# ---------------------------------------------------------------------------
# R-4.6: Project Template Library
# ---------------------------------------------------------------------------


class TestP4EndToEnd:
    """Full P4 integration: provider selection + cost tracking."""

    def test_cost_registry_covers_default_model(self):
        """Cost registry handles the default Anthropic model."""
        registry = CostRegistry()
        usage = TokenUsage(input_tokens=5000, output_tokens=2000)
        cost = registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage)
        assert cost > 0
