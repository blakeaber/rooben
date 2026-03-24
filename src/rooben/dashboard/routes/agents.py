"""Agent API routes — performance + introspection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps
from rooben.dashboard.queries import agents as agent_queries

router = APIRouter(prefix="/api/agents", tags=["agents"])


class UpdateAgentRequest(BaseModel):
    integration: str | None = None
    prompt_template: str | None = None
    model_override: str | None = None


@router.get("/performance")
async def agent_performance():
    deps = get_deps()
    agents = await agent_queries.agent_performance(deps.pool)
    return {"agents": agents}


@router.get("")
async def list_agents():
    """List all agents with spec + summary stats."""
    deps = get_deps()
    agents = await agent_queries.list_agents(deps.pool)
    return {"agents": agents}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Single agent detail with performance and recent tasks."""
    deps = get_deps()
    agent = await agent_queries.get_agent(deps.pool, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, req: UpdateAgentRequest):
    """Update agent configuration (integration, prompt_template, model_override)."""
    deps = get_deps()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await agent_queries.update_agent(deps.pool, agent_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"updated": True, **result}
