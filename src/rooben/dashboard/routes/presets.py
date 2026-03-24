"""Agent preset API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps, user_context as _user_context
from rooben.dashboard.queries import presets as preset_queries
from rooben.dashboard.queries import agents as agent_queries

router = APIRouter(prefix="/api/presets", tags=["presets"])


class CreatePresetRequest(BaseModel):
    name: str
    description: str = ""
    integration: str | None = None
    prompt_template: str = ""
    model_override: str = ""
    capabilities: list[str] = []
    max_context_tokens: int = 200000
    budget: dict | None = None


class UpdatePresetRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    integration: str | None = None
    prompt_template: str | None = None
    model_override: str | None = None
    capabilities: list[str] | None = None
    max_context_tokens: int | None = None
    budget: dict | None = None


@router.get("")
async def list_presets(request: Request):
    """List all agent presets."""
    deps = get_deps()
    presets = await preset_queries.list_presets(
        deps.pool, user_context=_user_context(request),
    )
    return {"presets": presets}


@router.post("")
async def create_preset(req: CreatePresetRequest):
    """Create a new agent preset."""
    deps = get_deps()
    data = req.model_dump()
    data["id"] = str(uuid.uuid4())
    preset = await preset_queries.create_preset(deps.pool, data)
    return {"created": True, **preset}


@router.post("/from-agent/{agent_id}")
async def create_preset_from_agent(agent_id: str, name: str = ""):
    """Snapshot an agent's config as a preset."""
    deps = get_deps()
    agent = await agent_queries.get_agent(deps.pool, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    preset_name = name or f"{agent['name']}-preset"
    data = {
        "id": str(uuid.uuid4()),
        "name": preset_name,
        "description": f"Preset from agent '{agent['name']}'",
        "integration": agent.get("integration"),
        "prompt_template": agent.get("prompt_template", ""),
        "model_override": agent.get("model_override", ""),
        "capabilities": agent.get("capabilities", []),
        "max_context_tokens": agent.get("max_context_tokens", 200000),
        "budget": agent.get("budget"),
    }
    preset = await preset_queries.create_preset(deps.pool, data)
    return {"created": True, **preset}


@router.put("/{preset_id}")
async def update_preset(preset_id: str, req: UpdatePresetRequest):
    """Update an existing preset."""
    deps = get_deps()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await preset_queries.update_preset(deps.pool, preset_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"updated": True, **result}


@router.delete("/{preset_id}")
async def delete_preset(preset_id: str):
    """Delete a preset."""
    deps = get_deps()
    deleted = await preset_queries.delete_preset(deps.pool, preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"deleted": True}


@router.post("/{preset_id}/apply/{agent_id}")
async def apply_preset_to_agent(preset_id: str, agent_id: str):
    """Apply a preset's config to an agent."""
    deps = get_deps()
    preset = await preset_queries.get_preset(deps.pool, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    updates = {}
    if preset.get("integration"):
        updates["integration"] = preset["integration"]
    if preset.get("prompt_template"):
        updates["prompt_template"] = preset["prompt_template"]
    if preset.get("model_override"):
        updates["model_override"] = preset["model_override"]

    if not updates:
        raise HTTPException(status_code=400, detail="Preset has no applicable config")

    result = await agent_queries.update_agent(deps.pool, agent_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"applied": True, "preset_id": preset_id, "agent": result}
