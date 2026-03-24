"""Community publishing API routes — publish, browse, install, flag, rate."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from rooben.dashboard.auth import get_current_user_id
from rooben.dashboard.deps import get_deps
from rooben.dashboard.queries import community as comm_queries

from rooben.extensions.registry import get_extension

def _get_mkt_queries():
    """Load marketplace queries from Pro extension if available."""
    ext = get_extension("pro")
    if ext and hasattr(ext, "get_marketplace_queries"):
        return ext.get_marketplace_queries()
    return None


def run_quality_gates(artifact_type: str, data: dict) -> list:
    """Stub — quality gates not available in OSS."""
    return []


def all_gates_passed(results: list) -> bool:
    """Stub — auto-pass when no gates are configured."""
    return True

router = APIRouter(prefix="/api/community", tags=["community"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CommunityPublishRequest(BaseModel):
    artifact_type: str  # template | integration
    artifact_id: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    category: str = "general"


class FlagRequest(BaseModel):
    reason: str = ""


class RateRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


class UpdatePublicationRequest(BaseModel):
    version: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] | None = None


class BundleCreateRequest(BaseModel):
    title: str
    description: str = ""
    items: list[dict] = Field(default_factory=list)
    sample_output: dict | None = None
    tags: list[str] = Field(default_factory=list)
    category: str = "general"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FLAG_THRESHOLD = 3


async def _get_artifact_data(pool, artifact_type: str, artifact_id: str) -> dict | None:
    """Retrieve artifact data for publishing quality checks."""
    mkt = _get_mkt_queries()
    if artifact_type == "template" and mkt:
        return await mkt.get_template(pool, artifact_id)
    # Integration artifacts — check DB or integration registry
    if artifact_type == "integration":
        row = await pool.fetchrow(
            "SELECT * FROM credentials WHERE integration_name = $1 LIMIT 1",
            artifact_id,
        )
        if row:
            return dict(row)
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/publish")
async def publish_to_community(req: CommunityPublishRequest, request: Request):
    """Publish an artifact to the community. Runs quality gates."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    user_id = get_current_user_id(request)

    # Fetch artifact data for validation
    artifact = await _get_artifact_data(deps.pool, req.artifact_type, req.artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Build data dict for quality gates
    gate_data = {
        "title": req.title or artifact.get("title", ""),
        "description": req.description or artifact.get("description", ""),
        "tags": req.tags or artifact.get("tags", []),
        "spec_yaml": artifact.get("spec_yaml", ""),
        "servers": artifact.get("servers", []),
        "config_yaml": artifact.get("config_yaml", ""),
    }

    gate_results = run_quality_gates(req.artifact_type, gate_data)
    passed = all_gates_passed(gate_results)

    now = datetime.now(timezone.utc) if passed else None
    status = "published" if passed else "pending_review"

    pub_data = {
        "id": uuid.uuid4().hex[:12],
        "artifact_type": req.artifact_type,
        "artifact_id": req.artifact_id,
        "author_id": user_id or "anonymous",
        "author_name": "",
        "status": status,
        "published_at": now,
        "title": gate_data["title"],
        "description": gate_data["description"],
        "tags": gate_data["tags"],
        "category": req.category,
        "automated_checks_passed": passed,
        "review_notes": json.dumps([r.model_dump() for r in gate_results]),
    }

    publication = await comm_queries.create_publication(deps.pool, pub_data)

    return {
        "publication_id": publication["id"],
        "status": status,
        "gate_results": [
            {"gate_name": r.gate_name, "passed": r.passed, "message": r.message, "severity": r.severity}
            for r in gate_results
        ],
    }


@router.get("/browse")
async def browse_community(
    artifact_type: str | None = None,
    category: str | None = None,
    search: str | None = None,
    sort: str = "popular",
    page: int = 1,
    per_page: int = 20,
):
    """Browse published community artifacts."""
    deps = get_deps()
    if not deps.pool:
        return {"publications": [], "total": 0, "page": page, "per_page": per_page}

    publications = await comm_queries.list_publications(
        deps.pool,
        artifact_type=artifact_type,
        category=category,
        search=search,
        sort=sort,
        page=page,
        per_page=per_page,
    )

    total = await comm_queries.count_publications(
        deps.pool,
        artifact_type=artifact_type,
        category=category,
        search=search,
    )

    # Compute rating_avg for each publication
    for p in publications:
        rc = p.get("rating_count", 0)
        p["rating_avg"] = (p.get("rating_sum", 0) / rc) if rc > 0 else 0.0

    return {
        "publications": publications,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/{publication_id}/install")
async def install_community_artifact(publication_id: str, request: Request):
    """Install a community artifact — creates a local copy."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    pub = await comm_queries.get_publication(deps.pool, publication_id)
    if not pub or pub.get("status") != "published":
        raise HTTPException(status_code=404, detail="Publication not found or not published")

    user_id = get_current_user_id(request)
    artifact_type = pub["artifact_type"]

    mkt = _get_mkt_queries()
    if artifact_type == "template" and mkt:
        source = await mkt.get_template(deps.pool, pub["artifact_id"])
        if source:
            install_name = f"{source['name']}-community-{uuid.uuid4().hex[:6]}"
            await mkt.create_template(deps.pool, {
                "id": str(uuid.uuid4()),
                "name": install_name,
                "title": pub.get("title", source.get("title", "")),
                "description": pub.get("description", source.get("description", "")),
                "category": "community",
                "author": pub.get("author_name", ""),
                "tags": pub.get("tags", []),
                "spec_yaml": source.get("spec_yaml", ""),
                "status": "published",
                "owner_id": user_id,
                "installed_from": publication_id,
            })

    elif artifact_type == "bundle" and mkt:
        manifest = pub.get("bundle_manifest")
        if isinstance(manifest, dict):
            for item in manifest.get("items", []):
                if item.get("role") in ("primary", "required"):
                    if item.get("artifact_type") == "template":
                        source = await mkt.get_template(deps.pool, item["artifact_id"])
                        if source:
                            install_name = f"{source['name']}-bundle-{uuid.uuid4().hex[:6]}"
                            await mkt.create_template(deps.pool, {
                                "id": str(uuid.uuid4()),
                                "name": install_name,
                                "title": source.get("title", ""),
                                "description": source.get("description", ""),
                                "category": "community",
                                "author": pub.get("author_name", ""),
                                "tags": pub.get("tags", []),
                                "spec_yaml": source.get("spec_yaml", ""),
                                "status": "published",
                                "owner_id": user_id,
                                "installed_from": publication_id,
                            })

    await comm_queries.increment_install_count(deps.pool, publication_id)

    return {"installed": True, "artifact_type": artifact_type, "publication_id": publication_id}


@router.post("/{publication_id}/flag")
async def flag_artifact(publication_id: str, req: FlagRequest, request: Request):
    """Flag inappropriate content."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    user_id = get_current_user_id(request) or "anonymous"

    flag_count = await comm_queries.create_flag(deps.pool, publication_id, user_id, req.reason)
    if flag_count == 0:
        return {"flagged": False, "message": "Already flagged by this user"}

    # Auto-hide at threshold
    if flag_count >= FLAG_THRESHOLD:
        await comm_queries.update_publication_status(deps.pool, publication_id, "flagged")

    return {"flagged": True, "flag_count": flag_count}


@router.post("/{publication_id}/rate")
async def rate_artifact(publication_id: str, req: RateRequest, request: Request):
    """Rate a community artifact (1-5). One rating per user."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    user_id = get_current_user_id(request) or "anonymous"

    new_avg = await comm_queries.upsert_rating(deps.pool, publication_id, user_id, req.rating)

    return {"rated": True, "new_avg": new_avg}


@router.get("/my")
async def my_publications(request: Request):
    """List current user's community publications grouped by status."""
    deps = get_deps()
    if not deps.pool:
        return {"publications": {}}

    user_id = get_current_user_id(request)
    if not user_id:
        return {"publications": {}}

    grouped = await comm_queries.list_publications_by_author(deps.pool, user_id)
    return {"publications": grouped}


@router.post("/{publication_id}/update")
async def update_publication(publication_id: str, req: UpdatePublicationRequest, request: Request):
    """Update a publication (new version). Re-runs quality gates."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    pub = await comm_queries.get_publication(deps.pool, publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    user_id = get_current_user_id(request)
    if pub.get("author_id") != user_id:
        raise HTTPException(status_code=403, detail="Not the author of this publication")

    # Re-fetch artifact for gate checks
    artifact = await _get_artifact_data(deps.pool, pub["artifact_type"], pub["artifact_id"])
    gate_data = {
        "title": req.title or pub.get("title", ""),
        "description": req.description or pub.get("description", ""),
        "tags": req.tags if req.tags is not None else pub.get("tags", []),
        "spec_yaml": artifact.get("spec_yaml", "") if artifact else "",
        "servers": artifact.get("servers", []) if artifact else [],
        "config_yaml": artifact.get("config_yaml", "") if artifact else "",
    }

    gate_results = run_quality_gates(pub["artifact_type"], gate_data)
    passed = all_gates_passed(gate_results)

    # Update fields
    updates = []
    params = []
    idx = 1
    if req.version:
        updates.append(f"version = ${idx}")
        params.append(req.version)
        idx += 1
    if req.title:
        updates.append(f"title = ${idx}")
        params.append(req.title)
        idx += 1
    if req.description:
        updates.append(f"description = ${idx}")
        params.append(req.description)
        idx += 1
    if req.tags is not None:
        updates.append(f"tags = ${idx}::jsonb")
        params.append(json.dumps(req.tags))
        idx += 1

    updates.append(f"automated_checks_passed = ${idx}")
    params.append(passed)
    idx += 1
    updates.append("updated_at = now()")

    if updates:
        params.append(publication_id)
        await deps.pool.execute(
            f"UPDATE community_publications SET {', '.join(updates)} WHERE id = ${idx}",
            *params,
        )

    return {
        "updated": True,
        "version": req.version or pub.get("version", "1.0.0"),
        "gate_results": [
            {"gate_name": r.gate_name, "passed": r.passed, "message": r.message, "severity": r.severity}
            for r in gate_results
        ],
    }


@router.post("/bundle")
async def create_bundle(req: BundleCreateRequest, request: Request):
    """Create and publish a bundle of artifacts."""
    deps = get_deps()
    if not deps.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    user_id = get_current_user_id(request)

    # Validate all items exist
    for item in req.items:
        artifact = await _get_artifact_data(deps.pool, item.get("artifact_type", ""), item.get("artifact_id", ""))
        if not artifact:
            raise HTTPException(
                status_code=400,
                detail=f"Artifact {item.get('artifact_id')} not found",
            )

    # Run quality gates on the bundle title/description
    gate_data = {
        "title": req.title,
        "description": req.description,
        "tags": req.tags,
    }
    gate_results = run_quality_gates("bundle", gate_data)
    passed = all_gates_passed(gate_results)

    now = datetime.now(timezone.utc) if passed else None
    status = "published" if passed else "pending_review"

    pub_data = {
        "id": uuid.uuid4().hex[:12],
        "artifact_type": "bundle",
        "artifact_id": uuid.uuid4().hex[:12],  # bundle has no separate artifact
        "author_id": user_id or "anonymous",
        "status": status,
        "published_at": now,
        "title": req.title,
        "description": req.description,
        "tags": req.tags,
        "category": req.category,
        "automated_checks_passed": passed,
        "bundle_manifest": {
            "title": req.title,
            "description": req.description,
            "items": req.items,
            "sample_output": req.sample_output,
        },
    }

    publication = await comm_queries.create_publication(deps.pool, pub_data)

    return {
        "publication_id": publication["id"],
        "status": status,
        "gate_results": [
            {"gate_name": r.gate_name, "passed": r.passed, "message": r.message, "severity": r.severity}
            for r in gate_results
        ],
    }
