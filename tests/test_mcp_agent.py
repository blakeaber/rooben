"""Tests for MCP agent support — MCPAgent, MCPClient, and registry integration."""

from __future__ import annotations

import json
import tempfile
from typing import Any
from unittest.mock import patch

import pytest

from rooben.agents.mcp_agent import MCPAgent
from rooben.agents.mcp_client import MCPClient, MCPToolInfo
from rooben.agents.scratchpad import ScratchpadAccumulator
from rooben.agents.registry import AgentRegistry
from rooben.domain import Task, TaskStatus, TokenUsage, WorkflowStatus
from rooben.planning.provider import GenerationResult
from rooben.orchestrator import Orchestrator
from rooben.planning.llm_planner import LLMPlanner
from rooben.spec.models import (
    AgentSpec,
    AgentTransport,
    MCPServerConfig,
    MCPTransportType,
)
from rooben.state.filesystem import FilesystemBackend
from rooben.verification.llm_judge import LLMJudgeVerifier


def _gen(text: str, truncated: bool = False) -> GenerationResult:
    return GenerationResult(
        text=text,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        model="mock-model",
        provider="mock",
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockMCPClient:
    """Mock MCP client that simulates tool discovery and invocation."""

    def __init__(self, tools: list[MCPToolInfo], tool_responses: dict[str, str] | None = None):
        self._tools = tools
        self._tool_responses = tool_responses or {}
        self._calls: list[dict[str, Any]] = []

    async def connect(self) -> None:
        pass

    async def list_tools(self) -> list[MCPToolInfo]:
        return self._tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        self._calls.append({
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments,
        })
        key = f"{server_name}/{tool_name}"
        return self._tool_responses.get(key, f"Result from {key}")

    async def close(self) -> None:
        pass

    @property
    def connected_servers(self) -> list[str]:
        return list({t.server_name for t in self._tools})


class MockLLMProviderForMCP:
    """LLM provider that simulates tool-calling agent behavior."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or []
        self._call_index = 0
        self._calls: list[dict[str, str]] = []

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
        self._calls.append({"system": system, "prompt": prompt})
        if self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return _gen(resp)
        return _gen(json.dumps({
            "final_result": {
                "output": "Default response",
                "artifacts": {},
                "generated_tests": [],
            }
        }))


# ---------------------------------------------------------------------------
# MCPToolInfo tests
# ---------------------------------------------------------------------------

class TestMCPToolInfo:
    def test_to_prompt_dict(self):
        tool = MCPToolInfo(
            server_name="web-search",
            name="search",
            description="Search the web",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        d = tool.to_prompt_dict()
        assert d["server"] == "web-search"
        assert d["tool"] == "search"
        assert d["description"] == "Search the web"
        assert "query" in d["parameters"]["properties"]


# ---------------------------------------------------------------------------
# MCPServerConfig model tests
# ---------------------------------------------------------------------------

class TestMCPServerConfig:
    def test_stdio_config(self):
        config = MCPServerConfig(
            name="local-tools",
            transport_type=MCPTransportType.STDIO,
            command="python",
            args=["-m", "my_mcp_server"],
            env={"API_KEY": "test"},
        )
        assert config.name == "local-tools"
        assert config.transport_type == MCPTransportType.STDIO
        assert config.command == "python"
        assert config.args == ["-m", "my_mcp_server"]

    def test_sse_config(self):
        config = MCPServerConfig(
            name="remote-tools",
            transport_type=MCPTransportType.SSE,
            url="http://localhost:8080/sse",
        )
        assert config.transport_type == MCPTransportType.SSE
        assert config.url == "http://localhost:8080/sse"

    def test_defaults(self):
        config = MCPServerConfig(name="minimal")
        assert config.transport_type == MCPTransportType.STDIO
        assert config.command is None
        assert config.args == []
        assert config.env == {}
        assert config.url is None


# ---------------------------------------------------------------------------
# AgentSpec with MCP servers
# ---------------------------------------------------------------------------

class TestAgentSpecMCP:
    def test_mcp_transport_agent(self):
        spec = AgentSpec(
            id="mcp-agent-1",
            name="MCP Tool Agent",
            transport=AgentTransport.MCP,
            description="Agent backed by MCP servers",
            mcp_servers=[
                MCPServerConfig(
                    name="file-tools",
                    command="python",
                    args=["-m", "file_server"],
                ),
                MCPServerConfig(
                    name="web-tools",
                    transport_type=MCPTransportType.SSE,
                    url="http://localhost:9090/sse",
                ),
            ],
        )
        assert spec.transport == AgentTransport.MCP
        assert len(spec.mcp_servers) == 2
        assert spec.mcp_servers[0].name == "file-tools"
        assert spec.mcp_servers[1].name == "web-tools"

    def test_non_mcp_agent_with_mcp_servers(self):
        """Any agent transport can optionally have mcp_servers."""
        spec = AgentSpec(
            id="http-agent-1",
            name="HTTP Agent With Tools",
            transport=AgentTransport.HTTP,
            endpoint="http://localhost:8000",
            description="HTTP agent with extra MCP tools",
            mcp_servers=[
                MCPServerConfig(name="db-tools", command="db_server"),
            ],
        )
        assert spec.transport == AgentTransport.HTTP
        assert len(spec.mcp_servers) == 1


# ---------------------------------------------------------------------------
# MCPAgent tests (with mocked MCP client)
# ---------------------------------------------------------------------------

class TestMCPAgent:
    @pytest.fixture
    def sample_tools(self):
        return [
            MCPToolInfo(
                server_name="web-search",
                name="search",
                description="Search the web for information",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            ),
            MCPToolInfo(
                server_name="web-search",
                name="fetch_page",
                description="Fetch a web page's content",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            ),
            MCPToolInfo(
                server_name="file-system",
                name="read_file",
                description="Read a file from disk",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),
        ]

    @pytest.fixture
    def sample_task(self):
        return Task(
            id="task-001",
            workstream_id="ws-001",
            workflow_id="wf-001",
            title="Research Python Frameworks",
            description="Search the web for top Python web frameworks and summarize findings.",
            status=TaskStatus.PENDING,
            assigned_agent_id="mcp-agent-1",
            depends_on=[],
            acceptance_criteria_ids=["AC-001"],
            verification_strategy="llm_judge",
            skeleton_tests=[],
            attempt=0,
            max_retries=3,
        )

    @pytest.mark.asyncio
    async def test_single_turn_no_tools(self, sample_task):
        """Agent completes task immediately without tool calls."""
        provider = MockLLMProviderForMCP(responses=[
            json.dumps({
                "final_result": {
                    "output": "Here are the top frameworks: Django, Flask, FastAPI",
                    "artifacts": {"report.md": "# Python Web Frameworks\n..."},
                    "generated_tests": [],
                }
            })
        ])

        mcp_configs = [MCPServerConfig(name="web-search", command="search_server")]

        agent = MCPAgent(
            agent_id="mcp-agent-1",
            mcp_configs=mcp_configs,
            llm_provider=provider,
        )

        # Patch MCPClient to use our mock
        mock_client = MockMCPClient(tools=[], tool_responses={})
        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert result.output == "Here are the top frameworks: Django, Flask, FastAPI"
        assert "report.md" in result.artifacts
        assert result.error is None

    @pytest.mark.asyncio
    async def test_multi_turn_with_tool_calls(self, sample_task, sample_tools):
        """Agent calls tools, gets results, then produces final output."""
        provider = MockLLMProviderForMCP(responses=[
            # Turn 1: Call search tool
            json.dumps({
                "tool_calls": [
                    {
                        "server": "web-search",
                        "tool": "search",
                        "arguments": {"query": "top Python web frameworks 2025"},
                    }
                ]
            }),
            # Turn 2: Call fetch_page tool based on search results
            json.dumps({
                "tool_calls": [
                    {
                        "server": "web-search",
                        "tool": "fetch_page",
                        "arguments": {"url": "https://example.com/frameworks"},
                    }
                ]
            }),
            # Turn 3: Final result
            json.dumps({
                "final_result": {
                    "output": "Research complete. Top frameworks: Django, Flask, FastAPI.",
                    "artifacts": {
                        "frameworks.md": "# Top Python Web Frameworks\n\n1. Django\n2. Flask\n3. FastAPI",
                    },
                    "generated_tests": [],
                }
            }),
        ])

        tool_responses = {
            "web-search/search": "Results: 1. Django 2. Flask 3. FastAPI",
            "web-search/fetch_page": "<html><body>FastAPI is the fastest growing...</body></html>",
        }

        mcp_configs = [MCPServerConfig(name="web-search", command="search_server")]
        mock_client = MockMCPClient(tools=sample_tools, tool_responses=tool_responses)

        agent = MCPAgent(
            agent_id="mcp-agent-1",
            mcp_configs=mcp_configs,
            llm_provider=provider,
        )

        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "call_tool", mock_client.call_tool), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert "Django" in result.output
        assert "frameworks.md" in result.artifacts
        assert result.error is None
        # Verify tools were called
        assert len(mock_client._calls) == 2
        assert mock_client._calls[0]["tool"] == "search"
        assert mock_client._calls[1]["tool"] == "fetch_page"
        # Verify LLM saw tool results in conversation
        assert len(provider._calls) == 3

    @pytest.mark.asyncio
    async def test_max_turns_exceeded(self, sample_task, sample_tools):
        """Agent hits max_turns and returns an error."""
        # LLM always calls tools, never produces final result
        infinite_tool_call = json.dumps({
            "tool_calls": [
                {"server": "web-search", "tool": "search", "arguments": {"query": "more"}}
            ]
        })
        provider = MockLLMProviderForMCP(
            responses=[infinite_tool_call] * 20
        )

        mcp_configs = [MCPServerConfig(name="web-search", command="search_server")]
        mock_client = MockMCPClient(tools=sample_tools, tool_responses={})

        agent = MCPAgent(
            agent_id="mcp-agent-1",
            mcp_configs=mcp_configs,
            llm_provider=provider,
            max_turns=3,
        )

        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "call_tool", mock_client.call_tool), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert result.error is not None
        assert "maximum" in result.error.lower() or "max" in result.error.lower()

    @pytest.mark.asyncio
    async def test_system_prompt_includes_tools(self, sample_tools):
        """Verify the system prompt contains tool descriptions."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        prompt = agent._build_system_prompt(sample_tools)
        assert "web-search" in prompt
        assert "search" in prompt
        assert "fetch_page" in prompt
        assert "read_file" in prompt
        assert "tool_calls" in prompt
        assert "final_result" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_no_tools(self):
        """When no tools are available, use the simplified prompt."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        prompt = agent._build_system_prompt([])
        assert "no tools are currently available" in prompt.lower()

    @pytest.mark.asyncio
    async def test_multiple_tools_per_turn(self, sample_task, sample_tools):
        """Agent can call multiple tools in a single turn."""
        provider = MockLLMProviderForMCP(responses=[
            json.dumps({
                "tool_calls": [
                    {"server": "web-search", "tool": "search", "arguments": {"query": "Django"}},
                    {"server": "web-search", "tool": "search", "arguments": {"query": "Flask"}},
                    {"server": "file-system", "tool": "read_file", "arguments": {"path": "/data/notes.txt"}},
                ]
            }),
            json.dumps({
                "final_result": {
                    "output": "Combined results from all tools",
                    "artifacts": {},
                    "generated_tests": [],
                }
            }),
        ])

        tool_responses = {
            "web-search/search": "Framework info...",
            "file-system/read_file": "Previous notes on frameworks",
        }
        mock_client = MockMCPClient(tools=sample_tools, tool_responses=tool_responses)
        mcp_configs = [MCPServerConfig(name="web-search", command="search_server")]

        agent = MCPAgent(
            agent_id="mcp-agent-1",
            mcp_configs=mcp_configs,
            llm_provider=provider,
        )

        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "call_tool", mock_client.call_tool), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert result.error is None
        # All 3 tools called
        assert len(mock_client._calls) == 3

    @pytest.mark.asyncio
    async def test_llm_generation_failure(self, sample_task, sample_tools):
        """LLM generation failure returns an error TaskResult."""
        class FailingProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                raise RuntimeError("API rate limit exceeded")

        mcp_configs = [MCPServerConfig(name="web-search", command="search_server")]
        mock_client = MockMCPClient(tools=sample_tools, tool_responses={})

        agent = MCPAgent(
            agent_id="mcp-agent-1",
            mcp_configs=mcp_configs,
            llm_provider=FailingProvider(),
        )

        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert result.error is not None
        assert "rate limit" in result.error.lower()


# ---------------------------------------------------------------------------
# AgentRegistry MCP integration tests
# ---------------------------------------------------------------------------

class TestRegistryMCP:
    def test_build_mcp_agent(self):
        """Registry builds MCPAgent for MCP transport."""
        provider = MockLLMProviderForMCP()
        registry = AgentRegistry(llm_provider=provider)

        specs = [
            AgentSpec(
                id="mcp-1",
                name="MCP Agent",
                transport=AgentTransport.MCP,
                description="Agent with MCP tools",
                mcp_servers=[
                    MCPServerConfig(name="tools", command="python", args=["-m", "tool_server"]),
                ],
            ),
        ]
        registry.register_from_specs(specs)

        agent = registry.get("mcp-1")
        assert agent is not None
        assert isinstance(agent, MCPAgent)
        assert agent.agent_id == "mcp-1"

    def test_mcp_agent_requires_llm_provider(self):
        """MCP agents need an LLM provider for tool orchestration."""
        registry = AgentRegistry(llm_provider=None)
        specs = [
            AgentSpec(
                id="mcp-1",
                name="MCP Agent",
                transport=AgentTransport.MCP,
                description="Agent with MCP tools",
                mcp_servers=[
                    MCPServerConfig(name="tools", command="python"),
                ],
            ),
        ]
        with pytest.raises(ValueError, match="LLM provider"):
            registry.register_from_specs(specs)

    def test_mcp_agent_with_empty_servers_falls_through(self):
        """MCP agents with empty servers gracefully fall through to NO_TOOLS_SYSTEM_PROMPT."""
        provider = MockLLMProviderForMCP()
        registry = AgentRegistry(llm_provider=provider)
        specs = [
            AgentSpec(
                id="mcp-1",
                name="MCP Agent",
                transport=AgentTransport.MCP,
                description="Agent with no tools",
                mcp_servers=[],
            ),
        ]
        # Should not raise — gracefully creates MCPAgent with empty configs
        registry.register_from_specs(specs)
        assert registry.get("mcp-1") is not None


# ---------------------------------------------------------------------------
# Full orchestration with MCP agent
# ---------------------------------------------------------------------------

class TestMCPOrchestration:
    @pytest.mark.asyncio
    async def test_mcp_agent_in_orchestration(self, sample_spec):
        """End-to-end test: MCP agent executes tasks via tool calls within orchestrator."""
        from tests.conftest import MockLLMProvider

        # We need to intercept the MCPAgent creation and mock the MCP client
        class MCPOrchestratorProvider(MockLLMProvider):
            """Handles planning, verification, AND MCP agent execution."""

            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                self._calls.append({"system": system, "prompt": prompt})

                if "planning engine" in system.lower():
                    return _gen(self._default_plan)
                elif "quality assurance" in system.lower():
                    return _gen(self._default_judge_response)
                elif "tool_calls" in system.lower() or "available tools" in system.lower():
                    # MCP agent system prompt — return final result directly
                    return _gen(json.dumps({
                        "final_result": {
                            "output": "Task completed using MCP tools",
                            "artifacts": {"result.py": "print('done')"},
                            "generated_tests": [],
                        }
                    }))
                elif "autonomous agent executing" in system.lower():
                    return _gen(self._default_agent_response)
                elif "no tools are currently available" in system.lower():
                    return _gen(json.dumps({
                        "final_result": {
                            "output": "Task completed without tools",
                            "artifacts": {"result.py": "print('done')"},
                            "generated_tests": [],
                        }
                    }))

                return _gen(json.dumps({"output": "ok"}))

        provider = MCPOrchestratorProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)

            # Register agent-1 as an MCP agent
            mcp_configs = [
                MCPServerConfig(name="code-tools", command="python", args=["-m", "code_server"]),
            ]
            # Manually build and register the MCP agent with mocked client
            mock_client = MockMCPClient(
                tools=[
                    MCPToolInfo("code-tools", "write_code", "Write code", {"type": "object"}),
                ],
                tool_responses={"code-tools/write_code": "Code written successfully"},
            )

            mcp_agent = MCPAgent(
                agent_id="agent-1",
                mcp_configs=mcp_configs,
                llm_provider=provider,
            )
            import asyncio
            registry._agents["agent-1"] = mcp_agent
            registry._semaphores["agent-1"] = asyncio.Semaphore(2)

            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=sample_spec.global_budget,
            )

            # Patch the MCPClient methods on the agent
            with patch.object(MCPClient, "connect", mock_client.connect), \
                 patch.object(MCPClient, "list_tools", mock_client.list_tools), \
                 patch.object(MCPClient, "call_tool", mock_client.call_tool), \
                 patch.object(MCPClient, "close", mock_client.close):
                state = await orchestrator.run(sample_spec)

            # Verify completion
            assert len(state.workflows) >= 1
            wf = list(state.workflows.values())[0]
            assert wf.status == WorkflowStatus.COMPLETED
            assert wf.completed_tasks > 0

    @pytest.mark.asyncio
    async def test_mcp_agent_with_tool_loop_in_orchestration(self, sample_spec):
        """MCP agent does multi-turn tool calling within orchestrator."""
        from tests.conftest import MockLLMProvider

        turn_counter = {"count": 0}

        class ToolLoopProvider(MockLLMProvider):
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                self._calls.append({"system": system, "prompt": prompt})

                if "planning engine" in system.lower():
                    return _gen(self._default_plan)
                elif "quality assurance" in system.lower():
                    return _gen(self._default_judge_response)
                elif "available tools" in system.lower() or "no tools" in system.lower():
                    turn_counter["count"] += 1
                    if turn_counter["count"] == 1:
                        # First turn: call a tool
                        return _gen(json.dumps({
                            "tool_calls": [
                                {"server": "code-tools", "tool": "analyze", "arguments": {"code": "x=1"}}
                            ]
                        }))
                    else:
                        # Second turn: final result
                        return _gen(json.dumps({
                            "final_result": {
                                "output": "Analysis complete after tool call",
                                "artifacts": {"analysis.txt": "Code looks good"},
                                "generated_tests": [],
                            }
                        }))
                elif "autonomous agent executing" in system.lower():
                    return _gen(self._default_agent_response)

                return _gen(json.dumps({"output": "ok"}))

        provider = ToolLoopProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)

            mcp_configs = [
                MCPServerConfig(name="code-tools", command="python", args=["-m", "analyzer"]),
            ]
            mock_client = MockMCPClient(
                tools=[MCPToolInfo("code-tools", "analyze", "Analyze code", {"type": "object"})],
                tool_responses={"code-tools/analyze": "No issues found in code"},
            )

            mcp_agent = MCPAgent(
                agent_id="agent-1",
                mcp_configs=mcp_configs,
                llm_provider=provider,
            )
            import asyncio
            registry._agents["agent-1"] = mcp_agent
            registry._semaphores["agent-1"] = asyncio.Semaphore(2)

            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=sample_spec.global_budget,
            )

            with patch.object(MCPClient, "connect", mock_client.connect), \
                 patch.object(MCPClient, "list_tools", mock_client.list_tools), \
                 patch.object(MCPClient, "call_tool", mock_client.call_tool), \
                 patch.object(MCPClient, "close", mock_client.close):
                state = await orchestrator.run(sample_spec)

            wf = list(state.workflows.values())[0]
            assert wf.status == WorkflowStatus.COMPLETED
            # Verify the tool was called
            assert len(mock_client._calls) >= 1
            assert mock_client._calls[0]["tool"] == "analyze"


# ---------------------------------------------------------------------------
# YAML spec loading with MCP servers
# ---------------------------------------------------------------------------

class TestMCPSpecLoading:
    def test_load_spec_with_mcp_agent(self):
        """Verify a YAML spec with MCP agents loads correctly."""
        import yaml
        from rooben.spec.loader import load_spec

        spec_data = {
            "id": "mcp-test-spec",
            "title": "MCP Test",
            "goal": "Test MCP agent loading",
            "deliverables": [
                {
                    "id": "D-001",
                    "name": "Test output",
                    "deliverable_type": "code",
                    "description": "A test artifact",
                }
            ],
            "agents": [
                {
                    "id": "mcp-research",
                    "name": "MCP Research Agent",
                    "transport": "mcp",
                    "description": "Researches topics using web tools",
                    "mcp_servers": [
                        {
                            "name": "brave-search",
                            "transport_type": "stdio",
                            "command": "npx",
                            "args": ["-y", "@anthropic/brave-search-mcp"],
                            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
                        },
                        {
                            "name": "web-fetch",
                            "transport_type": "sse",
                            "url": "http://localhost:3001/sse",
                        },
                    ],
                    "capabilities": ["research", "web-search"],
                    "max_concurrency": 2,
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            spec = load_spec(f.name)

        assert spec.id == "mcp-test-spec"
        assert len(spec.agents) == 1
        agent = spec.agents[0]
        assert agent.transport == AgentTransport.MCP
        assert len(agent.mcp_servers) == 2
        assert agent.mcp_servers[0].name == "brave-search"
        assert agent.mcp_servers[0].command == "npx"
        assert agent.mcp_servers[0].args == ["-y", "@anthropic/brave-search-mcp"]
        assert agent.mcp_servers[1].transport_type == MCPTransportType.SSE
        assert agent.mcp_servers[1].url == "http://localhost:3001/sse"

    def test_load_spec_mixed_transports(self):
        """Spec with both MCP and traditional agents loads correctly."""
        import yaml
        from rooben.spec.loader import load_spec

        spec_data = {
            "id": "mixed-spec",
            "title": "Mixed Transport Test",
            "goal": "Test mixed agent transports",
            "deliverables": [
                {"id": "D-001", "name": "Output", "deliverable_type": "code", "description": "Test"}
            ],
            "agents": [
                {
                    "id": "mcp-agent",
                    "name": "MCP Agent",
                    "transport": "mcp",
                    "description": "Uses MCP tools",
                    "mcp_servers": [
                        {"name": "tools", "command": "tool_server"},
                    ],
                },
                {
                    "id": "http-agent",
                    "name": "HTTP Agent",
                    "transport": "http",
                    "endpoint": "http://localhost:8000",
                    "description": "Traditional HTTP agent",
                },
                {
                    "id": "subprocess-agent",
                    "name": "Local Agent",
                    "transport": "subprocess",
                    "endpoint": "mymodule.run",
                    "description": "Local subprocess agent",
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            spec = load_spec(f.name)

        assert len(spec.agents) == 3
        transports = {a.transport for a in spec.agents}
        assert transports == {AgentTransport.MCP, AgentTransport.HTTP, AgentTransport.SUBPROCESS}


# ---------------------------------------------------------------------------
# Truncation recovery tests
# ---------------------------------------------------------------------------

class TestTruncationRecovery:
    """Tests for smart truncation recovery: fragment accumulation, tool nudge, and JSON repair."""

    @pytest.fixture
    def sample_task(self):
        return Task(
            id="task-trunc",
            workstream_id="ws-001",
            workflow_id="wf-001",
            title="Generate Code",
            description="Generate a large code file.",
            status=TaskStatus.PENDING,
            assigned_agent_id="agent-1",
            depends_on=[],
            acceptance_criteria_ids=[],
            verification_strategy="llm_judge",
            skeleton_tests=[],
            attempt=0,
            max_retries=3,
        )

    @pytest.mark.asyncio
    async def test_no_tools_fragment_concatenation(self, sample_task):
        """No-tools agent: truncated response is accumulated and concatenated."""
        fragment1 = '{"final_result": {"output": "hello '
        fragment2 = 'world", "artifacts": {}, "generated_tests": [], "learnings": []}}'

        class TruncatingProvider:
            def __init__(self):
                self._call_index = 0

            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                self._call_index += 1
                if self._call_index == 1:
                    return _gen(fragment1, truncated=True)
                else:
                    return _gen(fragment2, truncated=False)

        agent = MCPAgent(
            agent_id="agent-1",
            mcp_configs=[],
            llm_provider=TruncatingProvider(),
        )
        result = await agent.execute(sample_task)

        assert result.error is None
        assert result.output == "hello world"

    @pytest.mark.asyncio
    async def test_with_tools_nudge_message(self, sample_task):
        """Tool-equipped agent: first truncation sends nudge, not fragment accumulation."""
        calls: list[dict] = []

        class NudgeCheckProvider:
            def __init__(self):
                self._call_index = 0

            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                calls.append({"prompt": prompt})
                self._call_index += 1
                if self._call_index == 1:
                    # Truncated response with big artifact
                    return _gen('{"final_result": {"output": "big file', truncated=True)
                else:
                    # After nudge, agent uses tools properly
                    return _gen(json.dumps({
                        "final_result": {
                            "output": "Wrote file via tools",
                            "artifacts": {},
                            "generated_tests": [],
                        }
                    }), truncated=False)

        tools = [
            MCPToolInfo("fs", "write_file", "Write a file", {"type": "object"}),
        ]
        mock_client = MockMCPClient(tools=tools)
        mcp_configs = [MCPServerConfig(name="fs", command="fs_server")]

        agent = MCPAgent(
            agent_id="agent-1",
            mcp_configs=mcp_configs,
            llm_provider=NudgeCheckProvider(),
        )

        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "call_tool", mock_client.call_tool), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert result.error is None
        assert result.output == "Wrote file via tools"
        # Second call's prompt should contain the nudge message
        assert "STOP" in calls[1]["prompt"]
        assert "filesystem tools" in calls[1]["prompt"]

    @pytest.mark.asyncio
    async def test_max_continuation_rounds(self, sample_task):
        """Truncation exceeding _MAX_CONTINUATION_ROUNDS returns best-effort result."""

        class AlwaysTruncatingProvider:
            def __init__(self):
                self._call_index = 0

            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                self._call_index += 1
                return _gen(f"fragment{self._call_index} ", truncated=True)

        agent = MCPAgent(
            agent_id="agent-1",
            mcp_configs=[],
            llm_provider=AlwaysTruncatingProvider(),
            max_turns=10,
        )
        result = await agent.execute(sample_task)

        assert result.error is not None
        assert "maximum continuation" in result.error.lower()
        # Should have concatenated all fragments in the output
        assert "fragment1" in result.output
        assert "fragment2" in result.output

    @pytest.mark.asyncio
    async def test_json_repair_missing_closing_brace(self, sample_task):
        """JSON repair fixes truncation that drops a closing brace."""

        class AlmostValidProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                # Missing final closing brace
                return _gen(
                    '{"final_result": {"output": "repaired", "artifacts": {}, '
                    '"generated_tests": [], "learnings": []}',
                    truncated=False,
                )

        agent = MCPAgent(
            agent_id="agent-1",
            mcp_configs=[],
            llm_provider=AlmostValidProvider(),
        )
        result = await agent.execute(sample_task)

        assert result.error is None
        assert result.output == "repaired"

    @pytest.mark.asyncio
    async def test_tool_nudge_then_fragment_accumulation(self, sample_task):
        """Tool agent: nudge fails (still truncates), falls back to fragment accumulation."""
        calls: list[dict] = []

        class StubProvider:
            def __init__(self):
                self._call_index = 0

            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                calls.append({"prompt": prompt})
                self._call_index += 1
                if self._call_index == 1:
                    # First: truncated
                    return _gen('{"final_result": {"output": "part1', truncated=True)
                elif self._call_index == 2:
                    # After nudge: still truncated (nudge failed)
                    return _gen(' part2', truncated=True)
                else:
                    # Continuation completes
                    return _gen(
                        '", "artifacts": {}, "generated_tests": [], "learnings": []}}',
                        truncated=False,
                    )

        tools = [MCPToolInfo("fs", "write_file", "Write a file", {"type": "object"})]
        mock_client = MockMCPClient(tools=tools)
        mcp_configs = [MCPServerConfig(name="fs", command="fs_server")]

        agent = MCPAgent(
            agent_id="agent-1",
            mcp_configs=mcp_configs,
            llm_provider=StubProvider(),
            max_turns=10,
        )

        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "call_tool", mock_client.call_tool), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert result.error is None
        # Fragment concatenation should have joined part2 + completion
        assert "part2" in result.output or result.output != ""

    def test_try_repair_json_method(self):
        """Unit test for _try_repair_json with various truncation patterns."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )

        # Missing closing brace
        result = agent._try_repair_json('{"key": "value"')
        assert result == {"key": "value"}

        # Missing closing quote and brace
        result = agent._try_repair_json('{"key": "value')
        assert result == {"key": "value"}

        # With markdown fences
        result = agent._try_repair_json('```json\n{"key": "value"')
        assert result == {"key": "value"}

        # Completely invalid
        result = agent._try_repair_json('not json at all')
        assert result is None

    @pytest.mark.asyncio
    async def test_multi_json_response_tool_calls_and_final(self, sample_task):
        """Agent returns multiple JSON objects (tool_calls + final_result) in one response."""
        multi_json_response = (
            '{"tool_calls": [{"server": "fs", "tool": "write_file", '
            '"arguments": {"path": "out.py", "content": "print(1)"}}]}\n\n'
            '{"tool_calls": [{"server": "fs", "tool": "write_file", '
            '"arguments": {"path": "readme.md", "content": "# Readme"}}]}\n\n'
            '{"final_result": {"output": "Wrote 2 files via tools", '
            '"artifacts": {}, "generated_tests": [], "learnings": []}}'
        )

        class MultiJsonProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                return _gen(multi_json_response)

        tools = [MCPToolInfo("fs", "write_file", "Write a file", {"type": "object"})]
        mock_client = MockMCPClient(tools=tools)
        mcp_configs = [MCPServerConfig(name="fs", command="fs_server")]

        agent = MCPAgent(
            agent_id="agent-1",
            mcp_configs=mcp_configs,
            llm_provider=MultiJsonProvider(),
        )

        with patch.object(MCPClient, "connect", mock_client.connect), \
             patch.object(MCPClient, "list_tools", mock_client.list_tools), \
             patch.object(MCPClient, "call_tool", mock_client.call_tool), \
             patch.object(MCPClient, "close", mock_client.close):
            result = await agent.execute(sample_task)

        assert result.error is None
        assert result.output == "Wrote 2 files via tools"
        # Both write_file tool calls should have been executed
        write_calls = [c for c in mock_client._calls if c["tool"] == "write_file"]
        assert len(write_calls) == 2
        assert write_calls[0]["arguments"]["path"] == "out.py"
        assert write_calls[1]["arguments"]["path"] == "readme.md"
        # Backfill should have attempted read_file for both written files
        read_calls = [c for c in mock_client._calls if c["tool"] == "read_file"]
        assert len(read_calls) == 2

    def test_parse_multi_json(self):
        """Unit test for parse_llm_json_multi with multiple JSON objects."""
        from rooben.utils import parse_llm_json_multi

        # Single object
        assert len(parse_llm_json_multi('{"key": "value"}')) == 1

        # Multiple objects
        raw = '{"a": 1}\n\n{"b": 2}\n\n{"c": 3}'
        results = parse_llm_json_multi(raw)
        assert len(results) == 3
        assert results[0] == {"a": 1}
        assert results[1] == {"b": 2}
        assert results[2] == {"c": 3}

        # With markdown fences
        raw = '```json\n{"a": 1}\n{"b": 2}\n```'
        results = parse_llm_json_multi(raw)
        assert len(results) == 2

        # Empty / invalid
        assert parse_llm_json_multi("not json") == []

        # Nested braces in strings shouldn't confuse parser
        raw = '{"content": "function() { return {} }"}\n{"other": true}'
        results = parse_llm_json_multi(raw)
        assert len(results) == 2
        assert results[0]["content"] == "function() { return {} }"

    def test_system_prompt_one_file_per_turn(self):
        """Verify system prompt enforces one-file-per-turn and includes max_tokens."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
            max_tokens=16384,
        )
        tools = [MCPToolInfo("fs", "write_file", "Write a file", {"type": "object"})]
        prompt = agent._build_system_prompt(tools)
        assert "ONE file" in prompt
        assert "16384" in prompt
        assert str(16384 * 4) in prompt  # max_chars
        assert "Do NOT batch" in prompt

    def test_compact_messages_tool_results(self):
        """Verify _compact_messages keeps first and last 2, summarizes middle."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        messages: list[dict[str, str]] = [
            {"role": "user", "content": "Task: build something"},
        ]
        # Add 10 tool result / response pairs (alternating user/assistant)
        for i in range(10):
            messages.append(
                {"role": "assistant", "content": f"Writing file_{i}.py..."}
            )
            messages.append(
                {"role": "user", "content": f"Tool results:\n[{i+1}] filesystem/write_file: Successfully wrote to /workspace/file_{i}.py"}
            )

        result = agent._compact_messages(messages)
        # First message should contain the original task
        assert "Task: build something" in result[0]["content"]
        # Should mention compaction somewhere
        all_content = " ".join(m["content"] for m in result)
        assert "[Conversation compacted" in all_content
        assert "Files written so far" in all_content
        # Should be much shorter than original
        assert len(result) < len(messages)

    def test_token_estimation(self):
        """Verify _estimate_tokens returns reasonable values."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        # 400 chars at ~3 chars/token should be ~133 tokens
        parts = ["a" * 400]
        assert agent._estimate_tokens(parts) == 133

        # Empty
        assert agent._estimate_tokens([]) == 0

        # Multiple parts: (100 + 300) / 3 = 133
        parts = ["a" * 100, "b" * 300]
        assert agent._estimate_tokens(parts) == 133

    def test_compact_messages_preserves_first_and_last(self):
        """Verify _compact_messages preserves first and last entries."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        messages = [
            {"role": "user", "content": "Task: build an API"},
            {"role": "assistant", "content": "Some middle context 1"},
            {"role": "user", "content": "Some middle context 2"},
            {"role": "assistant", "content": "Some middle context 3"},
            {"role": "user", "content": "Recent context"},
            {"role": "assistant", "content": "Most recent context"},
        ]
        result = agent._compact_messages(messages)
        assert result[0]["content"] == "Task: build an API"
        assert result[-1]["content"] == "Most recent context"
        assert result[-2]["content"] == "Recent context"
        summary_msgs = [m for m in result if "[Conversation compacted" in m["content"]]
        assert len(summary_msgs) == 1

    def test_fix_message_alternation(self):
        """Verify _fix_message_alternation merges consecutive same-role messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "More context"},
            {"role": "assistant", "content": "Response"},
            {"role": "assistant", "content": "More response"},
            {"role": "user", "content": "Follow-up"},
        ]
        result = MCPAgent._fix_message_alternation(messages)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert "Hello" in result[0]["content"] and "More context" in result[0]["content"]
        assert result[1]["role"] == "assistant"
        assert "Response" in result[1]["content"] and "More response" in result[1]["content"]
        assert result[2]["role"] == "user"
        assert result[2]["content"] == "Follow-up"

    def test_compaction_uses_scratchpad_summary(self):
        """Verify compacted messages contain scratchpad output when provided."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        scratchpad = ScratchpadAccumulator(workspace_dir="/workspace")
        scratchpad.record_file_write(1, "/workspace/app.py", "Main application")
        scratchpad.record_decision(2, "Chose Flask over FastAPI")
        scratchpad.record_error(3, "Missing directory", "created it")

        messages: list[dict[str, str]] = [
            {"role": "user", "content": "Task: build something"},
        ]
        for i in range(10):
            messages.append({"role": "assistant", "content": f"Writing file_{i}.py..."})
            messages.append({"role": "user", "content": f"Tool results:\n[{i+1}] ok"})

        result = agent._compact_messages(messages, scratchpad)
        all_content = " ".join(m["content"] for m in result)
        # Should use scratchpad summary, not fallback
        assert "## Files Written" in all_content
        assert "/workspace/app.py" in all_content
        assert "## Key Decisions" in all_content
        assert "Chose Flask" in all_content

    def test_compaction_fallback_without_scratchpad(self):
        """Verify compaction falls back to message parsing when no scratchpad."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        messages: list[dict[str, str]] = [
            {"role": "user", "content": "Task: build something"},
        ]
        for i in range(10):
            messages.append({"role": "assistant", "content": f"Writing file_{i}.py..."})
            messages.append({"role": "user", "content": f"Tool results:\n[{i+1}] filesystem/write_file: Successfully wrote to /workspace/file_{i}.py"})

        result = agent._compact_messages(messages)
        all_content = " ".join(m["content"] for m in result)
        assert "[Conversation compacted" in all_content
        assert "Files written so far" in all_content

    def test_scratchpad_graceful_no_workspace(self):
        """Verify scratchpad works when workspace_dir is None."""
        scratchpad = ScratchpadAccumulator(workspace_dir=None)
        scratchpad.record_file_write(1, "/app.py")
        assert scratchpad.scratchpad_path is None
        # Should still produce a valid summary
        summary = scratchpad.to_compact_summary()
        assert "[Conversation compacted" in summary
        assert "/app.py" in summary

    @pytest.mark.asyncio
    async def test_scratchpad_flush_integration(self):
        """Verify _flush_scratchpad calls write_file on the MCP client."""
        cfg = MCPServerConfig(
            name="filesystem",
            transport=MCPTransportType.STDIO,
            command="node",
            args=["server.js", "/workspace"],
        )
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[cfg],
            llm_provider=MockLLMProviderForMCP(),
        )
        scratchpad = ScratchpadAccumulator(workspace_dir="/workspace")
        scratchpad.record_file_write(1, "/workspace/app.py")

        mock_client = MockMCPClient([], {})
        await agent._flush_scratchpad(mock_client, scratchpad)

        # Verify write_file was called
        assert len(mock_client._calls) == 1
        call = mock_client._calls[0]
        assert call["tool"] == "write_file"
        assert call["arguments"]["path"] == "/workspace/.scratchpad.md"
        assert "# Agent Scratchpad" in call["arguments"]["content"]
        assert scratchpad._flushed is True

    @pytest.mark.asyncio
    async def test_scratchpad_flush_no_filesystem_server(self):
        """Verify _flush_scratchpad is a no-op when no filesystem server configured."""
        cfg = MCPServerConfig(
            name="shell",
            transport=MCPTransportType.STDIO,
            command="node",
            args=["shell-server.js"],
        )
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[cfg],
            llm_provider=MockLLMProviderForMCP(),
        )
        scratchpad = ScratchpadAccumulator(workspace_dir="/workspace")
        scratchpad.record_file_write(1, "/workspace/app.py")

        mock_client = MockMCPClient([], {})
        await agent._flush_scratchpad(mock_client, scratchpad)

        assert len(mock_client._calls) == 0
        assert scratchpad._flushed is False

    @pytest.mark.asyncio
    async def test_backfill_budget_limit(self):
        """Verify backfill respects per-file and total budget limits."""
        from rooben.agents.mcp_agent import AgentExecutionConfig
        cfg = AgentExecutionConfig()
        _BACKFILL_TOTAL_BUDGET = cfg.backfill_total_budget
        _BACKFILL_PER_FILE = cfg.backfill_per_file

        # Create a mock client that returns large file contents
        # Total must exceed _BACKFILL_TOTAL_BUDGET (200K) to trigger budget limit
        large_content = "x" * 20000
        tool_responses = {}
        written_files = []
        for i in range(15):
            path = f"/workspace/file_{i}.py"
            written_files.append(path)
            tool_responses["filesystem/read_file"] = large_content

        mock_client = MockMCPClient([], tool_responses)

        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        from rooben.domain import TaskResult
        result = TaskResult(output="done", artifacts={})
        await agent._backfill_artifacts(mock_client, result, written_files)

        # Check per-file truncation: no artifact exceeds _BACKFILL_PER_FILE + truncation marker
        for path, content in result.artifacts.items():
            if content != "(content omitted — total artifact budget exceeded)":
                assert len(content) <= _BACKFILL_PER_FILE + len("\n... (truncated)")

        # Check that some files got budget-exceeded placeholder
        budget_exceeded = [
            p for p, c in result.artifacts.items()
            if c == "(content omitted — total artifact budget exceeded)"
        ]
        assert len(budget_exceeded) > 0  # Some files should be omitted

    @pytest.mark.asyncio
    async def test_write_calls_limited_per_turn(self):
        """Verify _execute_tool_calls enforces max write calls per turn."""
        from rooben.agents.mcp_agent import AgentExecutionConfig
        _MAX_WRITE_CALLS_PER_TURN = AgentExecutionConfig().max_write_calls_per_turn

        tools = [MCPToolInfo("filesystem", "write_file", "Write a file", {"type": "object"})]
        mock_client = MockMCPClient(tools, {"filesystem/write_file": "OK"})

        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )

        # Try to batch 10 write_file calls
        tool_calls = [
            {"server": "filesystem", "tool": "write_file", "arguments": {"path": f"/workspace/file_{i}.py", "content": f"# file {i}"}}
            for i in range(10)
        ]
        results_str, written_files = await agent._execute_tool_calls(mock_client, tool_calls)

        # Only _MAX_WRITE_CALLS_PER_TURN should have been executed
        assert len(written_files) == _MAX_WRITE_CALLS_PER_TURN
        assert "deferred" in results_str.lower()
        # The mock client should only have received limited calls
        write_calls = [c for c in mock_client._calls if c["tool"] == "write_file"]
        assert len(write_calls) == _MAX_WRITE_CALLS_PER_TURN

    def test_turn0_max_tokens_reduced(self):
        """Verify turn 0 uses reduced max_tokens for tool-equipped agents."""
        from rooben.agents.mcp_agent import AgentExecutionConfig
        cfg = AgentExecutionConfig()
        assert cfg.turn0_max_tokens == 12288
        assert cfg.turn0_max_tokens < 16384

    def test_compaction_threshold_lowered(self):
        """Verify compaction threshold is low enough to fire in practice."""
        from rooben.agents.mcp_agent import AgentExecutionConfig
        cfg = AgentExecutionConfig()
        assert cfg.compaction_threshold == 20_000
        assert cfg.compaction_threshold * 3 < 200_000  # chars < context window

    def test_workspace_prompt_discourages_listing(self):
        """Verify workspace note tells agent NOT to call list_allowed_directories."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@anthropic/mcp-filesystem", "/workspace/test"],
                transport=MCPTransportType.STDIO,
            )],
            llm_provider=MockLLMProviderForMCP(),
        )
        tools = [MCPToolInfo("filesystem", "write_file", "Write a file", {"type": "object"})]
        prompt = agent._build_system_prompt(tools)
        assert "Do NOT call list_allowed_directories" in prompt
        assert "/workspace/test" in prompt
        assert "cd /workspace/test &&" in prompt

    def test_connect_lock_exists(self):
        """Verify MCPAgent has a class-level connection lock mechanism."""
        import asyncio
        lock = MCPAgent._get_connect_lock()
        assert isinstance(lock, asyncio.Lock)
        # Same lock returned on subsequent calls
        assert MCPAgent._get_connect_lock() is lock

    @pytest.mark.asyncio
    async def test_connect_lock_serializes(self):
        """Verify concurrent executions serialize MCP connections via lock."""
        import asyncio
        connect_order: list[str] = []

        class SlowConnectClient:
            def __init__(self, agent_id):
                self._id = agent_id
            async def connect(self):
                connect_order.append(f"{self._id}_start")
                await asyncio.sleep(0.01)  # Simulate connection time
                connect_order.append(f"{self._id}_end")
            async def list_tools(self):
                return []
            async def close(self):
                pass
            @property
            def connected_servers(self):
                return ["test"]

        # Reset the lock for this test
        MCPAgent._connect_lock = None

        # Patch MCPClient to use our slow mock
        configs = [MCPServerConfig(
            name="test", command="echo", args=[],
            transport=MCPTransportType.STDIO,
        )]
        agent_a = MCPAgent(agent_id="a", mcp_configs=configs, llm_provider=MockLLMProviderForMCP())
        agent_b = MCPAgent(agent_id="b", mcp_configs=configs, llm_provider=MockLLMProviderForMCP())

        # Mock MCPClient construction and the agentic loop
        with patch("rooben.agents.mcp_agent.MCPClient") as mock_cls:
            mock_cls.side_effect = lambda configs: SlowConnectClient(
                "a" if not connect_order or connect_order[-1].startswith("a") else "b"
            )
            # Track which agent the client is for
            call_count = {"n": 0}
            _original_side_effect = mock_cls.side_effect
            def tracked_side_effect(configs):
                call_count["n"] += 1
                client = SlowConnectClient(f"agent_{call_count['n']}")
                return client
            mock_cls.side_effect = tracked_side_effect

            # Mock the agentic loop to return immediately
            from rooben.domain import TaskResult as TR
            async def quick_loop(task, client, tools, start):
                return TR(output="done")

            agent_a._agentic_loop = quick_loop
            agent_b._agentic_loop = quick_loop

            task_a = Task(id="t-a", title="A", description="Task A", workflow_id="w1", workstream_id="ws1")
            task_b = Task(id="t-b", title="B", description="Task B", workflow_id="w1", workstream_id="ws1")

            await asyncio.gather(agent_a.execute(task_a), agent_b.execute(task_b))

        # Verify connections were serialized (agent_1_end before agent_2_start)
        assert connect_order[0] == "agent_1_start"
        assert connect_order[1] == "agent_1_end"
        assert connect_order[2] == "agent_2_start"
        assert connect_order[3] == "agent_2_end"

        # Reset for other tests
        MCPAgent._connect_lock = None


class TestAutoMkdir:
    """Tests for automatic parent directory creation."""

    @pytest.mark.asyncio
    async def test_ensure_directories_creates_parents(self):
        """_ensure_directories creates each level of a nested path."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        created: list[str] = []

        class DirTracker:
            async def call_tool(self, server, tool, args):
                created.append(args["path"])
                return "OK"

        await agent._ensure_directories(DirTracker(), "fs", "/workspace/src/api/models")
        assert "/workspace" in created
        assert "/workspace/src" in created
        assert "/workspace/src/api" in created
        assert "/workspace/src/api/models" in created

    @pytest.mark.asyncio
    async def test_auto_mkdir_on_write_failure(self):
        """write_file auto-retries after creating parent directories."""
        call_log: list[tuple[str, str]] = []
        write_attempts = {"n": 0}

        class AutoMkdirClient:
            async def call_tool(self, server, tool, args):
                call_log.append((tool, args.get("path", "")))
                if tool == "write_file":
                    write_attempts["n"] += 1
                    if write_attempts["n"] == 1:
                        return "Tool error: Parent directory does not exist: /ws/src/api"
                    return "Successfully wrote to /ws/src/api/main.py"
                if tool == "create_directory":
                    return "OK"
                return "OK"

        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=MockLLMProviderForMCP(),
        )
        tool_calls = [{"server": "fs", "tool": "write_file", "arguments": {"path": "/ws/src/api/main.py"}}]
        result_text, written = await agent._execute_tool_calls(AutoMkdirClient(), tool_calls)

        # Should have retried after creating dirs
        assert write_attempts["n"] == 2
        assert "/ws/src/api/main.py" in written
        assert "Successfully wrote" in result_text

    def test_system_prompt_includes_directory_guidance(self):
        """System prompt tells agents to create directories one level at a time."""
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@anthropic/mcp-filesystem", "/workspace"],
                transport=MCPTransportType.STDIO,
            )],
            llm_provider=MockLLMProviderForMCP(),
        )
        tools = [MCPToolInfo("filesystem", "write_file", "Write a file", {"type": "object"})]
        prompt = agent._build_system_prompt(tools)
        assert "create_directory" in prompt
        assert "ONE level at a time" in prompt


class TestInvalidJsonRecovery:
    """Tests for graceful invalid_json nudge and recovery."""

    @pytest.mark.asyncio
    async def test_invalid_json_nudge_and_recovery(self):
        """Agent recovers after receiving prose then valid JSON."""
        valid_response = json.dumps({
            "final_result": {
                "output": "Recovered successfully",
                "artifacts": {},
                "generated_tests": [],
            }
        })
        provider = MockLLMProviderForMCP(responses=[
            "Sure, I can help with that!",  # prose, not JSON
            valid_response,
        ])
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=provider,
        )
        task = Task(
            id="t-1", title="Test", description="Test task",
            workflow_id="wf-1", workstream_id="ws-1",
        )
        result = await agent._agentic_loop(task, None, [], 0.0)
        assert result.output == "Recovered successfully"
        # Verify the nudge message was sent
        assert len(provider._calls) == 2

    @pytest.mark.asyncio
    async def test_invalid_json_exhausted(self):
        """Agent terminates gracefully after 3 consecutive invalid JSON responses."""
        provider = MockLLMProviderForMCP(responses=[
            "Not JSON at all",
            "Still not JSON",
            "Nope, still prose",
        ])
        agent = MCPAgent(
            agent_id="test",
            mcp_configs=[],
            llm_provider=provider,
        )
        task = Task(
            id="t-1", title="Test", description="Test task",
            workflow_id="wf-1", workstream_id="ws-1",
        )
        result = await agent._agentic_loop(task, None, [], 0.0)
        # Should return the raw output, not crash
        assert "Nope, still prose" in result.output
        assert len(provider._calls) == 3
