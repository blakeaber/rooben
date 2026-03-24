"""Extension manifest schema -- the load-bearing abstraction for Rooben extensions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ExtensionType(str, Enum):
    INTEGRATION = "integration"
    TEMPLATE = "template"
    AGENT = "agent"


class RequiredEnvVar(BaseModel):
    name: str
    description: str = ""
    link: str = ""


class MCPServerEntry(BaseModel):
    name: str
    transport_type: str = "stdio"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None


class ExtensionManifest(BaseModel):
    """Unified rooben-extension.yaml schema for all extension types."""

    # Shared fields
    schema_version: int = 1
    name: str  # kebab-case, unique
    type: ExtensionType
    version: str = "1.0.0"
    author: str = ""
    license: str = "MIT"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    category: str = "professional"
    use_cases: list[str] = Field(default_factory=list)
    min_rooben_version: str = ""

    # Integration-specific
    cost_tier: int = 2
    required_env: list[RequiredEnvVar] = Field(default_factory=list)
    servers: list[MCPServerEntry] = Field(default_factory=list)

    # Template-specific
    prefill: str = ""
    spec_yaml_file: str = ""
    requires: list[str] = Field(default_factory=list)  # integration dependencies
    template_agents: list[dict] = Field(default_factory=list)
    template_workflow_hints: list[dict] = Field(default_factory=list)
    template_input_sources: list[dict] = Field(default_factory=list)
    template_deliverables: list[dict] = Field(default_factory=list)
    template_acceptance_criteria: list[dict] = Field(default_factory=list)

    # Agent-specific
    transport: str = "llm"
    capabilities: list[str] = Field(default_factory=list)
    integration: str = ""  # External integration name (e.g. 'github-issues')
    system_capabilities: dict | None = None  # SystemCapabilities as dict
    model_override: str = ""
    max_concurrency: int = 2
    max_turns: int = 25
    max_context_tokens: int = 200000
    prompt_template: str = ""
    is_default: bool = False


def load_manifest(path) -> ExtensionManifest:
    """Load and validate a rooben-extension.yaml file."""
    from pathlib import Path

    import yaml

    path = Path(path)
    if path.is_dir():
        path = path / "rooben-extension.yaml"

    with open(path) as f:
        data = yaml.safe_load(f)

    return ExtensionManifest.model_validate(data)


def validate_manifest(data: dict) -> tuple[bool, list[str]]:
    """Validate manifest data, returning (valid, errors)."""
    errors = []
    try:
        ExtensionManifest.model_validate(data)
    except Exception as exc:
        errors.append(str(exc))
    return (len(errors) == 0, errors)


def manifest_to_integration_dict(manifest: ExtensionManifest) -> dict:
    """Convert an integration manifest to the dict format used by IntegrationRegistry."""
    return {
        "name": manifest.name,
        "description": manifest.description,
        "domain_tags": manifest.domain_tags,
        "cost_tier": manifest.cost_tier,
        "required_env": [e.name for e in manifest.required_env],
        "source": "extension",
        "author": manifest.author,
        "version": manifest.version,
        "servers": [s.model_dump() for s in manifest.servers],
    }


def manifest_to_agent_preset(manifest: ExtensionManifest) -> dict:
    """Convert an agent manifest to agent preset dict."""
    result = {
        "name": manifest.name,
        "description": manifest.description,
        "integration": manifest.integration,
        "capabilities": manifest.capabilities,
        "model_override": manifest.model_override,
        "max_concurrency": manifest.max_concurrency,
        "max_turns": manifest.max_turns,
        "max_context_tokens": manifest.max_context_tokens,
        "prompt_template": manifest.prompt_template,
        "is_default": manifest.is_default,
        "tags": manifest.tags,
        "domain_tags": manifest.domain_tags,
    }
    if manifest.system_capabilities:
        result["system_capabilities"] = manifest.system_capabilities
    return result
