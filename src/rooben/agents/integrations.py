"""Pre-configured MCP server integrations for common agent tasks.

The integration registry assigns domain-appropriate tools to agents based on their
capabilities. Each integration declares a cost tier (0-3) so the system can balance
capability vs. expense — more tools = more token overhead from tool descriptions
+ more API calls.

Cost tiers:
  0 — No tools, pure LLM reasoning. Cheapest.
  1 — Local tools only (filesystem). Low overhead.
  2 — Local tools + shell or web access. Moderate overhead.
  3 — Multiple external services. Highest overhead.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import structlog
import yaml

from rooben.config import get_settings as _get_settings
from rooben.spec.models import AgentSpec, MCPServerConfig, MCPTransportType, SystemCapabilities

log = structlog.get_logger()

# Credential cache — populated from DB at startup, refreshed on credential changes
_credential_cache: dict[str, str] = {}


def resolve_credential(env_var_name: str) -> str:
    """Resolve a credential: env var first, DB-stored cache fallback.

    Single entry point for ALL credential reads — providers, integrations, etc.
    Env vars take precedence so users can override at runtime.
    Always returns a string (empty string if not found).
    """
    return os.environ.get(env_var_name) or _credential_cache.get(env_var_name, "")


async def populate_credential_cache(pool: object) -> None:
    """Load decrypted credentials from DB into the module-level cache."""
    global _credential_cache
    try:
        from rooben.dashboard.queries.credentials import get_decrypted_credentials
        _credential_cache = await get_decrypted_credentials(pool)  # type: ignore[arg-type]
        log.info("integrations.credential_cache_loaded", count=len(_credential_cache))
    except Exception as exc:
        log.warning("integrations.credential_cache_error", error=str(exc))


# ---------------------------------------------------------------------------
# Gateway URL — configurable for local dev (npx fallback) vs Docker
# ---------------------------------------------------------------------------

_MCP_GATEWAY_URL = _get_settings().mcp_gateway_url


def _use_gateway() -> bool:
    """Return True if MCP servers should be routed through the gateway container."""
    return bool(_MCP_GATEWAY_URL)


def _gateway_config(
    server_name: str,
    npx_package: str,
    required_env: list[str],
    extra_args: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> list[MCPServerConfig]:
    """Build an SSE config that delegates to the MCP gateway container.

    Credentials are resolved from env vars and the credential cache, then
    passed as base64 JSON in HTTP headers — never baked into container env.
    """
    env_vars: dict[str, str] = {}
    for var in required_env:
        val = resolve_credential(var)
        if not val:
            return []  # credential not available
        env_vars[var] = val

    if extra_env:
        env_vars.update(extra_env)

    headers: dict[str, str] = {
        "X-MCP-Package": npx_package,
    }
    if env_vars:
        headers["X-MCP-Env"] = base64.b64encode(
            json.dumps(env_vars).encode()
        ).decode()
    if extra_args:
        headers["X-MCP-Args"] = json.dumps(extra_args)

    return [
        MCPServerConfig(
            name=server_name,
            transport_type=MCPTransportType.SSE,
            url=f"{_MCP_GATEWAY_URL}/sse",
            headers=headers,
        )
    ]


# Legacy npm helpers — kept as no-ops for backward compatibility
def ensure_mcp_packages_installed() -> None:
    """No-op when using gateway; packages are pre-installed in the gateway image."""
    if _use_gateway():
        return
    # Local dev fallback: no pre-install needed, npx handles it
    log.debug("integrations.ensure_packages_skipped", reason="gateway or local npx")


def check_mcp_packages_available() -> bool:
    """Return True if MCP servers can be started (gateway available or npx present)."""
    if _use_gateway():
        return True
    return bool(shutil.which("npx"))


# ---------------------------------------------------------------------------
# MCP Server Factories
# ---------------------------------------------------------------------------

def coding_mcp_servers(workspace_dir: str) -> list[MCPServerConfig]:
    """MCP server configs for coding tasks in an isolated workspace."""
    if _use_gateway():
        fs = _gateway_config(
            "filesystem",
            "@modelcontextprotocol/server-filesystem",
            [],
            extra_args=[workspace_dir],
        )
        shell = _gateway_config(
            "shell",
            "mcp-shell-server",
            [],
            extra_env={"ALLOWED_DIR": workspace_dir},
        )
        return fs + shell

    if not shutil.which("npx"):
        log.warning("integrations.npx_not_found", msg="npx not found, running without filesystem/shell tools")
        return []

    return [
        MCPServerConfig(
            name="filesystem",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", workspace_dir],
        ),
        MCPServerConfig(
            name="shell",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "mcp-shell-server"],
            env={"ALLOWED_DIR": workspace_dir},
        ),
    ]


def filesystem_mcp_server(workspace_dir: str) -> list[MCPServerConfig]:
    """Filesystem-only MCP server (no shell). For writing/content agents."""
    if _use_gateway():
        return _gateway_config(
            "filesystem",
            "@modelcontextprotocol/server-filesystem",
            [],
            extra_args=[workspace_dir],
        )

    if not shutil.which("npx"):
        log.warning("integrations.npx_not_found", msg="npx not found, running without filesystem tools")
        return []

    return [
        MCPServerConfig(
            name="filesystem",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", workspace_dir],
        ),
    ]


def web_search_servers() -> list[MCPServerConfig]:
    """Brave Search MCP server for web research. Requires BRAVE_API_KEY."""
    if _use_gateway():
        return _gateway_config(
            "brave-search",
            "@modelcontextprotocol/server-brave-search",
            ["BRAVE_API_KEY"],
        )

    if not shutil.which("npx"):
        return []
    brave_key = resolve_credential("BRAVE_API_KEY")
    if not brave_key:
        return []

    return [
        MCPServerConfig(
            name="brave-search",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": brave_key},
        ),
    ]


def web_fetch_server() -> list[MCPServerConfig]:
    """Fetch MCP server for reading web pages. No API key needed."""
    if _use_gateway():
        return _gateway_config("fetch", "@anthropic/mcp-server-fetch", [])

    if not shutil.which("npx"):
        return []

    return [
        MCPServerConfig(
            name="fetch",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@anthropic/mcp-server-fetch"],
        ),
    ]


def google_drive_server() -> list[MCPServerConfig]:
    """Google Drive MCP server. Requires GOOGLE_CREDENTIALS_PATH."""
    if _use_gateway():
        return _gateway_config(
            "google-drive",
            "@anthropic/mcp-server-gdrive",
            ["GOOGLE_CREDENTIALS_PATH"],
        )

    if not shutil.which("npx"):
        return []
    creds = resolve_credential("GOOGLE_CREDENTIALS_PATH")
    if not creds:
        return []

    return [
        MCPServerConfig(
            name="google-drive",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@anthropic/mcp-server-gdrive"],
            env={"GOOGLE_CREDENTIALS_PATH": creds},
        ),
    ]


def memory_server(workspace_dir: str) -> list[MCPServerConfig]:
    """Memory/knowledge-graph MCP server for persistent agent context."""
    if _use_gateway():
        return _gateway_config(
            "memory",
            "@anthropic/mcp-server-memory",
            [],
            extra_env={"MEMORY_DIR": workspace_dir},
        )

    if not shutil.which("npx"):
        return []

    return [
        MCPServerConfig(
            name="memory",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@anthropic/mcp-server-memory"],
            env={"MEMORY_DIR": workspace_dir},
        ),
    ]


# ---------------------------------------------------------------------------
# IntegrationDefinition + Registry
# ---------------------------------------------------------------------------

@dataclass
class IntegrationDefinition:
    """A named collection of MCP servers assigned to agents by domain."""

    name: str
    description: str
    domain_tags: list[str]
    cost_tier: int  # 0=free (pure LLM), 1=low, 2=medium, 3=high
    mcp_server_factory: Callable[[str], list[MCPServerConfig]]
    required_env: list[str] = field(default_factory=list)
    source: str = "builtin"  # "builtin" | "user" | "community"
    author: str = ""
    version: str = "1.0.0"
    kind: str = "mcp"  # "mcp" | "llm_provider"

    def to_dict(self) -> dict:
        """Serialize all fields except mcp_server_factory."""
        return {
            "name": self.name,
            "description": self.description,
            "domain_tags": self.domain_tags,
            "cost_tier": self.cost_tier,
            "required_env": self.required_env,
            "source": self.source,
            "author": self.author,
            "version": self.version,
            "kind": self.kind,
        }


# ---------------------------------------------------------------------------
# LLM Provider definitions (always registered)
# ---------------------------------------------------------------------------

def _build_llm_providers() -> list[IntegrationDefinition]:
    """LLM provider integrations — no MCP servers, just credential tracking."""
    def _no_servers(_ws: str) -> list[MCPServerConfig]:
        return []
    return [
        IntegrationDefinition(
            name="anthropic",
            description="Anthropic Claude — models for planning, agents, and verification",
            domain_tags=[],
            cost_tier=0,
            kind="llm_provider",
            mcp_server_factory=_no_servers,
            required_env=["ANTHROPIC_API_KEY"],
        ),
        IntegrationDefinition(
            name="openai",
            description="OpenAI GPT models for planning and generation",
            domain_tags=[],
            cost_tier=0,
            kind="llm_provider",
            mcp_server_factory=_no_servers,
            required_env=["OPENAI_API_KEY"],
        ),
        IntegrationDefinition(
            name="ollama",
            description="Ollama — local open-source models (no API key required)",
            domain_tags=[],
            cost_tier=0,
            kind="llm_provider",
            mcp_server_factory=_no_servers,
            required_env=[],
        ),
        IntegrationDefinition(
            name="bedrock",
            description="AWS Bedrock — managed Claude and other models via AWS",
            domain_tags=[],
            cost_tier=0,
            kind="llm_provider",
            mcp_server_factory=_no_servers,
            required_env=[],
        ),
    ]


# ---------------------------------------------------------------------------
# System Capabilities Resolver
# ---------------------------------------------------------------------------

def resolve_system_capabilities(
    system_capabilities: "SystemCapabilities | None",
    workspace_dir: str,
) -> list[MCPServerConfig]:
    """Resolve SystemCapabilities to MCP server configs.

    Phase 1 of two-phase resolution. Maps declarative capability flags
    directly to MCP servers — no scoring, no domain matching.
    """

    if system_capabilities is None:
        return []

    servers: list[MCPServerConfig] = []

    # Filesystem is infrastructure — always granted. Agents need it to write
    # artifacts to disk (the cross-task source of truth).
    servers.extend(filesystem_mcp_server(workspace_dir))

    if system_capabilities.shell and system_capabilities.shell.enabled:
        # coding_mcp_servers returns both filesystem + shell; only add what's new
        shell_servers = coding_mcp_servers(workspace_dir)
        existing_names = {s.name for s in servers}
        for s in shell_servers:
            if s.name not in existing_names:
                servers.append(s)

    if system_capabilities.memory and system_capabilities.memory.enabled:
        servers.extend(memory_server(workspace_dir))

    if system_capabilities.fetch and system_capabilities.fetch.enabled:
        servers.extend(web_fetch_server())

    return servers


class IntegrationRegistry:
    """Registry of external integrations and LLM providers.

    After the builtin deletion, this registry contains only:
    - LLM providers (anthropic, openai, ollama, bedrock)
    - User-defined integrations (.rooben/integrations.yaml)
    - Extension-based integrations (community/installed)

    System capabilities (filesystem, shell, memory, fetch) are handled
    separately by resolve_system_capabilities().
    """

    def __init__(self) -> None:
        self._integrations: dict[str, IntegrationDefinition] = {}
        self._register_providers()
        self._register_external_integrations()

    def _register_providers(self) -> None:
        for integ in _build_llm_providers():
            self._integrations[integ.name] = integ

    def _register_external_integrations(self) -> None:
        """Register built-in external integrations (require credentials)."""
        self._integrations["brave-search"] = IntegrationDefinition(
            name="brave-search",
            description="Brave Search — web search for research and URL discovery",
            domain_tags=["research", "search"],
            cost_tier=1,
            mcp_server_factory=lambda _ws: web_search_servers(),
            required_env=["BRAVE_API_KEY"],
            source="builtin",
        )

    def register(self, integration: IntegrationDefinition) -> None:
        """Register an integration (overwrites if name exists)."""
        self._integrations[integration.name] = integration

    def get(self, name: str) -> IntegrationDefinition | None:
        return self._integrations.get(name)

    def list_all(self) -> list[IntegrationDefinition]:
        return list(self._integrations.values())

    def is_available(self, integration: IntegrationDefinition) -> bool:
        """Check if required env vars are present (env or credential cache)."""
        for env_var in integration.required_env:
            if not resolve_credential(env_var):
                return False
        return True

    def _missing_env(self, integration: IntegrationDefinition) -> list[str]:
        """Return list of missing required env vars."""
        return [
            v for v in integration.required_env
            if not resolve_credential(v)
        ]

    def resolve_for_agent(
        self, agent: AgentSpec, workspace_dir: str
    ) -> tuple[str, list[MCPServerConfig]]:
        """Two-phase resolver: system capabilities + external integration.

        Phase 1: Resolve system_capabilities → MCP servers (filesystem, shell, etc.)
        Phase 2: Resolve external integration → additional MCP servers

        Returns (integration_name, combined_servers).
        """
        # Respect user-specified servers
        if agent.mcp_servers:
            return ("custom", agent.mcp_servers)

        servers: list[MCPServerConfig] = []

        # Phase 1: System capabilities
        sys_caps = getattr(agent, "system_capabilities", None)
        if sys_caps:
            servers.extend(resolve_system_capabilities(sys_caps, workspace_dir))

        # Phase 2: External integrations (iterate over list)
        integration_names: list[str] = []
        for integ_name in getattr(agent, "integrations", []):
            integ = self.get(integ_name)
            if not integ:
                log.warning("integrations.not_found", agent=agent.id, integration=integ_name)
                continue
            if integ.kind == "llm_provider":
                continue
            if not self.is_available(integ):
                missing = self._missing_env(integ)
                log.warning(
                    "integrations.unavailable",
                    agent=agent.id,
                    integration=integ_name,
                    missing_env=missing,
                )
                continue
            ext_servers = integ.mcp_server_factory(workspace_dir)
            if ext_servers:
                existing_names = {s.name for s in servers}
                for s in ext_servers:
                    if s.name not in existing_names:
                        servers.append(s)
                integration_names.append(integ.name)

        if servers:
            resolved_name = "+".join(integration_names) if integration_names else "system"
            log.info("integrations.resolved", agent=agent.id, integration=resolved_name, server_count=len(servers))
            return (resolved_name, servers)

        log.info("integrations.resolved", agent=agent.id, integration="_none", server_count=0)
        return ("_none", [])


# ---------------------------------------------------------------------------
# User-extensible integrations
# ---------------------------------------------------------------------------

def _substitute_env_vars(value: str) -> str:
    """Replace ${ENV_VAR} patterns with environment variable values.

    Falls back to _credential_cache when env var is empty.
    """
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return resolve_credential(var_name)
    return re.sub(r"\$\{(\w+)\}", _replace, value)


def load_user_integrations(registry: IntegrationRegistry) -> None:
    """Load user-defined integrations from .rooben/integrations.yaml."""
    config_path = Path(".rooben/integrations.yaml")
    if not config_path.exists():
        return

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        log.warning("integrations.user_config_error", error=str(exc))
        return

    if not data:
        return

    entries = data.get("integrations")
    if not entries:
        return

    for tk_data in entries:
        try:
            servers_data = tk_data.get("servers", [])

            # Collect required env vars from ${VAR} references
            required_env: list[str] = []
            raw_yaml = yaml.dump(tk_data)
            for match in re.finditer(r"\$\{(\w+)\}", raw_yaml):
                var = match.group(1)
                if var != "workspace_dir" and var not in required_env:
                    required_env.append(var)

            def _make_factory(servers_config: list[dict], ext_required_env: list[str]) -> Callable[[str], list[MCPServerConfig]]:
                def factory(workspace_dir: str) -> list[MCPServerConfig]:
                    configs = []
                    for s in servers_config:
                        transport = MCPTransportType(s.get("transport_type", "stdio"))

                        # Gateway mode: rewrite stdio/npx to SSE gateway config
                        if _use_gateway() and transport == MCPTransportType.STDIO and s.get("command") == "npx":
                            npx_args = s.get("args", [])
                            # Extract the package name (first arg that isn't a flag)
                            npx_package = ""
                            extra_args: list[str] = []
                            skip_next = False
                            for i, a in enumerate(npx_args):
                                if skip_next:
                                    skip_next = False
                                    continue
                                if a in ("-y", "--yes"):
                                    continue
                                if not npx_package:
                                    npx_package = a
                                else:
                                    resolved = _substitute_env_vars(str(a))
                                    resolved = resolved.replace("{workspace_dir}", workspace_dir)
                                    extra_args.append(resolved)

                            # Collect extra env from the server's env block
                            extra_env: dict[str, str] = {}
                            for k, v in s.get("env", {}).items():
                                resolved_v = _substitute_env_vars(str(v))
                                if resolved_v:
                                    extra_env[k] = resolved_v

                            gw = _gateway_config(
                                s.get("name", "custom"),
                                npx_package,
                                ext_required_env,
                                extra_args=extra_args or None,
                                extra_env=extra_env or None,
                            )
                            configs.extend(gw)
                            continue

                        # Substitute env vars and workspace_dir in args
                        args = []
                        for arg in s.get("args", []):
                            arg = _substitute_env_vars(str(arg))
                            arg = arg.replace("{workspace_dir}", workspace_dir)
                            args.append(arg)

                        # Substitute env vars in env dict
                        env = {}
                        for k, v in s.get("env", {}).items():
                            env[k] = _substitute_env_vars(str(v))

                        # Substitute env vars in url
                        url = s.get("url")
                        if url:
                            url = _substitute_env_vars(url)

                        configs.append(MCPServerConfig(
                            name=s.get("name", "custom"),
                            transport_type=transport,
                            command=s.get("command"),
                            args=args,
                            env=env,
                            url=url,
                        ))
                    return configs
                return factory

            integration = IntegrationDefinition(
                name=tk_data["name"],
                description=tk_data.get("description", ""),
                domain_tags=tk_data.get("domain_tags", []),
                cost_tier=tk_data.get("cost_tier", 2),
                mcp_server_factory=_make_factory(servers_data, required_env),
                required_env=required_env,
                source=tk_data.get("source", "user"),
                author=tk_data.get("author", ""),
                version=tk_data.get("version", "1.0.0"),
            )
            registry.register(integration)
            log.info("integrations.user_registered", name=integration.name)
        except Exception as exc:
            log.warning("integrations.user_integration_error", name=tk_data.get("name", "?"), error=str(exc))
