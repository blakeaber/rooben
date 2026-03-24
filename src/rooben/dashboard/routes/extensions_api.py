"""Extensions API — list, filter, install, and query extensions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/extensions", tags=["extensions"])


class InstallRequest(BaseModel):
    name: str


@router.get("")
async def list_extensions(type: str | None = None):
    """List all available extensions, optionally filtered by type."""
    from rooben.extensions.loader import load_all_extensions

    manifests = load_all_extensions()
    if type:
        manifests = [m for m in manifests if m.type.value == type]

    from rooben.extensions.installer import is_installed

    items = []
    for m in manifests:
        items.append({
            "name": m.name,
            "type": m.type.value,
            "version": m.version,
            "author": m.author,
            "description": m.description,
            "tags": m.tags,
            "domain_tags": m.domain_tags,
            "category": m.category,
            "use_cases": m.use_cases,
            "installed": is_installed(m.name),
            # Type-specific fields
            **({"cost_tier": m.cost_tier, "required_env": [e.model_dump() for e in m.required_env]} if m.type.value == "integration" else {}),
            **({"prefill": m.prefill, "requires": m.requires} if m.type.value == "template" else {}),
            **({"capabilities": m.capabilities, "integration": m.integration, "model_override": m.model_override, "prompt_template": m.prompt_template[:200] if m.prompt_template else ""} if m.type.value == "agent" else {}),
        })

    return {"extensions": items, "total": len(items)}


@router.get("/templates")
async def list_template_extensions():
    """List template extensions for workflow creation."""
    from rooben.extensions.loader import load_all_extensions
    from rooben.extensions.manifest import ExtensionType

    manifests = [m for m in load_all_extensions() if m.type == ExtensionType.TEMPLATE]
    return {
        "templates": [
            {
                "name": m.name,
                "description": m.description,
                "prefill": m.prefill,
                "tags": m.tags,
                "domain_tags": m.domain_tags,
                "category": m.category,
                "requires": m.requires,
                "author": m.author,
                "version": m.version,
            }
            for m in manifests
        ]
    }


@router.get("/agents")
async def list_agent_extensions():
    """List agent extension presets."""
    from rooben.extensions.loader import load_all_extensions
    from rooben.extensions.manifest import ExtensionType, manifest_to_agent_preset

    manifests = [m for m in load_all_extensions() if m.type == ExtensionType.AGENT]
    return {
        "agents": [manifest_to_agent_preset(m) for m in manifests]
    }


@router.get("/{name}/status")
async def extension_status(name: str):
    """Check readiness status for any extension type."""
    from rooben.extensions.loader import validate_extension_readiness

    return validate_extension_readiness(name)


@router.get("/{name}")
async def get_extension_detail(name: str):
    """Get full metadata for any extension type, including readiness status."""
    from rooben.extensions.installer import is_installed
    from rooben.extensions.loader import load_all_extensions, validate_extension_readiness
    from rooben.extensions.manifest import ExtensionType, manifest_to_agent_preset

    manifests = load_all_extensions()
    manifest = next((m for m in manifests if m.name == name), None)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Extension '{name}' not found")

    readiness = validate_extension_readiness(name)

    detail: dict = {
        "name": manifest.name,
        "type": manifest.type.value,
        "version": manifest.version,
        "author": manifest.author,
        "license": manifest.license,
        "description": manifest.description,
        "tags": manifest.tags,
        "domain_tags": manifest.domain_tags,
        "category": manifest.category,
        "use_cases": manifest.use_cases,
        "installed": is_installed(manifest.name),
        "ready": readiness["ready"],
        "checks": readiness["checks"],
    }

    if manifest.type == ExtensionType.INTEGRATION:
        detail["cost_tier"] = manifest.cost_tier
        detail["required_env"] = [e.model_dump() for e in manifest.required_env]
        detail["servers"] = [s.model_dump() for s in manifest.servers]
    elif manifest.type == ExtensionType.TEMPLATE:
        detail["prefill"] = manifest.prefill
        detail["requires"] = manifest.requires
        detail["template_agents"] = manifest.template_agents
        detail["template_workflow_hints"] = manifest.template_workflow_hints
        detail["template_input_sources"] = manifest.template_input_sources
        detail["template_deliverables"] = manifest.template_deliverables
        detail["template_acceptance_criteria"] = manifest.template_acceptance_criteria
        # Include the raw YAML manifest so the refinement engine can use it
        try:
            from rooben.extensions.installer import find_extension_source
            from pathlib import Path

            source_dir = find_extension_source(name)
            if source_dir:
                yaml_path = Path(source_dir) / "rooben-extension.yaml"
                if yaml_path.exists():
                    detail["spec_yaml"] = yaml_path.read_text()
        except Exception:
            detail["spec_yaml"] = ""
    elif manifest.type == ExtensionType.AGENT:
        detail.update(manifest_to_agent_preset(manifest))

    return detail


@router.post("/install")
async def install_extension(req: InstallRequest):
    """Install an extension by name."""
    from rooben.extensions.installer import install_extension as do_install

    try:
        path = do_install(req.name)
        return {"installed": True, "name": req.name, "path": str(path)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Extension '{req.name}' not found")
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Extension '{req.name}' is already installed")


@router.post("/uninstall")
async def uninstall_extension(req: InstallRequest):
    """Uninstall an extension by name."""
    from rooben.extensions.installer import uninstall_extension as do_uninstall

    try:
        do_uninstall(req.name)
        return {"uninstalled": True, "name": req.name}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Extension '{req.name}' is not installed")
