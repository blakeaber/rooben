"""POST /api/workflows — run a workflow via the API."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from rooben.dashboard.deps import get_deps, user_context as _user_context

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class ContextInput(BaseModel):
    type: Literal["file", "url"]
    filename: str | None = None
    content_base64: str | None = None
    url: str | None = None

    @field_validator("content_base64")
    @classmethod
    def validate_file_size(cls, v: str | None) -> str | None:
        if v is not None:
            import base64
            try:
                data = base64.b64decode(v)
            except Exception as exc:
                raise ValueError("Invalid base64 content") from exc
            if len(data) > MAX_FILE_SIZE:
                raise ValueError(f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit")
        return v


class WorkflowRequest(BaseModel):
    description: str
    spec_yaml: str | None = None
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    integration_names: list[str] | None = None
    context_inputs: list[ContextInput] | None = None


class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str = "started"


@router.post("/api/workflows", response_model=WorkflowResponse)
async def create_workflow(request: Request, req: WorkflowRequest) -> WorkflowResponse:
    """Create and run a new workflow in the background."""
    from rooben.dashboard.workflow_launcher import launch_workflow

    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        workflow_id = await launch_workflow(
            description=req.description,
            provider=req.provider,
            model=req.model,
            integration_names=req.integration_names,
            spec_yaml=req.spec_yaml,
            context_inputs=[ci.model_dump() for ci in req.context_inputs] if req.context_inputs else None,
            user_context=_user_context(request),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return WorkflowResponse(workflow_id=workflow_id, status="started")
