"""Tests for WS-1.1: Actual Token Usage Tracking."""

from __future__ import annotations

import json

import pytest

from rooben.domain import Task, TokenUsage
from rooben.planning.provider import GenerationResult


class TestTokenUsage:
    def test_total_computed(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total == 150

    def test_addition(self):
        a = TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=10)
        b = TokenUsage(input_tokens=200, output_tokens=100, cache_creation_tokens=5)
        combined = a + b
        assert combined.input_tokens == 300
        assert combined.output_tokens == 150
        assert combined.cache_read_tokens == 10
        assert combined.cache_creation_tokens == 5
        assert combined.total == 450

    def test_default_zero(self):
        usage = TokenUsage()
        assert usage.total == 0


class TestGenerationResult:
    def test_fields(self):
        gr = GenerationResult(
            text="hello",
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        assert gr.text == "hello"
        assert gr.usage.total == 15
        assert gr.model == "claude-sonnet-4-20250514"
        assert gr.provider == "anthropic"


class TestProviderReturnsTokenUsage:
    @pytest.mark.asyncio
    async def test_provider_returns_token_usage(self, mock_provider):
        """Mock provider returns GenerationResult with usage."""
        result = await mock_provider.generate(
            system="test",
            prompt="test",
            max_tokens=100,
        )
        assert isinstance(result, GenerationResult)
        assert result.usage.input_tokens > 0
        assert result.usage.output_tokens > 0
        assert result.usage.total > 0


class TestMCPAgentNoToolsPopulatesUsage:
    @pytest.mark.asyncio
    async def test_mcp_agent_no_tools_populates_usage(self, mock_provider):
        """MCPAgent with no servers populates token_usage and token_usage_detailed."""
        from rooben.agents.mcp_agent import MCPAgent

        agent = MCPAgent(agent_id="test-agent", mcp_configs=[], llm_provider=mock_provider)
        task = Task(
            id="task-1",
            workstream_id="ws-1",
            workflow_id="wf-1",
            title="Test Task",
            description="Do something",
        )
        result = await agent.execute(task)

        assert result.token_usage > 0
        assert result.token_usage_detailed is not None
        assert result.token_usage_detailed.input_tokens > 0
        assert result.token_usage == result.token_usage_detailed.total


class TestMCPAgentAccumulatesAcrossTurns:
    @pytest.mark.asyncio
    async def test_mcp_agent_accumulates_across_turns(self):
        """MCP agent accumulates token usage across multiple turns."""
        from unittest.mock import patch

        from rooben.agents.mcp_agent import MCPAgent
        from rooben.agents.mcp_client import MCPClient, MCPToolInfo
        from rooben.spec.models import MCPServerConfig

        turn = {"count": 0}

        class MultiTurnProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                turn["count"] += 1
                usage = TokenUsage(input_tokens=100 * turn["count"], output_tokens=50)
                if turn["count"] < 3:
                    text = json.dumps({
                        "tool_calls": [{"server": "s", "tool": "t", "arguments": {}}]
                    })
                else:
                    text = json.dumps({
                        "final_result": {
                            "output": "done",
                            "artifacts": {},
                            "generated_tests": [],
                        }
                    })
                return GenerationResult(text=text, usage=usage, model="m", provider="p")

        class MockClient:
            async def connect(self): pass
            async def list_tools(self):
                return [MCPToolInfo("s", "t", "desc", {})]
            async def call_tool(self, server, tool, args):
                return "ok"
            async def close(self): pass
            @property
            def connected_servers(self): return ["s"]

        mock = MockClient()
        agent = MCPAgent(
            agent_id="mcp-1",
            mcp_configs=[MCPServerConfig(name="s", command="cmd")],
            llm_provider=MultiTurnProvider(),
        )

        task = Task(
            id="task-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Test", description="Do it",
        )

        with patch.object(MCPClient, "connect", mock.connect), \
             patch.object(MCPClient, "list_tools", mock.list_tools), \
             patch.object(MCPClient, "call_tool", mock.call_tool), \
             patch.object(MCPClient, "close", mock.close):
            result = await agent.execute(task)

        assert turn["count"] == 3
        # Accumulated: (100+50) + (200+50) + (300+50) = 750
        assert result.token_usage_detailed is not None
        assert result.token_usage_detailed.input_tokens == 600  # 100+200+300
        assert result.token_usage_detailed.output_tokens == 150  # 50*3
        assert result.token_usage == 750


class TestBudgetSummaryBreakdown:
    @pytest.mark.asyncio
    async def test_budget_summary_breakdown(self):
        """Budget summary includes per-agent and per-task stats."""
        from rooben.security.budget import BudgetTracker

        tracker = BudgetTracker(max_total_tokens=100000)
        await tracker.record_tokens(100, agent_id="agent-a")
        await tracker.record_tokens(200, agent_id="agent-a")
        await tracker.record_tokens(300, agent_id="agent-b")

        summary = tracker.summary()
        assert summary["tokens_used"] == 600
        assert summary["per_agent_tokens"]["agent-a"] == 300
        assert summary["per_agent_tokens"]["agent-b"] == 300
        assert summary["per_task_stats"]["count"] == 3
        assert summary["per_task_stats"]["avg"] == 200
        assert summary["per_task_stats"]["min"] == 100
        assert summary["per_task_stats"]["max"] == 300


class TestPerTaskBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_per_task_budget_enforcement(self):
        """BudgetExceeded raised when token limit exceeded."""
        from rooben.security.budget import BudgetExceeded, BudgetTracker

        tracker = BudgetTracker(max_total_tokens=500)
        await tracker.record_tokens(300)
        with pytest.raises(BudgetExceeded, match="tokens"):
            await tracker.record_tokens(300)
