"""State models for the extension builder engine."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtensionGap(BaseModel):
    """A gap in the gathered information for building an extension."""
    field_path: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str
    resolved: bool = False


class ExtensionGatheredInfo(BaseModel):
    """Information gathered during extension building."""
    # Common fields
    name: str = ""
    type: str = ""  # integration | template | agent
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    category: str = ""  # professional | builder | automator
    use_cases: list[str] = Field(default_factory=list)

    # Integration-specific
    servers: list[dict] = Field(default_factory=list)
    required_env: list[dict] = Field(default_factory=list)
    cost_tier: int = 2

    # Template-specific
    prefill: str = ""
    requires: list[str] = Field(default_factory=list)

    # Agent-specific
    capabilities: list[str] = Field(default_factory=list)
    prompt_template: str = ""
    model_override: str = ""
    integration: str = ""

    # Tracking
    raw_answers: list[dict] = Field(default_factory=list)


class ExtensionBuilderQuestion(BaseModel):
    """A question with optional choices for the builder flow."""
    text: str
    choices: list[str] = Field(default_factory=list)
    allow_freeform: bool = True


class ExtensionBuilderState(BaseModel):
    """Full state of an extension builder conversation."""
    phase: str = "discovery"  # discovery | refinement | review
    completeness: float = 0.0
    gathered_info: ExtensionGatheredInfo = Field(default_factory=ExtensionGatheredInfo)
    gaps: list[ExtensionGap] = Field(default_factory=list)
    turn_count: int = 0
    detected_type: str = ""  # Auto-detected extension type
