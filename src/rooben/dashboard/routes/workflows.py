"""Workflow API routes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from rooben.dashboard.deps import get_deps, user_context as _user_context
from rooben.dashboard.queries import workflows as wf_queries

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ─── Diagnostics models ──────────────────────────────────────────────────────

class DiagnosticItem(BaseModel):
    category: str
    severity: str
    title: str
    description: str
    suggestion: str
    affected_task_count: int
    affected_task_ids: list[str] = Field(default_factory=list)


class DiagnosticsResponse(BaseModel):
    workflow_id: str
    diagnostics: list[DiagnosticItem]
    recommendation: str
    has_failures: bool


@router.get("")
async def list_workflows(
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    deps = get_deps()
    workflows, total = await wf_queries.list_workflows(
        deps.pool, status=status, limit=limit, offset=offset,
        user_context=_user_context(request),
    )
    return {"workflows": workflows, "total": total}


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, request: Request):
    deps = get_deps()
    result = await wf_queries.get_workflow(
        deps.pool, workflow_id, user_context=_user_context(request),
    )
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Attach is_live flag so the frontend can detect orphaned workflows
    from rooben.dashboard.workflow_registry import get_registry
    registry = get_registry()
    wf_data = result.get("workflow", result) if isinstance(result, dict) else result
    if isinstance(wf_data, dict):
        wf_data["is_live"] = registry.get(workflow_id) is not None
    return result


@router.get("/{workflow_id}/dag")
async def get_workflow_dag(workflow_id: str):
    deps = get_deps()
    return await wf_queries.get_workflow_dag(deps.pool, workflow_id)


@router.get("/{workflow_id}/timeline")
async def get_workflow_timeline(workflow_id: str):
    deps = get_deps()
    events = await wf_queries.get_workflow_timeline(deps.pool, workflow_id)
    return {"events": events}


@router.get("/{workflow_id}/agents")
async def get_workflow_agents(workflow_id: str):
    """Return agents used in a specific workflow."""
    deps = get_deps()
    from rooben.dashboard.queries import agents as agent_queries
    agents = await agent_queries.get_workflow_agents(deps.pool, workflow_id)
    return {"agents": agents}


@router.get("/{workflow_id}/spec")
async def get_workflow_spec(workflow_id: str):
    """Return the persisted spec YAML and structured metadata."""
    deps = get_deps()
    row = await deps.pool.fetchrow(
        "SELECT spec_yaml, spec_metadata FROM workflows WHERE id = $1",
        workflow_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    spec_metadata = row["spec_metadata"]
    if isinstance(spec_metadata, str):
        spec_metadata = json.loads(spec_metadata)

    return {
        "spec_yaml": row["spec_yaml"],
        "spec_metadata": spec_metadata,
    }


@router.get("/{workflow_id}/diagnostics", response_model=DiagnosticsResponse)
async def get_workflow_diagnostics(workflow_id: str) -> DiagnosticsResponse:
    """Return user-friendly diagnostic summary for a workflow."""
    deps = get_deps()

    # Fetch tasks from DB
    from rooben.dashboard.queries import tasks as task_queries
    tasks_data = await task_queries.get_workflow_tasks(deps.pool, workflow_id)

    if not tasks_data:
        return DiagnosticsResponse(
            workflow_id=workflow_id,
            diagnostics=[],
            recommendation="",
            has_failures=False,
        )

    # Build a minimal WorkflowState for the analyzer
    from rooben.domain import Task, TaskResult, TaskStatus, WorkflowState
    from rooben.domain import VerificationFeedback

    state = WorkflowState()
    for td in tasks_data:
        task = Task(
            id=td["id"],
            title=td.get("title", ""),
            description=td.get("description", ""),
            workflow_id=workflow_id,
            workstream_id=td.get("workstream_id", ""),
            assigned_agent_id=td.get("assigned_agent_id"),
            status=TaskStatus(td.get("status", "pending")),
        )
        # Attach result if present
        if td.get("result") and isinstance(td["result"], dict):
            task.result = TaskResult(
                output=td["result"].get("output", ""),
                error=td["result"].get("error"),
            )
        # Fallback: if no result JSONB but error TEXT exists, create minimal result
        elif not td.get("result") and td.get("error"):
            task.result = TaskResult(error=td["error"])
        # Attach feedback if present
        if td.get("attempt_feedback") and isinstance(td["attempt_feedback"], list):
            task.attempt_feedback = [
                VerificationFeedback(
                    attempt=fb.get("attempt", 0),
                    verifier_type=fb.get("verifier_type", "llm_judge"),
                    passed=fb.get("passed", False),
                    score=fb.get("score", 0.0),
                    feedback=fb.get("feedback", ""),
                )
                for fb in td["attempt_feedback"]
                if isinstance(fb, dict)
            ]

        state.tasks[task.id] = task

    from rooben.observability.diagnostics import DiagnosticAnalyzer

    analyzer = DiagnosticAnalyzer()
    report = analyzer.analyze(state, workflow_id)
    friendly = analyzer.format_user_friendly(report)

    has_failures = bool(report.failure_categories)

    return DiagnosticsResponse(
        workflow_id=workflow_id,
        diagnostics=[
            DiagnosticItem(
                category=d.category,
                severity=d.severity,
                title=d.title,
                description=d.description,
                suggestion=d.suggestion,
                affected_task_count=d.affected_task_count,
                affected_task_ids=d.affected_task_ids,
            )
            for d in friendly
        ],
        recommendation=report.recommendation,
        has_failures=has_failures,
    )


# ─── Export as Template ──────────────────────────────────────────────────────

class ExportTemplateRequest(BaseModel):
    name: str = Field(..., description="Template name in kebab-case")


@router.post("/{workflow_id}/export-template")
async def export_workflow_as_template(workflow_id: str, body: ExportTemplateRequest):
    """Export a workflow spec as a local extension template."""
    deps = get_deps()

    # Validate kebab-case name
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", body.name):
        raise HTTPException(
            status_code=422,
            detail="Template name must be kebab-case (e.g. 'my-template')",
        )

    # Fetch spec data
    row = await deps.pool.fetchrow(
        "SELECT spec_yaml, spec_metadata FROM workflows WHERE id = $1",
        workflow_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    spec_yaml_content = row["spec_yaml"]
    if not spec_yaml_content:
        raise HTTPException(status_code=422, detail="Workflow has no spec to export")

    spec_metadata = row["spec_metadata"]
    if isinstance(spec_metadata, str):
        spec_metadata = json.loads(spec_metadata)
    if not spec_metadata:
        spec_metadata = {}

    # Build manifest from metadata
    manifest_data: dict = {
        "schema_version": 1,
        "name": body.name,
        "type": "template",
        "version": "1.0.0",
        "author": "exported",
        "license": "MIT",
        "description": spec_metadata.get("title", f"Template exported from workflow {workflow_id}"),
        "tags": ["exported"],
        "domain_tags": [],
        "category": "professional",
        "use_cases": [],
        "min_rooben_version": "0.1.0",
        "prefill": spec_metadata.get("description", ""),
        "spec_yaml_file": "spec.yaml",
        "requires": [],
    }

    # Extract structured fields from metadata when available
    if spec_metadata.get("deliverables"):
        manifest_data["template_deliverables"] = [
            {"name": d.get("name", ""), "description": d.get("description", ""), "deliverable_type": d.get("type", "document")}
            for d in spec_metadata["deliverables"]
            if isinstance(d, dict)
        ]

    if spec_metadata.get("acceptance_criteria"):
        manifest_data["template_acceptance_criteria"] = [
            {"description": c.get("description", str(c)), "priority": c.get("priority", "medium")}
            for c in spec_metadata["acceptance_criteria"]
            if isinstance(c, dict)
        ]

    if spec_metadata.get("agents"):
        manifest_data["template_agents"] = [
            {"name": a.get("name", ""), "description": a.get("description", ""), "capabilities": a.get("capabilities", [])}
            for a in spec_metadata["agents"]
            if isinstance(a, dict)
        ]

    # Write to .rooben/extensions/{name}/ (matches installer convention)
    install_dir = Path(".rooben") / "extensions" / body.name
    install_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = install_dir / "rooben-extension.yaml"
    spec_path = install_dir / "spec.yaml"

    with open(manifest_path, "w") as f:
        yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    with open(spec_path, "w") as f:
        f.write(spec_yaml_content)

    return {"name": body.name, "path": str(install_dir)}
