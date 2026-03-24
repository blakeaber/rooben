"""Integrations Hub API routes — manage MCP integrations."""

from __future__ import annotations

import os
from pathlib import Path

import structlog
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rooben.agents.integrations import IntegrationDefinition, IntegrationRegistry

log = structlog.get_logger()

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_registry() -> IntegrationRegistry:
    """Build a fresh registry with builtins + user integrations + all extensions."""
    from rooben.dashboard.orchestrator_factory import build_integration_registry
    return build_integration_registry()


def _integrations_yaml_path() -> Path:
    """Return path to integrations YAML."""
    return Path(".rooben/integrations.yaml")


def _read_user_integrations_raw() -> list[dict]:
    """Read raw integration entries from .rooben/integrations.yaml."""
    path = _integrations_yaml_path()
    if not path.exists():
        return []
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("integrations") or []
    except Exception:
        return []


def _write_user_integrations_raw(integrations: list[dict]) -> None:
    """Write integration entries to .rooben/integrations.yaml."""
    path = Path(".rooben/integrations.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump({"integrations": integrations}, f, default_flow_style=False)


def _integration_to_response(tk: IntegrationDefinition, registry: IntegrationRegistry) -> dict:
    """Convert an IntegrationDefinition to an API response dict."""
    from rooben.agents.integrations import _credential_cache

    d = tk.to_dict()
    d["available"] = registry.is_available(tk)
    d["missing_env"] = [
        v for v in tk.required_env
        if not os.environ.get(v) and v not in _credential_cache
    ]
    # Count servers (invoke factory with dummy dir)
    try:
        servers = tk.mcp_server_factory("/tmp/_probe")
        d["server_count"] = len(servers)
    except Exception:
        d["server_count"] = 0
    return d


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class InstallRequest(BaseModel):
    name: str
    description: str = ""
    domain_tags: list[str] = []
    cost_tier: int = 2
    author: str = ""
    version: str = "1.0.0"
    servers: list[dict] = []


class BuildRequest(BaseModel):
    description: str
    domain_tags: list[str] = []


class PublishRequest(BaseModel):
    author: str = ""
    description: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_integrations():
    """List all external integrations with availability status.

    System capabilities (filesystem, shell, memory, fetch) are not listed here —
    they are declared via agent system_capabilities. LLM providers are also excluded.
    """
    registry = _get_registry()
    items = []
    for tk in registry.list_all():
        if tk.kind == "llm_provider":
            continue
        items.append(_integration_to_response(tk, registry))
    return {"integrations": items}


@router.get("/library")
async def browse_library():
    """Browse community integration library.

    In OSS mode (no Pro extension), community items are excluded.
    OSS users install integrations via CLI: rooben extensions install <name>
    """
    from rooben.extensions.loader import load_all_extensions
    ext_names = {m.name for m in load_all_extensions()}
    is_pro = "pro" in ext_names

    sample_library = [
        {
            "name": "slack-notifications",
            "description": "Send notifications and read channels via Slack API",
            "author": "rooben-community",
            "version": "1.0.0",
            "domain_tags": ["operations", "marketing"],
            "cost_tier": 2,
            "install_count": 142,
            "servers": [
                {
                    "name": "slack",
                    "transport_type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@anthropic/mcp-server-slack"],
                    "env": {"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
                }
            ],
        },
        {
            "name": "github-issues",
            "description": "Create, read, and manage GitHub issues and PRs",
            "author": "rooben-community",
            "version": "1.2.0",
            "domain_tags": ["software", "operations"],
            "cost_tier": 2,
            "install_count": 238,
            "servers": [
                {
                    "name": "github",
                    "transport_type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
                }
            ],
        },
        {
            "name": "postgres-query",
            "description": "Run read-only SQL queries against PostgreSQL databases",
            "author": "rooben-community",
            "version": "1.0.0",
            "domain_tags": ["data-science", "analytics"],
            "cost_tier": 2,
            "install_count": 95,
            "servers": [
                {
                    "name": "postgres",
                    "transport_type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"],
                    "env": {},
                }
            ],
        },
        {
            "name": "notion-sync",
            "description": "Read and write Notion pages and databases",
            "author": "rooben-community",
            "version": "0.9.0",
            "domain_tags": ["operations", "content"],
            "cost_tier": 2,
            "install_count": 67,
            "servers": [
                {
                    "name": "notion",
                    "transport_type": "stdio",
                    "command": "npx",
                    "args": ["-y", "mcp-notion-server"],
                    "env": {"NOTION_API_KEY": "${NOTION_API_KEY}"},
                }
            ],
        },
        {
            "name": "puppeteer-scraper",
            "description": "Browser automation and web scraping via Puppeteer",
            "author": "rooben-community",
            "version": "1.1.0",
            "domain_tags": ["research", "data-science"],
            "cost_tier": 3,
            "install_count": 54,
            "servers": [
                {
                    "name": "puppeteer",
                    "transport_type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@anthropic/mcp-server-puppeteer"],
                    "env": {},
                }
            ],
        },
    ]
    if not is_pro:
        # OSS: show library items with install_via_cli flag, no Install button
        for item in sample_library:
            item["install_via_cli"] = True
            item["cli_command"] = f"rooben extensions install {item['name']}"
    return {"library": sample_library, "pro_enabled": is_pro}


@router.get("/names")
async def list_integration_names():
    """List external integration names and descriptions for dropdown population."""
    registry = _get_registry()
    items = []
    for tk in registry.list_all():
        if tk.kind == "llm_provider":
            continue
        items.append({"name": tk.name, "description": tk.description})
    return {"integrations": items}


@router.get("/{name}")
async def get_integration(name: str):
    """Single integration detail with server count. LLM providers are excluded."""
    registry = _get_registry()
    tk = registry.get(name)
    if not tk or tk.kind == "llm_provider":
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")
    return _integration_to_response(tk, registry)


@router.post("/{name}/test")
async def test_integration(name: str):
    """Test an integration: config checks + gateway liveness probe.

    Returns tiered checks:
    - tier: "config" — env vars, server routing
    - tier: "liveness" — actual MCP server startup via gateway /probe
    """
    from rooben.agents.integrations import _credential_cache, _use_gateway, _MCP_GATEWAY_URL

    registry = _get_registry()
    tk = registry.get(name)
    if not tk or tk.kind == "llm_provider":
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")

    checks: list[dict] = []

    # Tier 1: Config checks — env vars
    for env_var in tk.required_env:
        from_env = bool(os.environ.get(env_var))
        from_cache = env_var in _credential_cache
        present = from_env or from_cache
        source = "env" if from_env else ("stored" if from_cache else "missing")
        checks.append({
            "check": f"env:{env_var}",
            "tier": "config",
            "passed": present,
            "message": f"{'Available' if present else 'Missing'}: {env_var} (source: {source})",
        })

    # Tier 1: Config checks — server availability
    try:
        servers = tk.mcp_server_factory("/tmp/_test")
        if not servers:
            checks.append({
                "check": "servers",
                "tier": "config",
                "passed": False,
                "message": "No servers configured (missing credentials or configuration)",
            })
        elif _use_gateway():
            for s in servers:
                checks.append({
                    "check": f"gateway:{s.name}",
                    "tier": "config",
                    "passed": s.transport_type.value == "sse" and bool(s.url),
                    "message": f"Gateway route configured for {s.name}",
                })
        else:
            import shutil as _shutil
            for s in servers:
                if s.command:
                    found = _shutil.which(s.command) is not None
                    checks.append({
                        "check": f"binary:{s.command}",
                        "tier": "config",
                        "passed": found,
                        "message": f"{'Found' if found else 'Not found'}: {s.command}",
                    })
    except Exception as exc:
        checks.append({
            "check": "server_factory",
            "tier": "config",
            "passed": False,
            "message": f"Error creating servers: {exc}",
        })

    # Tier 1.5: Warm up package cache (download npm packages before probing)
    config_passed = all(c["passed"] for c in checks)
    if config_passed and _use_gateway() and servers:
        import httpx

        for s in servers:
            pkg = (s.headers or {}).get("X-MCP-Package", "")
            if pkg and s.transport_type.value == "sse":
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        warmup_resp = await client.post(
                            _MCP_GATEWAY_URL + "/warmup",
                            json={"package": pkg},
                        )
                        warmup_data = warmup_resp.json()
                        checks.append({
                            "check": f"warmup:{s.name}",
                            "tier": "warmup",
                            "passed": warmup_data.get("status") == "ready",
                            "message": (
                                f"Package cached ({warmup_data.get('duration_ms', 0)}ms)"
                                if warmup_data.get("status") == "ready"
                                else f"Package cache failed: {warmup_data.get('error', 'unknown')}"
                            ),
                        })
                except Exception as exc:
                    checks.append({
                        "check": f"warmup:{s.name}",
                        "tier": "warmup",
                        "passed": False,
                        "message": f"Warmup error: {exc}",
                    })

    # Tier 2: Liveness probe via gateway /probe (only if gateway available and config passed)
    config_passed = all(c["passed"] for c in checks)
    if config_passed and _use_gateway() and servers:
        for s in servers:
            if s.transport_type.value == "sse" and s.url:
                probe_url = _MCP_GATEWAY_URL + "/probe"
                headers = dict(s.headers) if s.headers else {}
                try:
                    async with httpx.AsyncClient(timeout=35.0) as client:
                        resp = await client.get(probe_url, headers=headers)
                        probe_data = resp.json()
                        checks.append({
                            "check": f"liveness:{s.name}",
                            "tier": "liveness",
                            "passed": probe_data.get("alive", False),
                            "message": (
                                f"Server alive (startup: {probe_data.get('startup_ms', '?')}ms)"
                                if probe_data.get("alive")
                                else f"Probe failed: {probe_data.get('error', 'unknown')}"
                            ),
                        })
                except Exception as exc:
                    checks.append({
                        "check": f"liveness:{s.name}",
                        "tier": "liveness",
                        "passed": False,
                        "message": f"Gateway unreachable: {exc}",
                    })

    all_passed = all(c["passed"] for c in checks)
    return {
        "name": name,
        "passed": all_passed,
        "checks": checks,
    }


@router.post("/install")
async def install_from_library(req: InstallRequest):
    """Install an integration from the community library → .rooben/integrations.yaml.

    Requires Pro extension. OSS users should use the CLI:
      rooben extensions install <name>

    Validates server config before saving. If gateway is available, probes the
    MCP server to verify it starts successfully.
    """
    # Gate behind Pro extension
    from rooben.extensions.loader import load_all_extensions
    ext_names = {m.name for m in load_all_extensions()}
    if "pro" not in ext_names:
        raise HTTPException(
            status_code=403,
            detail="Community install requires Pro. Use CLI: rooben extensions install <name>",
        )
    registry = _get_registry()
    if registry.get(req.name):
        raise HTTPException(status_code=409, detail=f"Integration '{req.name}' already installed")

    # Schema validation: each server must have command+args OR url
    for s in req.servers:
        has_stdio = bool(s.get("command"))
        has_sse = bool(s.get("url"))
        if not has_stdio and not has_sse:
            raise HTTPException(
                status_code=422,
                detail=f"Server '{s.get('name', '?')}' must have 'command' (stdio) or 'url' (SSE)",
            )

    # Package warmup + probe: cache package then verify it starts
    from rooben.agents.integrations import _use_gateway, _MCP_GATEWAY_URL
    if _use_gateway():
        for s in req.servers:
            if s.get("command") == "npx" and s.get("args"):
                # Extract package name
                npx_args = s["args"]
                pkg = ""
                for a in npx_args:
                    if a in ("-y", "--yes"):
                        continue
                    pkg = a
                    break
                if pkg:
                    import httpx
                    # Warmup: cache the package before probing
                    try:
                        async with httpx.AsyncClient(timeout=120.0) as client:
                            await client.post(
                                _MCP_GATEWAY_URL + "/warmup",
                                json={"package": pkg},
                            )
                    except Exception:
                        log.debug("integrations.warmup_failed", package=pkg, exc_info=True)
                    try:
                        async with httpx.AsyncClient(timeout=35.0) as client:
                            resp = await client.get(
                                _MCP_GATEWAY_URL + "/probe",
                                headers={"X-MCP-Package": pkg},
                            )
                            probe = resp.json()
                            if not probe.get("alive"):
                                raise HTTPException(
                                    status_code=422,
                                    detail=f"Package probe failed for '{pkg}': {probe.get('error', 'unknown')}",
                                )
                    except httpx.HTTPError:
                        pass  # Gateway unreachable; skip probe

    entry = {
        "name": req.name,
        "description": req.description,
        "domain_tags": req.domain_tags,
        "cost_tier": req.cost_tier,
        "author": req.author,
        "version": req.version,
        "source": "community",
        "servers": req.servers,
    }

    existing = _read_user_integrations_raw()
    existing.append(entry)
    _write_user_integrations_raw(existing)

    return {"installed": True, **entry}


@router.post("/build")
async def build_integration(req: BuildRequest):
    """AI-assisted integration builder.

    For MVP: generates an integration YAML config based on the description.
    The LLM suggests npx packages, args, and env vars.
    """
    # Simple rule-based builder for MVP (no LLM call required)
    name = req.description.lower().replace(" ", "-")[:30].strip("-")
    if not name:
        name = "custom-integration"

    # Build a sensible config based on description keywords
    servers = []
    required_env: list[str] = []

    desc_lower = req.description.lower()

    if "slack" in desc_lower:
        servers.append({
            "name": "slack",
            "transport_type": "stdio",
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-slack"],
            "env": {"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
        })
        required_env.append("SLACK_BOT_TOKEN")
    elif "github" in desc_lower:
        servers.append({
            "name": "github",
            "transport_type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
        })
        required_env.append("GITHUB_TOKEN")
    elif "postgres" in desc_lower or "database" in desc_lower or "sql" in desc_lower:
        servers.append({
            "name": "postgres",
            "transport_type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"],
            "env": {},
        })
        required_env.append("DATABASE_URL")
    elif "notion" in desc_lower:
        servers.append({
            "name": "notion",
            "transport_type": "stdio",
            "command": "npx",
            "args": ["-y", "mcp-notion-server"],
            "env": {"NOTION_API_KEY": "${NOTION_API_KEY}"},
        })
        required_env.append("NOTION_API_KEY")
    elif "search" in desc_lower or "web" in desc_lower:
        servers.append({
            "name": "brave-search",
            "transport_type": "stdio",
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-brave-search"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        })
        required_env.append("BRAVE_API_KEY")
    else:
        # Generic filesystem-based integration
        servers.append({
            "name": "filesystem",
            "transport_type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workspace_dir}"],
            "env": {},
        })

    config = {
        "name": name,
        "description": req.description,
        "domain_tags": req.domain_tags or ["operations"],
        "cost_tier": 2,
        "author": "",
        "version": "1.0.0",
        "servers": servers,
    }

    plan = {
        "name": name,
        "description": req.description,
        "servers": [
            {
                "package": s.get("args", [None, ""])[1] if len(s.get("args", [])) > 1 else s.get("command", ""),
                "env_vars": list(s.get("env", {}).keys()) + [
                    arg.replace("${", "").replace("}", "")
                    for arg in s.get("args", [])
                    if "${" in str(arg)
                ],
            }
            for s in servers
        ],
        "required_env": required_env,
        "domain_tags": config["domain_tags"],
    }

    return {
        "plan": plan,
        "config": config,
        "message": "Review the plan above. To install, POST to /api/integrations with the config.",
    }


@router.post("/{name}/publish")
async def publish_integration(name: str, req: PublishRequest):
    """Publish a user integration to the community library (stub)."""
    registry = _get_registry()
    tk = registry.get(name)
    if not tk:
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")
    if tk.source == "builtin":
        raise HTTPException(status_code=403, detail="Cannot publish builtin integrations")

    # Stub: return the YAML that would be submitted + quality checks
    publish_yaml = yaml.dump(tk.to_dict(), default_flow_style=False)

    quality_checks = [
        {"check": "has_description", "passed": bool(tk.description), "message": "Integration has a description"},
        {"check": "has_servers", "passed": len(tk.mcp_server_factory("/tmp/_check")) > 0 if True else False, "message": "Integration has MCP servers"},
        {"check": "has_domain_tags", "passed": bool(tk.domain_tags), "message": "Integration has domain tags"},
        {"check": "has_author", "passed": bool(req.author or tk.author), "message": "Author is specified"},
    ]

    return {
        "message": "Publishing coming soon. Below is the YAML that would be submitted to the community registry.",
        "name": name,
        "author": req.author or tk.author,
        "yaml": publish_yaml,
        "quality_checks": quality_checks,
        "pr_title": f"Add integration: {name}",
        "pr_body": f"## New Integration: {name}\n\n{req.description or tk.description}",
    }
