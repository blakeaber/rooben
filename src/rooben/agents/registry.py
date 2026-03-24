"""Agent registry — builds agent instances from spec and manages their lifecycle."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from rooben.agents.http_agent import HTTPAgent
from rooben.agents.mcp_agent import MCPAgent
from rooben.agents.protocol import AgentProtocol
from rooben.agents.subprocess_agent import SubprocessAgent
from rooben.planning.provider import LLMProvider
from rooben.spec.models import AgentSpec, AgentTransport

if TYPE_CHECKING:
    from rooben.agents.mcp_pool import MCPConnectionPool

log = structlog.get_logger()


class AgentRegistry:
    """
    Builds and manages agent instances from spec definitions.

    Enforces per-agent concurrency limits via semaphores.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        provider_map: dict[str, LLMProvider] | None = None,
        connection_pool: MCPConnectionPool | None = None,
    ):
        self._agents: dict[str, AgentProtocol] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._llm_provider = llm_provider
        self._provider_map = provider_map or {}
        self._connection_pool = connection_pool

    def register_from_specs(self, agent_specs: list[AgentSpec]) -> None:
        """Build agent instances from a list of AgentSpec definitions."""
        for spec in agent_specs:
            agent = self._build_agent(spec)
            self._agents[spec.id] = agent
            self._semaphores[spec.id] = asyncio.Semaphore(spec.max_concurrency)
            log.info(
                "agent_registry.registered",
                agent_id=spec.id,
                transport=spec.transport.value,
                max_concurrency=spec.max_concurrency,
            )

    def get(self, agent_id: str) -> AgentProtocol | None:
        return self._agents.get(agent_id)

    def get_semaphore(self, agent_id: str) -> asyncio.Semaphore:
        return self._semaphores[agent_id]

    def all_ids(self) -> list[str]:
        return list(self._agents.keys())

    def _resolve_provider(self, spec: AgentSpec) -> LLMProvider | None:
        """Per-agent model override: use provider_map if agent has a dedicated provider."""
        return self._provider_map.get(spec.id, self._llm_provider)

    def _build_agent(self, spec: AgentSpec) -> AgentProtocol:
        builders = {
            AgentTransport.LLM: self._build_llm_agent,
            AgentTransport.SUBPROCESS: self._build_subprocess_agent,
            AgentTransport.HTTP: self._build_http_agent,
            AgentTransport.MCP: self._build_mcp_agent,
        }
        builder = builders.get(spec.transport)
        if builder is None:
            raise ValueError(f"Unknown transport: {spec.transport}")
        return builder(spec)

    def _build_llm_agent(self, spec: AgentSpec) -> AgentProtocol:
        provider = self._resolve_provider(spec)
        if not provider:
            raise ValueError("LLM agents require an LLM provider")
        return MCPAgent(
            agent_id=spec.id,
            mcp_configs=[],
            llm_provider=provider,
            max_turns=spec.max_turns,
            max_tokens=spec.budget.max_tokens if spec.budget and spec.budget.max_tokens else 16384,
            connection_pool=self._connection_pool,
        )

    def _build_subprocess_agent(self, spec: AgentSpec) -> AgentProtocol:
        return SubprocessAgent(
            agent_id=spec.id,
            callable_path=spec.endpoint,
            timeout=spec.budget.max_wall_seconds if spec.budget and spec.budget.max_wall_seconds else 300,
        )

    def _build_http_agent(self, spec: AgentSpec) -> AgentProtocol:
        return HTTPAgent(
            agent_id=spec.id,
            base_url=spec.endpoint,
            timeout=spec.budget.max_wall_seconds if spec.budget and spec.budget.max_wall_seconds else 300,
        )

    def _build_mcp_agent(self, spec: AgentSpec) -> AgentProtocol:
        provider = self._resolve_provider(spec)
        if not provider:
            raise ValueError("MCP agents require an LLM provider for tool orchestration")
        return MCPAgent(
            agent_id=spec.id,
            mcp_configs=spec.mcp_servers or [],
            llm_provider=provider,
            max_turns=spec.max_turns,
            max_tokens=spec.budget.max_tokens if spec.budget and spec.budget.max_tokens else 16384,
            connection_pool=self._connection_pool,
        )

    def register_mcp_agent(
        self, agent_id: str, max_concurrency: int = 1, mcp_configs: list | None = None
    ) -> None:
        """Register an MCPAgent (uses the registry's LLM provider).

        With no mcp_configs (or empty list), behaves like the old LLMAgent.
        """
        if not self._llm_provider:
            raise ValueError("Cannot create agent without an LLM provider")
        agent = MCPAgent(
            agent_id=agent_id,
            mcp_configs=mcp_configs or [],
            llm_provider=self._llm_provider,
        )
        self._agents[agent_id] = agent
        self._semaphores[agent_id] = asyncio.Semaphore(max_concurrency)
