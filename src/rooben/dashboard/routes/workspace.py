"""Workspace file access — list, download, and ZIP export."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from rooben.dashboard.deps import get_deps
from rooben.workspace.local import LocalWorkspaceStorage

router = APIRouter(tags=["workspace"])


async def _get_workspace_dir(workflow_id: str) -> Path:
    """Resolve workspace_dir for a workflow or raise 404."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    row = await deps.pool.fetchrow(
        "SELECT workspace_dir FROM workflows WHERE id = $1",
        workflow_id,
    )
    if not row or not row["workspace_dir"]:
        raise HTTPException(status_code=404, detail="No workspace for this workflow")

    ws_path = Path(row["workspace_dir"])
    if not ws_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    return ws_path


def _validate_path(workspace: Path, file_path: str) -> Path:
    """Resolve file_path within workspace, rejecting traversal attempts."""
    resolved = (workspace / file_path).resolve()
    if not str(resolved).startswith(str(workspace.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return resolved


def _normalize_artifact_path(artifact_path: str, ws_path: Path) -> str:
    """Strip container-specific prefixes to produce a clean relative path."""
    ws_str = str(ws_path)
    # Strip known container prefixes
    for prefix in [ws_str, "/app/.rooben/state/", "/app/.rooben/workspaces/"]:
        if artifact_path.startswith(prefix):
            artifact_path = artifact_path[len(prefix):]
            break
    # Remove leading workflow ID path component if present
    parts = artifact_path.strip("/").split("/", 1)
    if len(parts) > 1 and len(parts[0]) >= 8 and "-" in parts[0]:
        artifact_path = parts[1]
    return artifact_path.strip("/")


async def _get_db_artifacts(workflow_id: str) -> dict[str, str]:
    """Fetch all task artifacts from DB for a workflow."""
    deps = get_deps()
    if not deps.pool:
        return {}

    rows = await deps.pool.fetch(
        "SELECT result FROM tasks WHERE workflow_id = $1 AND result IS NOT NULL",
        workflow_id,
    )
    artifacts: dict[str, str] = {}
    for row in rows:
        result = row["result"]
        if isinstance(result, str):
            result = json.loads(result)
        for path, content in (result.get("artifacts") or {}).items():
            if content and len(content) > 50:  # skip placeholders
                artifacts[path] = content
    return artifacts


async def _generate_readme(workflow_id: str, pool: object, ws_path: Path) -> str:
    """Generate a README.md from workflow metadata."""
    # Query workflow info
    wf_row = await pool.fetchrow(
        """SELECT status, total_tasks, completed_tasks, failed_tasks,
                  created_at, completed_at, spec_metadata
           FROM workflows WHERE id = $1""",
        workflow_id,
    )
    if not wf_row:
        return f"# Workflow {workflow_id}\n\nNo metadata available.\n"

    metadata = {}
    if wf_row["spec_metadata"]:
        try:
            metadata = json.loads(wf_row["spec_metadata"]) if isinstance(
                wf_row["spec_metadata"], str
            ) else wf_row["spec_metadata"]
        except (json.JSONDecodeError, TypeError):
            pass

    description = metadata.get("goal", metadata.get("title", "Workflow output"))

    # Query tasks
    task_rows = await pool.fetch(
        """SELECT title, status, result FROM tasks
           WHERE workflow_id = $1 ORDER BY created_at""",
        workflow_id,
    )

    # Query workstreams
    ws_rows = await pool.fetch(
        "SELECT name, status FROM workstreams WHERE workflow_id = $1",
        workflow_id,
    )

    # Calculate cost from token usage
    total_tokens = 0
    for tr in task_rows:
        if tr["result"]:
            r = tr["result"]
            if isinstance(r, str):
                r = json.loads(r)
            total_tokens += r.get("token_usage", 0)
    cost = total_tokens * 0.000003  # rough estimate

    # Build project structure
    top_level: list[str] = []
    if ws_path.is_dir():
        for entry in sorted(ws_path.iterdir()):
            name = entry.name
            if name in ("node_modules", ".git", "__pycache__", ".venv", "venv"):
                continue
            suffix = "/" if entry.is_dir() else ""
            top_level.append(f"  {name}{suffix}")

    # Auto-detect quick start
    quick_start_lines: list[str] = []
    if ws_path.is_dir():
        if (ws_path / "requirements.txt").exists():
            quick_start_lines.append("pip install -r requirements.txt")
        if (ws_path / "package.json").exists():
            quick_start_lines.append("npm install && npm start")
        if (ws_path / "main.py").exists():
            quick_start_lines.append("python main.py")
        if (ws_path / "index.html").exists():
            quick_start_lines.append("open index.html")
    if not quick_start_lines:
        quick_start_lines.append("Review the project files to determine how to run.")

    # Render
    parts = [
        f"# Workflow Output: {description[:100]}",
        "",
        "## Overview",
        f"- **Workflow ID**: `{workflow_id}`",
        f"- **Status**: {wf_row['status']}",
        f"- **Tasks**: {wf_row['completed_tasks']}/{wf_row['total_tasks']} completed",
        f"- **Estimated cost**: ${cost:.2f}",
        f"- **Generated**: {wf_row.get('completed_at') or wf_row.get('created_at', 'N/A')}",
    ]

    if ws_rows:
        parts.append("")
        parts.append("## Workstreams")
        for ws in ws_rows:
            parts.append(f"- **{ws['name']}**: {ws['status']}")

    if top_level:
        parts.append("")
        parts.append("## Project structure")
        parts.append("```")
        parts.extend(top_level)
        parts.append("```")

    parts.append("")
    parts.append("## Quick start")
    parts.append("```bash")
    parts.extend(quick_start_lines)
    parts.append("```")

    if task_rows:
        parts.append("")
        parts.append("## Task outputs")
        for tr in task_rows:
            status_icon = "pass" if tr["status"] == "passed" else tr["status"]
            summary = ""
            if tr["result"]:
                r = tr["result"]
                if isinstance(r, str):
                    r = json.loads(r)
                summary = (r.get("output") or "")[:200]
            parts.append(f"- **{tr['title']}** [{status_icon}]: {summary}")

    parts.append("")
    parts.append("---")
    parts.append("Generated by Rooben")
    parts.append("")

    return "\n".join(parts)


@router.get("/api/workflows/{workflow_id}/files")
async def list_workspace_files(workflow_id: str):
    """List all files in the workflow workspace, including DB-only artifacts."""
    deps = get_deps()
    storage: LocalWorkspaceStorage = deps.workspace_storage
    ws_path = await _get_workspace_dir(workflow_id)

    # Disk files via storage protocol
    entries = await storage.list_files(str(ws_path))
    result = [
        {
            "path": e.path,
            "size_bytes": e.size_bytes,
            "source": e.source,
        }
        for e in entries
    ]

    # Add DB-only artifacts not found on disk
    disk_paths = {e.path for e in entries}
    db_artifacts = await _get_db_artifacts(workflow_id)
    for artifact_path, content in db_artifacts.items():
        rel = _normalize_artifact_path(artifact_path, ws_path)
        if rel not in disk_paths:
            result.append({
                "path": rel,
                "size_bytes": len(content),
                "source": "artifact",
            })

    result.sort(key=lambda f: f["path"])
    return result


@router.get("/api/workflows/{workflow_id}/files/zip")
async def download_workspace_zip(workflow_id: str):
    """Download the workspace as a ZIP, merging disk files + DB artifacts + README."""
    import io
    import zipfile

    deps = get_deps()
    storage: LocalWorkspaceStorage = deps.workspace_storage
    ws_path = await _get_workspace_dir(workflow_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Step 1: Add disk files (excluding node_modules etc.)
        disk_paths: set[str] = set()
        disk_entries = await storage.list_files(str(ws_path))
        for entry in disk_entries:
            full = ws_path / entry.path
            if full.is_file():
                zf.write(str(full), entry.path)
                disk_paths.add(entry.path)

        # Step 2: Add DB-only artifacts
        db_artifacts = await _get_db_artifacts(workflow_id)
        for artifact_path, content in db_artifacts.items():
            rel = _normalize_artifact_path(artifact_path, ws_path)
            if rel not in disk_paths:
                arcname = f"artifacts/{rel}" if not rel.startswith("artifacts/") else rel
                zf.writestr(arcname, content)

        # Step 3: Generate and add README
        if deps.pool:
            readme = await _generate_readme(workflow_id, deps.pool, ws_path)
            zf.writestr("README.md", readme)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="workspace-{workflow_id[:12]}.zip"',
        },
    )


@router.get("/api/workflows/{workflow_id}/files/{file_path:path}")
async def download_file(workflow_id: str, file_path: str):
    """Download a single file from the workspace."""
    ws_path = await _get_workspace_dir(workflow_id)
    resolved = _validate_path(ws_path, file_path)
    return FileResponse(resolved, filename=resolved.name)


@router.get("/api/admin/storage")
async def storage_usage():
    """Return total workspace storage usage across all workflows."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    storage: LocalWorkspaceStorage = deps.workspace_storage

    rows = await deps.pool.fetch(
        "SELECT id, workspace_dir FROM workflows WHERE workspace_dir IS NOT NULL",
    )

    total_bytes = 0
    workflow_sizes: list[dict] = []
    for row in rows:
        if row["workspace_dir"]:
            size = await storage.workspace_size(row["workspace_dir"])
            total_bytes += size
            workflow_sizes.append({
                "workflow_id": row["id"],
                "size_bytes": size,
            })

    workflow_sizes.sort(key=lambda w: w["size_bytes"], reverse=True)

    return {
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 1),
        "workflow_count": len(workflow_sizes),
        "workflows": workflow_sizes[:20],  # top 20 by size
    }
