"""Shared orchestrator builder for CLI and API."""

from __future__ import annotations

from typing import Any, Callable


def build_integration_registry() -> Any:
    """Build complete registry: builtins + user YAML + all extension manifests.

    All Tier 1 and installed extension manifests are registered so the planner
    can select whichever integrations a workflow needs. Missing env vars cause
    ``is_available()`` to return False rather than blocking registration.
    """
    from rooben.agents.integrations import IntegrationRegistry, load_user_integrations
    from rooben.extensions.loader import load_all_extensions, register_extensions

    registry = IntegrationRegistry()
    load_user_integrations(registry)
    register_extensions(load_all_extensions(), integration_registry=registry)
    return registry


def get_llm_provider(
    provider_name: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
) -> Any:
    """Return a ready-to-use LLM provider with default settings.

    Convenience wrapper around ``_build_provider`` for callers that don't
    need per-role model overrides (e.g. the extension builder).
    """
    return _build_provider(provider_name, model)


def _build_provider(provider_name: str, model: str, api_key: str | None = None) -> Any:
    """Build an LLM provider by name.

    If *api_key* is supplied it is forwarded to the provider directly.
    Otherwise, the key is resolved from the integration registry via
    ``resolve_credential()`` (DB-first, env-fallback).
    """
    if not api_key:
        from rooben.agents.integrations import resolve_credential
        registry = build_integration_registry()
        provider_def = registry.get(provider_name)
        if provider_def and provider_def.required_env:
            api_key = resolve_credential(provider_def.required_env[0]) or None

    if provider_name == "openai":
        from rooben.planning.openai_provider import OpenAIProvider
        return OpenAIProvider(model=model, **({"api_key": api_key} if api_key else {}))
    elif provider_name == "ollama":
        from rooben.planning.ollama_provider import OllamaProvider
        return OllamaProvider(model=model)
    elif provider_name == "bedrock":
        from rooben.planning.bedrock_provider import BedrockProvider
        return BedrockProvider(model_id=model)
    else:
        from rooben.planning.provider import AnthropicProvider
        return AnthropicProvider(model=model, **({"api_key": api_key} if api_key else {}))


def build_orchestrator(
    spec: Any,
    provider_name: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
    model_planner: str | None = None,
    model_agent: str | None = None,
    model_verifier: str | None = None,
    verbose: bool = False,
    event_callback: Callable | None = None,
    backend: str = "filesystem",
    state_dir: str = ".rooben/state",
    pg_pool: Any | None = None,
) -> Any:
    """Build an Orchestrator from a Specification.

    Used by both CLI and API to avoid duplicating construction logic.
    """
    from rooben.agents.mcp_pool import MCPConnectionPool
    from rooben.agents.registry import AgentRegistry
    from rooben.orchestrator import Orchestrator
    from rooben.planning.llm_planner import LLMPlanner
    from rooben.verification.heuristic import HeuristicVerifier
    from rooben.verification.llm_judge import LLMJudgeVerifier
    from rooben.verification.tiered import TieredVerifier

    # Per-role providers — keys resolved via resolve_credential()
    planner_provider = _build_provider(provider_name, model_planner or model)
    agent_provider = _build_provider(provider_name, model_agent or model)
    verifier_provider = _build_provider(provider_name, model_verifier or model)

    if verbose:
        from rooben.planning.provider import VerboseProvider
        planner_provider = VerboseProvider(planner_provider)
        agent_provider = VerboseProvider(agent_provider)
        verifier_provider = VerboseProvider(verifier_provider)

    mcp_pool = MCPConnectionPool()

    # Resolve system capabilities + external integrations for agents
    from rooben.spec.models import AgentTransport

    integration_registry = build_integration_registry()

    for agent in spec.agents:
        if not agent.mcp_servers:
            _name, servers = integration_registry.resolve_for_agent(agent, state_dir)
            if servers:
                agent.transport = AgentTransport.MCP
                agent.mcp_servers = servers

    # Build per-agent providers for agents with model overrides
    provider_map: dict[str, Any] = {}
    for agent in spec.agents:
        if agent.model:
            provider_map[agent.id] = _build_provider(provider_name, agent.model)

    planner = LLMPlanner(provider=planner_provider)
    registry = AgentRegistry(
        llm_provider=agent_provider,
        provider_map=provider_map,
        connection_pool=mcp_pool,
    )
    registry.register_from_specs(spec.agents)

    # State backend — use Postgres when pool is available (dashboard mode),
    # otherwise fall back to filesystem (CLI mode).
    if pg_pool is not None:
        from rooben.state.postgres import PostgresStateBackend
        state_backend = PostgresStateBackend(pool=pg_pool)
    else:
        from rooben.state.filesystem import FilesystemBackend
        state_backend = FilesystemBackend(base_dir=state_dir)

    llm_judge = LLMJudgeVerifier(provider=verifier_provider)
    heuristic = HeuristicVerifier()
    verifier = TieredVerifier(heuristic=heuristic, llm_judge=llm_judge)

    # Learning store (OSS stub — no-op)
    from rooben.memory.learning_store import LearningStore
    learning_store = LearningStore()

    orchestrator = Orchestrator(
        planner=planner,
        agent_registry=registry,
        backend=state_backend,
        verifier=verifier,
        budget=spec.global_budget,
        learning_store=learning_store,
        event_callback=event_callback,
    )

    return orchestrator, mcp_pool
