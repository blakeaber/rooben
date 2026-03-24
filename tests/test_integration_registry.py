"""Tests for the integration registry — two-phase resolver + external-only registry."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from rooben.agents.integrations import (
    IntegrationDefinition,
    IntegrationRegistry,
    load_user_integrations,
    resolve_system_capabilities,
)
from rooben.spec.models import (
    AgentSpec,
    AgentTransport,
    FetchCapability,
    MCPServerConfig,
    MCPTransportType,
    MemoryCapability,
    ShellCapability,
    SystemCapabilities,
)


def _agent(
    capabilities: list[str] | None = None,
    integrations: list[str] | None = None,
    mcp_servers: list[MCPServerConfig] | None = None,
    system_capabilities: SystemCapabilities | None = None,
) -> AgentSpec:
    """Helper to build a minimal AgentSpec for testing."""
    return AgentSpec(
        id="test-agent",
        name="Test Agent",
        transport=AgentTransport.LLM,
        description="Test agent",
        capabilities=capabilities or [],
        integrations=integrations or [],
        mcp_servers=mcp_servers or [],
        system_capabilities=system_capabilities,
    )


# ---------------------------------------------------------------------------
# SystemCapabilities schema tests
# ---------------------------------------------------------------------------


class TestSystemCapabilitiesSchema:
    def test_default_none(self):
        agent = _agent()
        assert agent.system_capabilities is None

    def test_empty_capabilities_always_has_filesystem(self):
        caps = SystemCapabilities()
        servers = resolve_system_capabilities(caps, "/tmp/ws")
        assert any(s.name == "filesystem" for s in servers)
        assert not any(s.name == "shell" for s in servers)

    def test_shell_includes_filesystem(self):
        caps = SystemCapabilities(shell=ShellCapability())
        servers = resolve_system_capabilities(caps, "/tmp/ws")
        names = {s.name for s in servers}
        assert "filesystem" in names
        assert "shell" in names

    def test_fetch_also_gets_filesystem(self):
        caps = SystemCapabilities(fetch=FetchCapability())
        servers = resolve_system_capabilities(caps, "/tmp/ws")
        assert any(s.name == "fetch" for s in servers)
        assert any(s.name == "filesystem" for s in servers)

    def test_memory_only(self):
        caps = SystemCapabilities(memory=MemoryCapability())
        servers = resolve_system_capabilities(caps, "/tmp/ws")
        assert len(servers) >= 1
        assert any(s.name == "memory" for s in servers)

    def test_all_capabilities(self):
        caps = SystemCapabilities(
            shell=ShellCapability(),
            memory=MemoryCapability(),
            fetch=FetchCapability(),
        )
        servers = resolve_system_capabilities(caps, "/tmp/ws")
        names = {s.name for s in servers}
        assert "filesystem" in names
        assert "shell" in names
        assert "memory" in names
        assert "fetch" in names

    def test_none_capabilities_returns_empty(self):
        servers = resolve_system_capabilities(None, "/tmp/ws")
        assert servers == []

    def test_serialization_roundtrip(self):
        caps = SystemCapabilities(
            shell=ShellCapability(scope="workspace"),
            fetch=FetchCapability(),
        )
        data = caps.model_dump()
        restored = SystemCapabilities.model_validate(data)
        assert restored.shell.scope == "workspace"
        assert restored.fetch.enabled is True


# ---------------------------------------------------------------------------
# Registry tests — external-only
# ---------------------------------------------------------------------------


class TestRegistryContents:
    def test_default_integrations_registered(self):
        registry = IntegrationRegistry()
        all_integrations = registry.list_all()
        names = {i.name for i in all_integrations}
        # LLM providers + built-in external integrations
        assert names == {"anthropic", "openai", "ollama", "bedrock", "brave-search"}

    def test_no_builtin_mcp_integrations(self):
        """Builtins (coding, writing, minimal, etc.) are gone."""
        registry = IntegrationRegistry()
        assert registry.get("coding") is None
        assert registry.get("writing") is None
        assert registry.get("minimal") is None
        assert registry.get("data") is None
        assert registry.get("web-research") is None
        assert registry.get("full-stack") is None

    def test_register_external_integration(self):
        registry = IntegrationRegistry()
        registry.register(IntegrationDefinition(
            name="test-integration",
            description="Test",
            domain_tags=["test"],
            cost_tier=1,
            mcp_server_factory=lambda _ws: [],
            source="extension",
        ))
        assert registry.get("test-integration") is not None


# ---------------------------------------------------------------------------
# Two-phase resolver tests
# ---------------------------------------------------------------------------


class TestTwoPhaseResolver:
    def test_prepopulated_mcp_servers_not_overwritten(self):
        registry = IntegrationRegistry()
        custom_server = MCPServerConfig(
            name="custom",
            transport_type=MCPTransportType.STDIO,
            command="echo",
            args=["hello"],
        )
        agent = _agent(mcp_servers=[custom_server])
        name, servers = registry.resolve_for_agent(agent, "/tmp/ws")
        assert name == "custom"
        assert servers == [custom_server]

    def test_system_capabilities_resolved(self):
        registry = IntegrationRegistry()
        agent = _agent(
            system_capabilities=SystemCapabilities(
                shell=ShellCapability(),
            ),
        )
        name, servers = registry.resolve_for_agent(agent, "/tmp/ws")
        assert name == "system"
        names = {s.name for s in servers}
        assert "filesystem" in names
        assert "shell" in names

    def test_external_integration_resolved(self):
        registry = IntegrationRegistry()
        registry.register(IntegrationDefinition(
            name="github-issues",
            description="GitHub Issues",
            domain_tags=["software"],
            cost_tier=2,
            mcp_server_factory=lambda _ws: [MCPServerConfig(
                name="github",
                transport_type=MCPTransportType.STDIO,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-github"],
            )],
            source="extension",
        ))
        agent = _agent(integrations=["github-issues"])
        name, servers = registry.resolve_for_agent(agent, "/tmp/ws")
        assert name == "github-issues"
        assert any(s.name == "github" for s in servers)

    def test_system_caps_plus_external_combined(self):
        """Both system capabilities and external integration produce combined servers."""
        registry = IntegrationRegistry()
        registry.register(IntegrationDefinition(
            name="slack",
            description="Slack",
            domain_tags=["operations"],
            cost_tier=2,
            mcp_server_factory=lambda _ws: [MCPServerConfig(
                name="slack",
                transport_type=MCPTransportType.STDIO,
                command="npx",
                args=["-y", "@anthropic/mcp-server-slack"],
            )],
            source="extension",
        ))
        agent = _agent(
            system_capabilities=SystemCapabilities(),
            integrations=["slack"],
        )
        name, servers = registry.resolve_for_agent(agent, "/tmp/ws")
        assert name == "slack"
        names = {s.name for s in servers}
        assert "filesystem" in names
        assert "slack" in names

    def test_no_caps_no_integration_returns_none(self):
        registry = IntegrationRegistry()
        agent = _agent()
        name, servers = registry.resolve_for_agent(agent, "/tmp/ws")
        assert name == "_none"
        assert servers == []

    def test_llm_provider_not_resolved_as_external(self):
        """LLM providers should not be used as tool integrations."""
        registry = IntegrationRegistry()
        agent = _agent(integrations=["anthropic"])
        name, servers = registry.resolve_for_agent(agent, "/tmp/ws")
        assert servers == []

    def test_unavailable_external_integration_skipped(self):
        """Missing credentials cause external integration to be skipped."""
        registry = IntegrationRegistry()
        registry.register(IntegrationDefinition(
            name="brave-search",
            description="Brave Search",
            domain_tags=["research"],
            cost_tier=2,
            mcp_server_factory=lambda _ws: [MCPServerConfig(
                name="brave",
                transport_type=MCPTransportType.STDIO,
                command="npx",
                args=["-y", "@anthropic/mcp-server-brave-search"],
            )],
            required_env=["BRAVE_API_KEY"],
            source="extension",
        ))
        # Remove only BRAVE_API_KEY; keep PATH so npx is found
        env_without_brave = {k: v for k, v in os.environ.items() if k != "BRAVE_API_KEY"}
        with patch.dict(os.environ, env_without_brave, clear=True):
            agent = _agent(
                system_capabilities=SystemCapabilities(fetch=FetchCapability()),
                integrations=["brave-search"],
            )
            name, servers = registry.resolve_for_agent(agent, "/tmp/ws")
            # System caps still work; external integration skipped
            assert any(s.name == "fetch" for s in servers)
            assert not any(s.name == "brave" for s in servers)


# ---------------------------------------------------------------------------
# User integrations tests
# ---------------------------------------------------------------------------


class TestUserIntegrations:
    def test_load_user_integrations_stdio(self, tmp_path: Path):
        config = {
            "integrations": [
                {
                    "name": "custom-search",
                    "description": "Custom search with Tavily",
                    "domain_tags": ["research"],
                    "cost_tier": 2,
                    "servers": [
                        {
                            "name": "tavily",
                            "transport_type": "stdio",
                            "command": "npx",
                            "args": ["-y", "tavily-mcp-server"],
                            "env": {"TAVILY_API_KEY": "${TAVILY_API_KEY}"},
                        }
                    ],
                }
            ]
        }

        config_path = tmp_path / ".rooben" / "integrations.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        registry = IntegrationRegistry()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            load_user_integrations(registry)
        finally:
            os.chdir(old_cwd)

        tk = registry.get("custom-search")
        assert tk is not None
        assert tk.description == "Custom search with Tavily"
        assert tk.cost_tier == 2
        assert "TAVILY_API_KEY" in tk.required_env

    def test_load_user_integrations_sse(self, tmp_path: Path):
        config = {
            "integrations": [
                {
                    "name": "remote-tools",
                    "description": "Remote tool server",
                    "domain_tags": ["operations"],
                    "cost_tier": 3,
                    "servers": [
                        {
                            "name": "enterprise-tools",
                            "transport_type": "sse",
                            "url": "https://tools.example.com/mcp",
                        }
                    ],
                }
            ]
        }

        config_path = tmp_path / ".rooben" / "integrations.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        registry = IntegrationRegistry()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            load_user_integrations(registry)
        finally:
            os.chdir(old_cwd)

        tk = registry.get("remote-tools")
        assert tk is not None
        servers = tk.mcp_server_factory("/tmp/ws")
        assert len(servers) == 1
        assert servers[0].transport_type == MCPTransportType.SSE
        assert servers[0].url == "https://tools.example.com/mcp"

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key-123"})
    def test_env_var_substitution(self, tmp_path: Path):
        config = {
            "integrations": [
                {
                    "name": "env-test",
                    "description": "Test env substitution",
                    "domain_tags": [],
                    "cost_tier": 1,
                    "servers": [
                        {
                            "name": "test",
                            "transport_type": "stdio",
                            "command": "echo",
                            "args": ["{workspace_dir}"],
                            "env": {"KEY": "${TAVILY_API_KEY}"},
                        }
                    ],
                }
            ]
        }

        config_path = tmp_path / ".rooben" / "integrations.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        registry = IntegrationRegistry()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            load_user_integrations(registry)
        finally:
            os.chdir(old_cwd)

        tk = registry.get("env-test")
        assert tk is not None
        servers = tk.mcp_server_factory("/my/workspace")
        assert servers[0].args == ["/my/workspace"]
        assert servers[0].env["KEY"] == "test-key-123"

    def test_no_config_file_is_noop(self, tmp_path: Path):
        registry = IntegrationRegistry()
        initial_count = len(registry.list_all())
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            load_user_integrations(registry)
        finally:
            os.chdir(old_cwd)
        assert len(registry.list_all()) == initial_count


# ---------------------------------------------------------------------------
# AgentSpec integration field tests
# ---------------------------------------------------------------------------


class TestAgentSpecIntegrationField:
    def test_integrations_default_empty(self):
        agent = AgentSpec(
            id="test",
            name="Test",
            transport=AgentTransport.LLM,
            description="test",
        )
        assert agent.integrations == []

    def test_integrations_field_set(self):
        agent = AgentSpec(
            id="test",
            name="Test",
            transport=AgentTransport.LLM,
            description="test",
            integrations=["github-issues", "brave-search"],
        )
        assert agent.integrations == ["github-issues", "brave-search"]

    def test_integrations_max_cap(self):
        with pytest.raises(Exception):
            AgentSpec(
                id="test",
                name="Test",
                transport=AgentTransport.LLM,
                description="test",
                integrations=["a", "b", "c", "d"],
            )

    def test_system_capabilities_field_set(self):
        agent = AgentSpec(
            id="test",
            name="Test",
            transport=AgentTransport.LLM,
            description="test",
            system_capabilities=SystemCapabilities(
                shell=ShellCapability(),
            ),
        )
        assert agent.system_capabilities is not None
        assert agent.system_capabilities.shell.enabled is True

    def test_system_capabilities_from_dict(self):
        """SystemCapabilities can be constructed from YAML-like dict."""
        data = {
            "id": "test",
            "name": "Test",
            "transport": "llm",
            "description": "test",
            "system_capabilities": {
                "shell": {"enabled": True},
                "fetch": {"enabled": True},
            },
        }
        agent = AgentSpec.model_validate(data)
        assert agent.system_capabilities is not None
        assert agent.system_capabilities.shell.enabled is True
        assert agent.system_capabilities.fetch.enabled is True
        assert agent.system_capabilities.memory is None


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_integrations_list(self):
        from click.testing import CliRunner
        from rooben.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["integrations", "list"])
        assert result.exit_code == 0
        assert "Available Integrations" in result.output
        # LLM providers should be listed
        assert "anthropic" in result.output

    def test_integrations_info_not_found(self):
        from click.testing import CliRunner
        from rooben.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["integrations", "info", "nonexistent"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Brave-search registration tests
# ---------------------------------------------------------------------------


class TestBraveSearchRegistration:
    def test_brave_search_registered_by_default(self):
        registry = IntegrationRegistry()
        integ = registry.get("brave-search")
        assert integ is not None
        assert integ.name == "brave-search"
        assert "BRAVE_API_KEY" in integ.required_env

    def test_brave_search_in_list(self):
        registry = IntegrationRegistry()
        names = {i.name for i in registry.list_all()}
        assert "brave-search" in names


# ---------------------------------------------------------------------------
# Heuristics tests
# ---------------------------------------------------------------------------


class TestToolCapabilityTaxonomy:
    def test_classify_search_tool(self):
        from rooben.agents.heuristics import ToolCapability, classify_tool_capability

        assert classify_tool_capability("Search the web for results") == ToolCapability.SEARCH
        assert classify_tool_capability("Query Google for information") == ToolCapability.SEARCH
        assert classify_tool_capability("Lookup relevant data") == ToolCapability.SEARCH

    def test_classify_fetch_tool(self):
        from rooben.agents.heuristics import ToolCapability, classify_tool_capability

        assert classify_tool_capability("Fetch a web page by URL") == ToolCapability.FETCH
        assert classify_tool_capability("Retrieve content via HTTP") == ToolCapability.FETCH
        assert classify_tool_capability("Download a resource") == ToolCapability.FETCH

    def test_classify_filesystem_tool(self):
        from rooben.agents.heuristics import ToolCapability, classify_tool_capability

        assert classify_tool_capability("Read a file from disk") == ToolCapability.FILESYSTEM
        assert classify_tool_capability("Write content to a file") == ToolCapability.FILESYSTEM

    def test_classify_unknown_tool(self):
        from rooben.agents.heuristics import classify_tool_capability

        assert classify_tool_capability("Some custom tool") is None
        # Tool named "Tavily" but described with search keywords
        assert classify_tool_capability("Tavily - search the web") is not None

    def test_is_research_capable(self):
        from rooben.agents.heuristics import is_research_capable

        class FakeTool:
            def __init__(self, desc: str):
                self.description = desc

        # Has both search + fetch
        tools = [FakeTool("Search the web"), FakeTool("Fetch a web page")]
        assert is_research_capable(tools) is True

        # Only fetch
        tools = [FakeTool("Fetch a web page")]
        assert is_research_capable(tools) is False

        # Only search
        tools = [FakeTool("Search the web")]
        assert is_research_capable(tools) is False

    def test_is_fetch_blocked(self):
        from rooben.agents.heuristics import is_fetch_blocked

        assert is_fetch_blocked("Access denied by robots.txt") is True
        assert is_fetch_blocked("403 Forbidden") is True
        assert is_fetch_blocked("This content requires a subscription required to view") is True
        assert is_fetch_blocked("Here is the content of the page...") is False


class TestOutputFeasibilityEstimation:
    def test_page_count(self):
        from rooben.agents.heuristics import CHARS_PER_PAGE, estimate_requested_output_chars

        assert estimate_requested_output_chars("Write a 50-page report") == 50 * CHARS_PER_PAGE
        assert estimate_requested_output_chars("Produce a 10 page summary") == 10 * CHARS_PER_PAGE

    def test_word_count(self):
        from rooben.agents.heuristics import estimate_requested_output_chars

        assert estimate_requested_output_chars("Write 10,000 words") == 10000 * 5
        assert estimate_requested_output_chars("Generate 5000 word article") == 5000 * 5

    def test_file_count(self):
        from rooben.agents.heuristics import estimate_requested_output_chars

        assert estimate_requested_output_chars("Create 20 files for the project") == 20 * 2000
        assert estimate_requested_output_chars("Generate 15 components") == 15 * 2000

    def test_no_indicators(self):
        from rooben.agents.heuristics import estimate_requested_output_chars

        assert estimate_requested_output_chars("Write a brief summary of findings") == 0
        assert estimate_requested_output_chars("Implement the login feature") == 0

    def test_largest_wins(self):
        from rooben.agents.heuristics import CHARS_PER_PAGE, estimate_requested_output_chars

        # "50-page" = 125K chars; "10,000 words" = 50K chars → 125K wins
        result = estimate_requested_output_chars("Write a 50-page report with 10,000 words")
        assert result == 50 * CHARS_PER_PAGE
