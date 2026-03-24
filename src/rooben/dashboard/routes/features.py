"""Feature detection endpoint — reports which edition is running."""

from __future__ import annotations

from fastapi import APIRouter

from rooben.extensions.registry import has_extension

router = APIRouter(tags=["features"])


@router.get("/api/features")
async def get_features():
    """Return the active edition and available feature flags."""
    edition = "pro" if has_extension("pro") else "oss"
    capabilities = {
        "export_files": True,  # File listing + ZIP always available
    }
    return {"edition": edition, "capabilities": capabilities}
