"""Interactive refinement API — chat-style spec building for the Create UX."""

from __future__ import annotations

import asyncio
import base64
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from rooben.dashboard.deps import get_deps, user_context as _user_context

router = APIRouter()

# In-memory session store (keyed by session ID)
_sessions: dict[str, object] = {}


class ContextInput(BaseModel):
    type: str  # "file" or "url"
    filename: str | None = None
    content_base64: str | None = None
    url: str | None = None


class StartRequest(BaseModel):
    description: str
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    template_spec_yaml: str = ""
    template_name: str = ""
    context_inputs: list[ContextInput] | None = None


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


class SessionIdRequest(BaseModel):
    session_id: str


class QuestionItem(BaseModel):
    text: str
    choices: list[str] = Field(default_factory=list)
    allow_freeform: bool = True


class SessionInfo(BaseModel):
    sessionId: str
    completeness: float
    phase: str


class QuestionResponse(BaseModel):
    questions: list[QuestionItem]
    session: SessionInfo
    review_ready: bool = False


class IntegrationCheckItem(BaseModel):
    name: str
    integration: str
    status: str
    connect_url: str
    required: bool = True


class SpecSummary(BaseModel):
    title: str = ""
    goal: str = ""
    deliverables: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    input_sources: list[str] = Field(default_factory=list)


class PlanSummaryResponse(BaseModel):
    task_count: int
    agent_count: int
    deliverable_count: int
    title: str = ""
    goal: str = ""


class DraftResponse(BaseModel):
    yaml: str
    summary: SpecSummary


class LaunchResponse(BaseModel):
    workflow_id: str
    status: str = "started"


def _get_session(session_id: str):
    """Retrieve a refinement session or raise 404."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/api/refine/start", response_model=QuestionResponse)
async def start_refinement(req: StartRequest) -> QuestionResponse:
    """Start a new refinement session from an initial description."""
    from rooben.dashboard.orchestrator_factory import _build_provider
    from rooben.refinement.engine import LLMUnavailableError, RefinementEngine

    # Pre-check: ensure an API key is available before creating the engine
    from rooben.agents.integrations import resolve_credential
    if not resolve_credential("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=401,
            detail=(
                "No API key configured. Please set your ANTHROPIC_API_KEY "
                "in Settings (/settings) or in your .env file."
            ),
        )

    provider = _build_provider(req.provider, req.model)

    # Build extension context for refinement — grouped by readiness and type
    extension_context = ""
    try:
        from rooben.extensions.loader import get_all_extension_metadata
        metadata = get_all_extension_metadata()
        if metadata:
            ready_integrations = [e for e in metadata if e["type"] == "integration" and e.get("ready")]
            available_integrations = [e for e in metadata if e["type"] == "integration" and not e.get("ready")]
            templates = [e for e in metadata if e["type"] == "template"]
            agents = [e for e in metadata if e["type"] == "agent"]

            sections = []
            if ready_integrations:
                lines = ["READY data sources (configured and available):"]
                for ext in ready_integrations:
                    checks_summary = ", ".join(c["message"] for c in ext.get("checks", []) if c["passed"])
                    lines.append(f"- {ext['name']} (integration): {ext['description']}")
                    if checks_summary:
                        lines.append(f"  \u2713 {checks_summary}")
                sections.append("\n".join(lines))

            if available_integrations:
                lines = ["AVAILABLE data sources (need setup):"]
                for ext in available_integrations:
                    missing = [c["message"] for c in ext.get("checks", []) if not c["passed"]]
                    lines.append(f"- {ext['name']} (integration): {ext['description']}")
                    if missing:
                        lines.append(f"  \u2717 {'; '.join(missing)}")
                sections.append("\n".join(lines))

            if templates:
                lines = ["TEMPLATES (workflow starting points):"]
                for ext in templates:
                    lines.append(f"- {ext['name']} (template): {ext['description']}")
                    if ext.get("use_cases"):
                        for uc in ext["use_cases"][:2]:
                            lines.append(f"  Use case: {uc}")
                sections.append("\n".join(lines))

            if agents:
                lines = ["AGENT PRESETS:"]
                for ext in agents:
                    lines.append(f"- {ext['name']} (agent): {ext['description']}")
                sections.append("\n".join(lines))

            extension_context = "\n\n".join(sections)
    except Exception:
        pass  # Extension system is optional

    # Build user-uploaded file context for the refinement engine
    file_context = ""
    if req.context_inputs:
        file_sections: list[str] = []
        max_chars_per_file = 5000
        for ci in req.context_inputs:
            if ci.type == "file" and ci.content_base64 and ci.filename:
                try:
                    raw = base64.b64decode(ci.content_base64)
                    text = raw.decode("utf-8", errors="replace")
                    if len(text) > max_chars_per_file:
                        text = text[:max_chars_per_file] + f"\n... [truncated, {len(raw)} bytes total]"
                    file_sections.append(f"### File: {ci.filename}\n{text}")
                except Exception:
                    file_sections.append(f"### File: {ci.filename}\n[unable to decode file content]")
            elif ci.type == "url" and ci.url:
                file_sections.append(f"### URL: {ci.url}")
        if file_sections:
            file_context = "USER-UPLOADED CONTEXT FILES:\n\n" + "\n\n".join(file_sections)

    engine = RefinementEngine(
        provider=provider,
        max_turns=20,
        extension_context=extension_context,
        file_context=file_context,
    )

    session_id = f"refine-{uuid.uuid4().hex[:12]}"

    # Seed GatheredInfo from template extension structure (Phase 4)
    if req.template_name:
        try:
            from rooben.extensions.loader import load_all_extensions
            from rooben.extensions.manifest import ExtensionType
            ext_manifests = load_all_extensions()
            tpl_manifest = next((m for m in ext_manifests if m.name == req.template_name and m.type == ExtensionType.TEMPLATE), None)
            if tpl_manifest:
                info = engine.state.gathered_info
                if tpl_manifest.template_agents and not info.agents:
                    info.agents = tpl_manifest.template_agents
                if tpl_manifest.template_deliverables and not info.deliverables:
                    info.deliverables = tpl_manifest.template_deliverables
                if tpl_manifest.template_acceptance_criteria and not info.acceptance_criteria:
                    info.acceptance_criteria = tpl_manifest.template_acceptance_criteria
                if tpl_manifest.template_input_sources and not info.input_sources:
                    info.input_sources = tpl_manifest.template_input_sources
                if tpl_manifest.template_workflow_hints:
                    engine._template_workflow_hints = tpl_manifest.template_workflow_hints
        except Exception:
            pass  # Best-effort

    # If a template spec is provided, enrich the description with template context
    description = req.description
    if req.template_spec_yaml:
        import yaml as _yaml
        try:
            tpl = _yaml.safe_load(req.template_spec_yaml) or {}
            parts = [f"Based on template: {req.template_name or 'imported'}"]
            if tpl.get("title"):
                parts.append(f"Title: {tpl['title']}")
            if tpl.get("goal"):
                parts.append(f"Goal: {tpl['goal']}")
            if tpl.get("context"):
                parts.append(f"Context: {tpl['context']}")
            if isinstance(tpl.get("deliverables"), list):
                names = [d.get("name", str(d)) for d in tpl["deliverables"] if isinstance(d, dict)]
                if names:
                    parts.append(f"Deliverables: {', '.join(names)}")
            if isinstance(tpl.get("constraints"), list):
                descs = [c.get("description", str(c)) for c in tpl["constraints"] if isinstance(c, dict)]
                if descs:
                    parts.append(f"Constraints: {'; '.join(descs)}")
            template_context = "\n".join(parts)
            description = f"{template_context}\n\nUser additions: {description}" if description else template_context
        except _yaml.YAMLError:
            pass

    try:
        questions = await engine.start(description)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    # Store the session (and the user's key for later use in launch)
    _sessions[session_id] = {
        "engine": engine,
        "provider_name": req.provider,
        "model": req.model,
        "template_name": req.template_name or None,
    }

    return QuestionResponse(
        questions=[
            QuestionItem(
                text=q.text,
                choices=q.choices,
                allow_freeform=q.allow_freeform,
            )
            for q in questions
        ],
        session=SessionInfo(
            sessionId=session_id,
            completeness=engine.state.completeness,
            phase=engine.state.phase,
        ),
    )


@router.post("/api/refine/answer", response_model=QuestionResponse)
async def process_answer(req: AnswerRequest) -> QuestionResponse:
    """Process a user answer and return next questions or review signal."""
    from rooben.refinement.engine import LLMUnavailableError
    from rooben.refinement.state import ConversationState

    session_data = _get_session(req.session_id)
    engine = session_data["engine"]

    try:
        result = await engine.process_answer(req.answer)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    review_ready = isinstance(result, ConversationState)

    if review_ready:
        questions = []
    else:
        questions = [
            QuestionItem(
                text=q.text,
                choices=q.choices,
                allow_freeform=q.allow_freeform,
            )
            for q in result
        ]

    return QuestionResponse(
        questions=questions,
        session=SessionInfo(
            sessionId=req.session_id,
            completeness=engine.state.completeness,
            phase=engine.state.phase,
        ),
        review_ready=review_ready,
    )


@router.post("/api/refine/continue", response_model=QuestionResponse)
async def continue_refining(req: SessionIdRequest) -> QuestionResponse:
    """Continue refining after review-ready state."""
    session_data = _get_session(req.session_id)
    engine = session_data["engine"]

    questions = await engine.continue_refining()

    return QuestionResponse(
        questions=[
            QuestionItem(
                text=q.text,
                choices=q.choices,
                allow_freeform=q.allow_freeform,
            )
            for q in questions
        ],
        session=SessionInfo(
            sessionId=req.session_id,
            completeness=engine.state.completeness,
            phase=engine.state.phase,
        ),
    )


@router.post("/api/refine/plan-summary", response_model=PlanSummaryResponse)
async def plan_summary(req: SessionIdRequest) -> PlanSummaryResponse:
    """Return a lightweight plan summary from the current refinement session."""
    session_data = _get_session(req.session_id)
    engine = session_data["engine"]
    info = engine.state.gathered_info

    return PlanSummaryResponse(
        task_count=len(info.deliverables),
        agent_count=len(info.agents),
        deliverable_count=len(info.deliverables),
        title=info.title,
        goal=info.goal,
    )


@router.get("/api/refine/draft")
async def get_draft_preview(session_id: str, preview: bool = True) -> DraftResponse:
    """Return current spec state as a preview without finalizing."""
    session_data = _get_session(session_id)
    engine = session_data["engine"]

    yaml_str = await engine.get_draft_yaml()
    info = engine.state.gathered_info

    return DraftResponse(
        yaml=yaml_str,
        summary=_build_spec_summary(info),
    )


@router.post("/api/refine/draft", response_model=DraftResponse)
async def get_draft(req: SessionIdRequest) -> DraftResponse:
    """Generate a draft spec YAML from the current session state."""
    session_data = _get_session(req.session_id)
    engine = session_data["engine"]

    yaml_str = await engine.get_draft_yaml()
    info = engine.state.gathered_info

    return DraftResponse(
        yaml=yaml_str,
        summary=_build_spec_summary(info),
    )


def _build_spec_summary(info) -> SpecSummary:
    """Build a SpecSummary from GatheredInfo."""
    return SpecSummary(
        title=info.title,
        goal=info.goal,
        deliverables=[
            d.get("name", d.get("description", str(d)))
            for d in info.deliverables
        ],
        agents=[
            a.get("name", a.get("id", str(a)))
            for a in info.agents
        ],
        acceptance_criteria=[
            c.get("description", str(c))
            for c in info.acceptance_criteria
        ],
        constraints=[
            c.get("description", str(c))
            for c in info.constraints
        ],
        input_sources=[
            f"{s.get('integration', s.get('type', 'unknown'))}: {s.get('description', s.get('name', ''))}"
            for s in info.input_sources
        ],
    )


@router.get("/api/refine/integration-check")
async def check_spec_integrations(session_id: str):
    """Check availability of integrations required by the current spec draft.

    OSS returns a flat list derived from the spec's declared input sources;
    Pro extends this endpoint (via the extension protocol) with external-service
    availability checks (OAuth status, API reachability, etc.).
    """
    session_data = _get_session(session_id)
    engine = session_data["engine"]
    info = engine.state.gathered_info

    sources = [
        {
            "name": s.get("integration") or s.get("type") or "unknown",
            "description": s.get("description") or s.get("name") or "",
            "available": None,
        }
        for s in info.input_sources
    ]
    return {"sources": sources}


@router.post("/api/refine/launch", response_model=LaunchResponse)
async def launch_workflow(req: SessionIdRequest, request: Request = None) -> LaunchResponse:
    """Accept the spec and launch a workflow."""
    from rooben.dashboard.event_adapter import DashboardEventAdapter
    from rooben.dashboard.orchestrator_factory import build_orchestrator
    from rooben.dashboard.routes.events import broadcaster

    session_data = _get_session(req.session_id)
    engine = session_data["engine"]
    provider_name = session_data["provider_name"]
    model = session_data["model"]
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    # Build the final spec
    spec = await engine.accept()

    # Create workspace
    workspace_id = uuid.uuid4().hex[:12]
    workspace_dir = str((Path(".rooben/workspaces") / workspace_id).resolve())
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)
    spec.workspace_dir = workspace_dir

    # Wire event adapter
    adapter = DashboardEventAdapter(pool=deps.pool, broadcaster=broadcaster)

    async def event_callback(event_type: str, payload: dict) -> None:
        await adapter.handle_event(event_type, payload)

    # Generate workflow ID upfront so client and orchestrator share it
    workflow_id = f"wf-{uuid.uuid4().hex[:8]}"

    # Insert a placeholder row immediately so the workflow appears on the
    # list page right away, before the planner finishes.
    template_name = session_data.get("template_name")
    uctx = _user_context(request) if request else None
    if uctx and uctx.get("user_id"):
        await deps.pool.execute(
            """INSERT INTO workflows (id, spec_id, status, template_name, created_at, user_id, org_id)
               VALUES ($1, $2, 'planning', $3, now(), $4, $5)
               ON CONFLICT (id) DO NOTHING""",
            workflow_id, spec.id, template_name,
            uctx["user_id"], uctx.get("org_id"),
        )
    else:
        await deps.pool.execute(
            """INSERT INTO workflows (id, spec_id, status, template_name, created_at)
               VALUES ($1, $2, 'planning', $3, now())
               ON CONFLICT (id) DO NOTHING""",
            workflow_id, spec.id, template_name,
        )

    # Seed agents + spec metadata directly (no longer done via event adapter)
    from rooben.dashboard.workflow_launcher import _seed_agents_and_spec
    await _seed_agents_and_spec(deps.pool, workflow_id, spec)

    orchestrator, mcp_pool = build_orchestrator(
        spec=spec,
        provider_name=provider_name,
        model=model,
        event_callback=event_callback,
        pg_pool=deps.pool,
    )

    async def _run() -> None:
        try:
            await orchestrator.run(spec, workflow_id=workflow_id)
        except Exception:
            # Mark workflow failed in DB so it doesn't appear stuck
            try:
                await deps.pool.execute(
                    """UPDATE workflows SET status = 'failed', completed_at = now()
                       WHERE id = $1 AND status != 'completed'""",
                    workflow_id,
                )
                await deps.pool.execute(
                    """UPDATE tasks SET status = 'cancelled', completed_at = now()
                       WHERE workflow_id = $1 AND status IN ('pending', 'in_progress')""",
                    workflow_id,
                )
            except Exception:
                pass
        finally:
            await mcp_pool.close_all()
            # Clean up session
            _sessions.pop(req.session_id, None)

    asyncio.create_task(_run())

    return LaunchResponse(workflow_id=workflow_id, status="started")
