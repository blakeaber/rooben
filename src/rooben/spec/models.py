"""
Specification models — the meta-programmed PRD schema.

A Specification is the singular input to the orchestration system. It is designed
to be domain-agnostic: it works equally well for producing software, content,
workflows, data pipelines, or any other artifact.

The schema has two layers:
  1. **Structured** — Pydantic-validated fields with types, enums, and constraints.
     These drive machine-readable planning and verification.
  2. **Semi-structured** — Free-text markdown fields (narrative, context, rationale)
     that carry intent an LLM planner can reason over but that don't need to parse
     deterministically.

The key sections mirror a product requirements document:
  - *What* is being built (goal, deliverables)
  - *Why* it matters (context, rationale)
  - *How* success is measured (acceptance criteria, test requirements)
  - *What constraints* apply (budget, time, security, technology)
  - *Who* does the work (agent roster)
  - *Hints* on workflow decomposition (optional; the planner can ignore them)
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DeliverableType(str, Enum):
    """What kind of artifact is expected."""
    CODE = "code"
    DOCUMENT = "document"
    DATASET = "dataset"
    DESIGN = "design"
    WORKFLOW = "workflow"
    APPLICATION = "application"
    API = "api"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


class TestType(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ACCESSIBILITY = "accessibility"
    MANUAL = "manual"


class ConstraintCategory(str, Enum):
    BUDGET = "budget"
    TIME = "time"
    TECHNOLOGY = "technology"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    OTHER = "other"


class AgentTransport(str, Enum):
    LLM = "llm"
    SUBPROCESS = "subprocess"
    HTTP = "http"
    MCP = "mcp"


class MCPTransportType(str, Enum):
    """How to connect to an MCP server."""
    STDIO = "stdio"
    SSE = "sse"


class InputSourceType(str, Enum):
    """Type of external data source."""
    MCP = "mcp"
    FILE = "file"
    URL = "url"


class InputSource(BaseModel):
    """Declares an external data source a workflow needs."""
    name: str = Field(..., description="Unique name for this input source")
    type: InputSourceType = Field(
        default=InputSourceType.MCP,
        description="Source type: mcp (integration), file, or url",
    )
    integration: str | None = Field(
        default=None,
        description="Integration name (required for type='mcp'), e.g. 'slack', 'salesforce'",
    )
    description: str = Field(default="", description="What data this source provides")
    query: dict[str, Any] = Field(
        default_factory=dict,
        description="Integration-specific query parameters",
    )
    required: bool = Field(
        default=True,
        description="If true, workflow fails when this source is unavailable",
    )
    pre_fetch: bool = Field(
        default=True,
        description="If true, data is loaded before execution; otherwise agents query at runtime",
    )

    @model_validator(mode="after")
    def _mcp_requires_integration(self) -> InputSource:
        if self.type == InputSourceType.MCP and not self.integration:
            raise ValueError("InputSource with type='mcp' requires 'integration' field")
        return self


class MCPServerConfig(BaseModel):
    """Configuration for connecting to an MCP server that exposes tools."""
    name: str = Field(..., description="Unique name for this MCP server")
    transport_type: MCPTransportType = MCPTransportType.STDIO
    command: str | None = Field(
        default=None,
        description="For stdio transport: the command to launch the MCP server process",
    )
    args: list[str] = Field(
        default_factory=list,
        description="For stdio transport: arguments to pass to the command",
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set for the MCP server process",
    )
    url: str | None = Field(
        default=None,
        description="For SSE transport: the server endpoint URL",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers for SSE transport (e.g. credential injection)",
    )


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class AcceptanceCriterion(BaseModel):
    """A single, testable statement of 'done'."""
    id: str = Field(..., description="Unique identifier, e.g. AC-001")
    description: str = Field(..., description="Plain-language criterion")
    verification: str = Field(
        default="llm_judge",
        description="How to verify: 'llm_judge', 'test', 'manual', or a custom verifier name",
    )
    priority: Priority = Priority.HIGH


class TestRequirement(BaseModel):
    """A test that must pass before the specification is considered satisfied."""
    id: str
    description: str
    test_type: TestType
    target_deliverable: str | None = Field(
        default=None, description="Which deliverable this test applies to"
    )
    skeleton: str | None = Field(
        default=None,
        description=(
            "Optional skeleton test code. If provided, the agent must implement "
            "this test and ensure it passes. Supports pytest, Playwright, etc."
        ),
    )


class SuccessCriteria(BaseModel):
    """Aggregated success definition."""
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    test_requirements: list[TestRequirement] = Field(default_factory=list)
    completion_threshold: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of acceptance criteria that must pass for the spec to be "
            "considered complete. 1.0 = all must pass."
        ),
    )


class Constraint(BaseModel):
    """An operational or technical constraint the system must respect."""
    id: str
    category: ConstraintCategory
    description: str
    hard: bool = Field(
        default=True,
        description="Hard constraints cause failure; soft constraints are best-effort.",
    )


class Deliverable(BaseModel):
    """A concrete output artifact."""
    id: str
    name: str
    deliverable_type: DeliverableType
    description: str
    output_path: str | None = Field(
        default=None, description="Where the artifact should be written (file, URL, etc.)"
    )
    acceptance_criteria_ids: list[str] = Field(
        default_factory=list,
        description="Which acceptance criteria apply to this deliverable",
    )


class ShellCapability(BaseModel):
    """Declares shell/command execution for an agent."""
    enabled: bool = True
    scope: str = Field(default="workspace", description="'workspace' limits to workspace_dir")


class MemoryCapability(BaseModel):
    """Declares persistent memory/knowledge-graph access for an agent."""
    enabled: bool = True


class FetchCapability(BaseModel):
    """Declares web fetch (HTTP read) capability for an agent."""
    enabled: bool = True


class SystemCapabilities(BaseModel):
    """Declarative system-level capabilities for an agent.

    These map directly to MCP servers provided by the runtime (filesystem, shell,
    memory, fetch). Unlike external integrations (GitHub, Slack, etc.), system
    capabilities don't require credentials and are always available.
    """
    shell: ShellCapability | None = None
    memory: MemoryCapability | None = None
    fetch: FetchCapability | None = None


class AgentSpec(BaseModel):
    """Describes an agent available to the orchestrator."""

    id: str
    name: str
    transport: AgentTransport
    description: str = Field(..., description="What this agent is good at")
    endpoint: str = Field(
        default="",
        description=(
            "For HTTP agents: the base URL. "
            "For subprocess agents: dotted Python path to callable. "
            "For MCP agents: leave empty (servers defined in mcp_servers)."
        ),
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Tags describing what this agent can do, e.g. ['python', 'testing', 'frontend']",
    )
    max_concurrency: int = Field(default=1, ge=1, description="Max parallel tasks for this agent")
    max_turns: int = Field(
        default=40, ge=1,
        description=(
            "Max agentic loop turns for this agent. Default 40."
        ),
    )
    max_context_tokens: int = Field(
        default=200000, ge=1,
        description="Max context window for this agent (used for prompt budget).",
    )
    budget: AgentBudget | None = None
    mcp_servers: list[MCPServerConfig] = Field(
        default_factory=list,
        description=(
            "MCP servers this agent can connect to for tool access. "
            "Required for MCP transport agents; optional for other transports."
        ),
    )
    integrations: list[str] = Field(
        default_factory=list,
        description="External integration names (e.g. ['brave-search', 'google-drive']). Max 3.",
    )
    model: str | None = Field(
        default=None,
        description="LLM model override. Uses workflow default when None.",
    )
    system_capabilities: SystemCapabilities | None = Field(
        default=None,
        description=(
            "Declarative system capabilities (filesystem, shell, memory, fetch). "
            "When set, these are resolved to MCP servers automatically."
        ),
    )

    @field_validator("integrations")
    @classmethod
    def _cap_integrations(cls, v: list[str]) -> list[str]:
        if len(v) > 3:
            raise ValueError(
                f"Agent declares {len(v)} integrations (max 3). "
                "Split into focused agents to keep scope narrow."
            )
        return v

    @field_validator("endpoint")
    @classmethod
    def _validate_endpoint(cls, v: str, info: Any) -> str:
        transport = info.data.get("transport")
        if transport == AgentTransport.HTTP:
            if not v.startswith(("http://", "https://")):
                raise ValueError("HTTP agent endpoint must start with http:// or https://")
        return v


class AgentBudget(BaseModel):
    """Resource limits for a single agent."""
    max_tokens: int | None = Field(default=None, ge=1)
    max_tasks: int | None = Field(default=None, ge=1)
    max_wall_seconds: int | None = Field(default=None, ge=1)
    max_retries_per_task: int = Field(default=3, ge=0)


class WorkflowHint(BaseModel):
    """Optional decomposition hint the planner may use or ignore."""
    name: str
    description: str
    suggested_agent_id: str | None = None
    depends_on: list[str] = Field(
        default_factory=list,
        description="Names of other workflow hints this should follow",
    )


# ---------------------------------------------------------------------------
# Top-level Specification
# ---------------------------------------------------------------------------

class Specification(BaseModel):
    """
    The top-level input contract.

    Structured fields are validated by Pydantic. Semi-structured fields (marked
    with `# semi-structured`) carry markdown prose the LLM planner reasons over.
    """

    # -- Identity --
    id: str = Field(..., description="Unique spec identifier")
    version: str = Field(default="1.0.0")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # -- Semi-structured: the "why" and "what" narrative --
    title: str = Field(..., max_length=200)
    goal: str = Field(
        ...,
        description=(
            "High-level goal in plain language. This is the north-star the planner "
            "decomposes into workstreams."
        ),
    )
    context: str = Field(
        default="",
        description="Background, motivation, prior art — anything the planner needs to understand.",
    )
    rationale: str = Field(
        default="",
        description="Why this approach was chosen over alternatives.",
    )

    # -- Structured: what gets built --
    deliverables: list[Deliverable] = Field(
        ..., min_length=1, description="At least one concrete output is required."
    )

    # -- Structured: how success is measured --
    success_criteria: SuccessCriteria = Field(default_factory=SuccessCriteria)

    # -- Structured: constraints --
    constraints: list[Constraint] = Field(default_factory=list)

    # -- Structured: agent roster --
    agents: list[AgentSpec] = Field(
        ..., min_length=1, description="At least one agent must be available."
    )

    # -- Semi-structured: workflow hints --
    workflow_hints: list[WorkflowHint] = Field(default_factory=list)

    # -- Structured: external data sources (P17) --
    input_sources: list[InputSource] = Field(
        default_factory=list,
        description="External data sources this workflow needs (optional).",
    )

    # -- Semi-structured: additional notes --
    notes: str = Field(default="", description="Anything else the planner should know.")

    # -- Structured: global budget --
    global_budget: GlobalBudget | None = None

    # -- Runtime: workspace directory (set by CLI / API, not in YAML) --
    workspace_dir: str | None = Field(default=None, exclude=True)

    def content_hash(self) -> str:
        """Deterministic hash of the spec content for dedup / caching."""
        payload = self.model_dump_json(exclude={"created_at"})
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @field_validator("deliverables")
    @classmethod
    def _check_deliverable_ids_unique(cls, v: list[Deliverable]) -> list[Deliverable]:
        ids = [d.id for d in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Deliverable IDs must be unique")
        return v

    @field_validator("agents")
    @classmethod
    def _check_agent_ids_unique(cls, v: list[AgentSpec]) -> list[AgentSpec]:
        ids = [a.id for a in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Agent IDs must be unique")
        return v


class GlobalBudget(BaseModel):
    """System-wide resource limits."""
    max_total_tokens: int | None = Field(default=None, ge=1)
    max_total_tasks: int | None = Field(default=None, ge=1)
    max_wall_seconds: int | None = Field(default=None, ge=1)
    max_concurrent_agents: int = Field(default=5, ge=1)
