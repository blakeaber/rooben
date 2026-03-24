"""Personal dashboard API endpoints — /api/me/*."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps
from rooben.dashboard.models.user import ANONYMOUS_USER
from rooben.dashboard.queries import (
    dashboard_summary,
    goals as goal_queries,
    outcomes as outcome_queries,
    roles as role_queries,
    user_preferences as pref_queries,
)

router = APIRouter(prefix="/api/me", tags=["me"])


def _get_user(request: Request):
    return getattr(request.state, "current_user", ANONYMOUS_USER)


def _require_pool():
    """Return the database pool or raise 503 if unavailable."""
    deps = get_deps()
    if deps.pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return deps.pool


# ── Identity ──────────────────────────────────────────────────────────


@router.get("/identity")
async def get_identity(request: Request):
    user = _get_user(request)
    return {
        "id": user.id,
        "is_anonymous": user.id == "anonymous",
    }


# ── Dashboard ──────────────────────────────────────────────────────────


@router.get("/dashboard")
async def get_dashboard(request: Request):
    deps = get_deps()
    user = _get_user(request)
    data = await dashboard_summary.get_user_dashboard(deps.pool, user.id)
    return data


# ── Preferences ────────────────────────────────────────────────────────


@router.get("/preferences")
async def get_preferences(request: Request):
    deps = get_deps()
    user = _get_user(request)
    prefs = await pref_queries.get_preferences(deps.pool, user.id)
    return {"preferences": prefs}


class UpdatePreferencesRequest(BaseModel):
    default_provider: str | None = None
    default_model: str | None = None
    integration_preferences: list[str] | None = None


@router.put("/preferences")
async def update_preferences(req: UpdatePreferencesRequest, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    prefs = await pref_queries.update_preferences(pool, user.id, updates)
    return {"preferences": prefs}


# Also accept POST for preferences (frontend convenience)
@router.post("/preferences")
async def update_preferences_post(req: UpdatePreferencesRequest, request: Request):
    return await update_preferences(req, request)


# ── Goals ──────────────────────────────────────────────────────────────


@router.get("/goals")
async def list_goals(request: Request, status: str | None = None):
    deps = get_deps()
    user = _get_user(request)
    if user.id == "anonymous":
        return {"goals": []}
    goals = await goal_queries.list_goals(deps.pool, user.id, status=status)
    return {"goals": goals}


class CreateGoalRequest(BaseModel):
    title: str
    description: str = ""
    target_date: str | None = None
    tags: list[str] = []


@router.post("/goals")
async def create_goal(req: CreateGoalRequest, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    import datetime

    data = req.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user.id
    if data.get("target_date"):
        data["target_date"] = datetime.date.fromisoformat(data["target_date"])
    else:
        data["target_date"] = None
    goal = await goal_queries.create_goal(pool, data)
    return {"created": True, **goal}


class UpdateGoalRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    target_date: str | None = None
    tags: list[str] | None = None


@router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, req: UpdateGoalRequest, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "target_date" in updates:
        import datetime
        updates["target_date"] = datetime.date.fromisoformat(updates["target_date"])
    result = await goal_queries.update_goal(pool, goal_id, user.id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"updated": True, **result}


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    deleted = await goal_queries.delete_goal(pool, goal_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"deleted": True}


# ── Roles ──────────────────────────────────────────────────────────────


@router.get("/roles")
async def list_roles(request: Request):
    deps = get_deps()
    user = _get_user(request)
    if user.id == "anonymous":
        return {"roles": []}
    roles = await role_queries.list_roles(deps.pool, user.id)
    return {"roles": roles}


class CreateRoleRequest(BaseModel):
    title: str
    department: str = ""
    context: str = ""
    is_active: bool = True


@router.post("/roles")
async def create_role(req: CreateRoleRequest, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    data = req.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user.id
    role = await role_queries.create_role(pool, data)
    return {"created": True, **role}


class UpdateRoleRequest(BaseModel):
    title: str | None = None
    department: str | None = None
    context: str | None = None
    is_active: bool | None = None


@router.put("/roles/{role_id}")
async def update_role(role_id: str, req: UpdateRoleRequest, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await role_queries.update_role(pool, role_id, user.id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"updated": True, **result}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    deleted = await role_queries.delete_role(pool, role_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"deleted": True}


# ── Outcomes ───────────────────────────────────────────────────────────


@router.get("/outcomes")
async def list_outcomes(request: Request, goal_id: str | None = None, limit: int = 20):
    deps = get_deps()
    user = _get_user(request)
    if user.id == "anonymous":
        return {"outcomes": []}
    outcomes = await outcome_queries.list_outcomes(deps.pool, user.id, goal_id=goal_id, limit=limit)
    return {"outcomes": outcomes}


# ── Default Preset ─────────────────────────────────────────────────────


@router.post("/presets/{preset_id}/default")
async def set_default_preset(preset_id: str, request: Request):
    user = _get_user(request)
    pool = _require_pool()
    ok = await pref_queries.set_default_preset(pool, user.id, preset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"set_default": True, "preset_id": preset_id}
