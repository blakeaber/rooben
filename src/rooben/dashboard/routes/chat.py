"""Workflow chat — conversational interface for inspecting results."""

from __future__ import annotations

import anthropic
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps
from rooben.dashboard.queries import tasks as task_queries
from rooben.dashboard.queries import workflows as wf_queries

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []  # [{role, content}]


class ChatResponse(BaseModel):
    reply: str


def _build_system_prompt(workflow: dict, tasks: list[dict]) -> str:
    """Build a system prompt with workflow context."""
    parts = [
        "You are a helpful assistant that answers questions about a workflow and its results.",
        f"Workflow ID: {workflow.get('id', 'unknown')}",
        f"Status: {workflow.get('status', 'unknown')}",
        "",
        "Tasks:",
    ]
    for t in tasks:
        status = t.get("status", "unknown")
        title = t.get("title", "untitled")
        parts.append(f"- [{status}] {title}")

        output = t.get("output") or (t.get("result", {}) or {}).get("output", "")
        if output:
            truncated = output[:2000]
            if len(output) > 2000:
                truncated += "... (truncated)"
            parts.append(f"  Output: {truncated}")

        error = t.get("error", "")
        if error:
            parts.append(f"  Error: {error[:500]}")

    # Artifact filenames
    artifact_files = []
    for t in tasks:
        result = t.get("result") or {}
        if isinstance(result, dict):
            artifacts = result.get("artifacts", {})
            if isinstance(artifacts, dict):
                artifact_files.extend(artifacts.keys())

    if artifact_files:
        parts.append("")
        parts.append(f"Artifact files: {', '.join(artifact_files)}")

    return "\n".join(parts)


@router.post("/api/workflows/{workflow_id}/chat", response_model=ChatResponse)
async def workflow_chat(
    workflow_id: str, req: ChatRequest, request: Request
) -> ChatResponse:
    """Chat about a workflow's results."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    wf_data = await wf_queries.get_workflow(deps.pool, workflow_id)
    if not wf_data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = wf_data.get("workflow", wf_data) if isinstance(wf_data, dict) else wf_data
    tasks = await task_queries.get_workflow_tasks(deps.pool, workflow_id)

    system_prompt = _build_system_prompt(workflow, tasks)

    # Build messages for Anthropic API
    messages = []
    for msg in req.history:
        role = msg.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    # Use server-configured LLM provider key (not the dashboard auth token)
    from rooben.agents.integrations import resolve_credential

    api_key = resolve_credential("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider key configured on server",
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        reply = response.content[0].text if response.content else ""
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid API key")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat error: {exc}")

    return ChatResponse(reply=reply)
