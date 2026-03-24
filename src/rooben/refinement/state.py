"""State models for the refinement engine."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SchemaGap(BaseModel):
    """A gap in the gathered information relative to the target schema."""
    field_path: str  # e.g. "deliverables[0].name"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str
    resolved: bool = False


class UserProfile(BaseModel):
    """Inferred user characteristics for adaptive questioning."""
    technical_level: str = "unknown"  # beginner | intermediate | advanced
    domain: str = "unknown"
    communication_style: str = "unknown"  # concise | detailed | conversational


class GatheredInfo(BaseModel):
    """Information gathered from the conversation so far."""
    title: str = ""
    goal: str = ""
    deliverables: list[dict] = Field(default_factory=list)
    constraints: list[dict] = Field(default_factory=list)
    acceptance_criteria: list[dict] = Field(default_factory=list)
    agents: list[dict] = Field(default_factory=list)
    input_sources: list[dict] = Field(default_factory=list)  # P17: external data sources
    raw_answers: list[dict] = Field(default_factory=list)  # {question, answer, turn}


class StructuredQuestion(BaseModel):
    """A question with optional enumerated choices."""
    text: str
    choices: list[str] = Field(default_factory=list)  # e.g. ["Docker", "Lambda", "Kubernetes"]
    allow_freeform: bool = True  # Whether user can type a custom answer


class ConversationState(BaseModel):
    """Full state of a refinement conversation."""
    phase: str = "discovery"  # discovery | refinement | review
    completeness: float = 0.0
    gathered_info: GatheredInfo = Field(default_factory=GatheredInfo)
    user_profile: UserProfile = Field(default_factory=UserProfile)
    schema_gaps: list[SchemaGap] = Field(default_factory=list)
    turn_count: int = 0
