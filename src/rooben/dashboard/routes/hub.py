"""Unified Hub API — browse library across all extension types + adaptive builder."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rooben.extensions.builder_engine import ExtensionBuilderEngine

router = APIRouter(prefix="/api/hub", tags=["hub"])

# In-memory builder sessions (per-process; sufficient for single-server dashboard)
_builder_sessions: dict[str, ExtensionBuilderEngine] = {}

DISPLAY_TYPE_MAP = {
    "integration": "Data Source",
    "template": "Template",
    "agent": "Agent",
    "llm_provider": "LLM Provider",
}


# ---------------------------------------------------------------------------
# Unified Library
# ---------------------------------------------------------------------------

@router.get("/library")
async def unified_library(
    type: str | None = None,
    q: str | None = None,
    domain_tag: str | None = None,
    category: str | None = None,
):
    """Merged browse across integrations, templates, and agents."""
    from rooben.dashboard.orchestrator_factory import build_integration_registry
    from rooben.extensions.installer import is_installed
    from rooben.extensions.loader import load_all_extensions

    items: list[dict] = []
    seen_names: set[str] = set()

    # 1. Installed integrations from IntegrationRegistry (builtins + user + extensions)
    registry = build_integration_registry()
    for tk in registry.list_all():
        if tk.name in seen_names:
            continue
        seen_names.add(tk.name)
        item_type = tk.kind if tk.kind == "llm_provider" else "integration"
        try:
            servers = tk.mcp_server_factory("/tmp/_probe")
            server_count = len(servers)
        except Exception:
            server_count = 0
        items.append({
            "name": tk.name,
            "type": item_type,
            "display_type": DISPLAY_TYPE_MAP.get(item_type, "Data Source"),
            "source": tk.source or "builtin",
            "description": tk.description,
            "tags": [],
            "domain_tags": tk.domain_tags,
            "category": "",
            "use_cases": [],
            "installed": True,
            "cost_tier": tk.cost_tier,
            "server_count": server_count,
            "author": tk.author,
            "version": tk.version,
            "kind": tk.kind,
        })

    # 2. All extension manifests (Tier 1 + installed)
    manifests = load_all_extensions()
    for m in manifests:
        if m.name in seen_names:
            continue
        seen_names.add(m.name)
        ext_type = m.type.value
        item = {
            "name": m.name,
            "type": ext_type,
            "display_type": DISPLAY_TYPE_MAP.get(ext_type, ext_type),
            "source": "builtin",
            "description": m.description,
            "tags": m.tags,
            "domain_tags": m.domain_tags,
            "category": m.category,
            "use_cases": m.use_cases,
            "installed": is_installed(m.name),
            "author": m.author,
            "version": m.version,
        }
        # Type-specific fields
        if ext_type == "integration":
            item["cost_tier"] = m.cost_tier
            item["server_count"] = len(m.servers)
        elif ext_type == "template":
            item["prefill"] = m.prefill
            item["requires"] = m.requires
        elif ext_type == "agent":
            item["capabilities"] = m.capabilities
            item["integration"] = m.integration
            item["model_override"] = m.model_override
        items.append(item)

    # 3. Community library sample (integration-type only, for items not yet seen)
    community_items = _get_community_library()
    for ci in community_items:
        if ci["name"] in seen_names:
            continue
        seen_names.add(ci["name"])
        items.append({
            "name": ci["name"],
            "type": "integration",
            "display_type": "Data Source",
            "source": "community",
            "description": ci["description"],
            "tags": [],
            "domain_tags": ci.get("domain_tags", []),
            "category": "",
            "use_cases": [],
            "installed": False,
            "cost_tier": ci.get("cost_tier", 2),
            "server_count": len(ci.get("servers", [])),
            "author": ci.get("author", ""),
            "version": ci.get("version", "1.0.0"),
            "servers": ci.get("servers", []),
            "install_count": ci.get("install_count", 0),
        })

    # Apply filters
    if type:
        items = [i for i in items if i["type"] == type]
    if q:
        q_lower = q.lower()
        items = [
            i for i in items
            if q_lower in i["name"].lower()
            or q_lower in i["description"].lower()
            or any(q_lower in t.lower() for t in i.get("tags", []))
        ]
    if domain_tag:
        items = [i for i in items if domain_tag in i.get("domain_tags", [])]
    if category:
        items = [i for i in items if i.get("category") == category]

    # Build filter metadata
    all_types = sorted({i["type"] for i in items})
    all_domain_tags = sorted({t for i in items for t in i.get("domain_tags", [])})
    all_categories = sorted({i["category"] for i in items if i.get("category")})

    type_options = [
        {"value": t, "label": DISPLAY_TYPE_MAP.get(t, t)} for t in all_types
    ]

    return {
        "items": items,
        "total": len(items),
        "filters": {
            "types": type_options,
            "domain_tags": all_domain_tags,
            "categories": all_categories,
        },
    }


def _get_community_library() -> list[dict]:
    """Community library sample registry."""
    return [
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


# ---------------------------------------------------------------------------
# Builder session endpoints
# ---------------------------------------------------------------------------

class BuildStartRequest(BaseModel):
    description: str
    type: str | None = None


class BuildAnswerRequest(BaseModel):
    session_id: str
    answer: str


class BuildSessionRequest(BaseModel):
    session_id: str


@router.post("/build/start")
async def build_start(req: BuildStartRequest):
    """Start a new extension builder session."""
    from rooben.extensions.builder_engine import ExtensionBuilderEngine
    from rooben.dashboard.orchestrator_factory import get_llm_provider

    provider = get_llm_provider()
    engine = ExtensionBuilderEngine(provider, max_turns=10)
    questions = await engine.start(req.description, req.type)

    session_id = str(uuid.uuid4())
    _builder_sessions[session_id] = engine

    return {
        "session_id": session_id,
        "detected_type": engine.state.detected_type,
        "display_type": DISPLAY_TYPE_MAP.get(engine.state.detected_type, "Extension"),
        "questions": [q.model_dump() for q in questions],
        "phase": engine.state.phase,
        "completeness": engine.state.completeness,
    }


@router.post("/build/answer")
async def build_answer(req: BuildAnswerRequest):
    """Process an answer in an active builder session."""
    engine = _builder_sessions.get(req.session_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Builder session not found")

    result = await engine.process_answer(req.answer)

    from rooben.extensions.builder_state import ExtensionBuilderState

    if isinstance(result, ExtensionBuilderState):
        return {
            "session_id": req.session_id,
            "phase": "review",
            "completeness": engine.state.completeness,
            "questions": [],
        }

    return {
        "session_id": req.session_id,
        "phase": engine.state.phase,
        "completeness": engine.state.completeness,
        "questions": [q.model_dump() for q in result],
    }


@router.post("/build/draft")
async def build_draft(req: BuildSessionRequest):
    """Get a manifest draft from the builder session."""
    engine = _builder_sessions.get(req.session_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Builder session not found")

    draft = engine.get_draft()

    import yaml
    yaml_preview = yaml.dump(draft, default_flow_style=False, sort_keys=False)

    return {
        "session_id": req.session_id,
        "manifest": draft,
        "yaml_preview": yaml_preview,
    }


@router.post("/build/install")
async def build_install(req: BuildSessionRequest):
    """Install the extension from the builder session."""
    engine = _builder_sessions.get(req.session_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Builder session not found")

    draft = engine.get_draft()
    name = draft.get("name", "custom-extension")

    # Write manifest to .rooben/extensions/<name>/rooben-extension.yaml
    from pathlib import Path
    import yaml

    ext_dir = Path(f".rooben/extensions/{name}")
    ext_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = ext_dir / "rooben-extension.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(draft, f, default_flow_style=False, sort_keys=False)

    # Clean up session
    _builder_sessions.pop(req.session_id, None)

    return {
        "installed": True,
        "name": name,
        "path": str(manifest_path),
        "type": draft.get("type", ""),
        "display_type": DISPLAY_TYPE_MAP.get(draft.get("type", ""), "Extension"),
    }
