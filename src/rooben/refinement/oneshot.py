"""One-shot spec generation — natural language to Specification in a single LLM call."""

from __future__ import annotations


import structlog

from rooben.planning.provider import LLMProvider
from rooben.refinement.spec_builder import SpecBuilder
from rooben.refinement.state import GatheredInfo
from rooben.spec.models import AgentSpec, AgentTransport, Specification, WorkflowHint
from rooben.utils import parse_llm_json

log = structlog.get_logger()

ONESHOT_PROMPT = """\
You are a project specification architect. Given a natural language description,
generate a complete, well-structured project specification as a single JSON object.

## User's Description
{description}

## Your Task
Produce a thorough, production-quality project specification. Be specific and actionable —
avoid vague language like "system should work" or "proper implementation".

### Agent Transport & System Capabilities Rules
- Use transport "mcp" for agents that need external tools (file I/O, shell, web search)
- Use transport "llm" for agents that only need reasoning (research, writing, editing, analysis)
- Include accurate "capabilities" tags (e.g. ["research", "analysis"] for a researcher, ["python", "api", "testing"] for a developer)
- Non-coding workflows (research, legal, strategy, writing) should NOT default to coding tools
- Specify "system_capabilities" to declare what system tools each agent needs:
  - filesystem: {{enabled: true, mode: "readwrite"}} — for agents that read/write files
  - shell: {{enabled: true}} — for agents that run commands (always include filesystem too)
  - fetch: {{enabled: true}} — for agents that need to read web pages
  - memory: {{enabled: true}} — for agents that need persistent knowledge storage
  - Omit capabilities the agent doesn't need (pure reasoning agents need none)

### Quality Standards
- Acceptance criteria must be specific and testable (e.g., "GET /hello returns 200 with \
JSON body {{"message": "Hello, World!"}}" not "API works correctly")
- Deliverables should include output_path suggestions (e.g., "output/src/main.py")
- Each deliverable should reference its acceptance criteria by ID
- Workflow hints must form a dependency chain (later steps depend_on earlier ones)
- Each workflow hint should reference a suggested_agent_id from the agents list
- Agents should have meaningful capabilities lists that match deliverable types

### Output Format
Return a JSON object with this exact structure:
{{
  "title": "Short project title",
  "goal": "Clear, actionable goal statement (1-3 sentences)",
  "context": "Background and motivation",
  "rationale": "Why this approach makes sense",
  "deliverables": [
    {{
      "id": "D-001",
      "name": "Deliverable name",
      "description": "What this deliverable is and what it contains",
      "deliverable_type": "code|document|dataset|design|api|infrastructure|other",
      "output_path": "output/path/to/artifact",
      "acceptance_criteria_ids": ["AC-001", "AC-002"]
    }}
  ],
  "constraints": [
    {{
      "category": "budget|time|technology|security|compliance|performance|compatibility|other",
      "description": "Constraint description",
      "hard": true
    }}
  ],
  "acceptance_criteria": [
    {{
      "id": "AC-001",
      "description": "Specific, testable success criterion",
      "verification": "llm_judge|test|manual",
      "priority": "critical|high|medium|low"
    }}
  ],
  "agents": [
    {{
      "id": "agent-id",
      "name": "Agent Name",
      "transport": "mcp",
      "description": "What this agent specializes in",
      "capabilities": ["python", "testing", "api"],
      "system_capabilities": {{
        "filesystem": {{"enabled": true, "mode": "readwrite"}},
        "shell": {{"enabled": true}}
      }},
      "max_concurrency": 2
    }}
  ],
  "workflow_hints": [
    {{
      "name": "Task or phase name",
      "description": "What this step accomplishes",
      "suggested_agent_id": "agent-id",
      "depends_on": ["name of prerequisite step, if any"]
    }}
  ],
  "domain": "software|legal|research|marketing|data-science|operations|content|general",
  "notes": "Any additional context or implementation notes"
}}

### Example Quality Bar
For a "Build a REST API" description (domain: "software"), the spec should look like:
- Deliverables: API Application (output/src/main.py), Test Suite (output/tests/), Dockerfile
- Acceptance criteria: "GET /endpoint returns 200 with JSON body {{"key": "value"}}" (not "API returns correct responses")
- Agents: "Python Developer" with capabilities ["python", "fastapi", "api"], "Test Engineer" with ["python", "testing", "pytest"]
- Workflow hints: "API Implementation" → "Test Suite" (depends_on: ["API Implementation"]) → "Documentation" (depends_on: ["API Implementation"])

For a "Draft a competitive analysis of Stripe vs Square" description (domain: "research"), the spec should look like:
- Deliverables: Competitive Analysis Report (output/competitive-analysis.md), Executive Summary (output/executive-summary.md)
- Acceptance criteria: "Report includes pricing comparison across 3+ transaction volume tiers" (not "Report is comprehensive")
- Agents: "Research Analyst" with capabilities ["research", "analysis", "writing"], "Editor" with capabilities ["writing", "editing", "review"]
- Workflow hints: "Market Research" → "Pricing Analysis" (depends_on: ["Market Research"]) → "Report Drafting" (depends_on: ["Market Research", "Pricing Analysis"])

Generate 2-4 deliverables, 3-5 acceptance criteria, 2-3 agents, and 3-5 workflow hints with dependency chains.
Output ONLY the JSON object.
"""


async def generate_spec_oneshot(
    provider: LLMProvider,
    description: str,
    workspace_dir: str | None = None,
) -> "Specification":
    """Generate a complete Specification from a natural language description in one LLM call.

    Args:
        provider: LLM provider for generation.
        description: Natural language project description.
        workspace_dir: If provided, agents get MCP filesystem/shell servers scoped to this dir.
    """

    prompt = ONESHOT_PROMPT.format(description=description)

    gen_result = await provider.generate(
        system="You are a project specification architect. You produce thorough, "
               "well-structured project specifications from natural language descriptions. "
               "Match agent transport to task needs: 'mcp' for tool-using agents, 'llm' for reasoning-only agents.",
        prompt=prompt,
        max_tokens=4096,
    )

    data = parse_llm_json(gen_result.text)
    if not data:
        raise ValueError("Failed to parse spec from LLM response")

    # Extract domain for capability enrichment (R-6.2: domain detection)
    domain = data.get("domain", "general")

    # Build agents directly from the LLM output (integration registry assigns tools later)
    agents = _parse_agents(data.get("agents", []), domain=domain)
    if not agents:
        # Minimal fallback — single agent; integration registry assigns tools based on capabilities
        caps = _infer_capabilities(description)
        if not caps or caps == ["analysis", "reasoning", "general"]:
            caps = _domain_to_capabilities(domain)
        agents = [
            AgentSpec(
                id="agent-general",
                name="General Agent",
                transport=AgentTransport.LLM,
                description="General-purpose agent",
                capabilities=caps,
                max_concurrency=2,
            )
        ]

    # Build GatheredInfo for SpecBuilder
    gathered = GatheredInfo(
        title=data.get("title", "Untitled Project"),
        goal=data.get("goal", description),
        deliverables=data.get("deliverables", []),
        constraints=data.get("constraints", []),
        acceptance_criteria=data.get("acceptance_criteria", []),
    )

    # Build validated spec
    builder = SpecBuilder()
    spec = builder.build(gathered, agents)

    # Enrich with additional fields from the LLM
    if data.get("context"):
        spec.context = data["context"]
    if data.get("rationale"):
        spec.rationale = data["rationale"]
    if data.get("notes"):
        spec.notes = data["notes"]

    # Add workflow hints with agent cross-references
    agent_ids = {a.id for a in agents}
    for hint in data.get("workflow_hints", []):
        try:
            suggested = hint.get("suggested_agent_id")
            if suggested and suggested not in agent_ids:
                suggested = None  # Drop invalid references
            spec.workflow_hints.append(WorkflowHint(
                name=hint.get("name", ""),
                description=hint.get("description", ""),
                suggested_agent_id=suggested,
                depends_on=hint.get("depends_on", []),
            ))
        except Exception:
            continue

    log.info(
        "oneshot.spec_generated",
        title=spec.title,
        deliverables=len(spec.deliverables),
        agents=len(spec.agents),
        criteria=len(spec.success_criteria.acceptance_criteria),
        workflow_hints=len(spec.workflow_hints),
    )

    return spec


def _parse_agents(agent_data: list[dict], domain: str = "general") -> list[AgentSpec]:
    """Parse agent dicts from LLM output. System capabilities are explicit."""
    agents = []
    for a in agent_data:
        try:
            # Normalize transport — accept what LLM provides, default to llm
            if a.get("transport") not in ("mcp", "llm", "http", "subprocess"):
                a["transport"] = "llm"
            a["endpoint"] = ""
            # Strip any MCP servers the LLM may have hallucinated
            a.pop("mcp_servers", None)
            # Enrich empty capabilities from domain (R-6.2)
            if not a.get("capabilities"):
                a["capabilities"] = _domain_to_capabilities(domain)
            # Infer system_capabilities from domain if not provided by LLM
            if not a.get("system_capabilities"):
                a["system_capabilities"] = _domain_to_system_capabilities(domain)
            agents.append(AgentSpec.model_validate(a))
        except Exception:
            continue
    return agents


_DOMAIN_TO_CAPABILITIES: dict[str, list[str]] = {
    "software": ["python", "code", "testing"],
    "legal": ["legal", "writing", "compliance"],
    "research": ["research", "analysis", "writing"],
    "marketing": ["marketing", "writing", "design"],
    "data-science": ["python", "data", "analytics"],
    "operations": ["operations", "analysis", "writing"],
    "content": ["writing", "editing", "content"],
    "general": ["analysis", "reasoning", "general"],
}


def _domain_to_capabilities(domain: str) -> list[str]:
    """Map a domain string to default agent capabilities."""
    return _DOMAIN_TO_CAPABILITIES.get(domain, _DOMAIN_TO_CAPABILITIES["general"])


_DOMAIN_TO_SYSTEM_CAPABILITIES: dict[str, dict | None] = {
    "software": {
        "filesystem": {"enabled": True, "mode": "readwrite"},
        "shell": {"enabled": True},
    },
    "data-science": {
        "filesystem": {"enabled": True, "mode": "readwrite"},
        "shell": {"enabled": True},
    },
    "research": {
        "fetch": {"enabled": True},
    },
    "legal": {
        "filesystem": {"enabled": True, "mode": "readwrite"},
    },
    "marketing": {
        "filesystem": {"enabled": True, "mode": "readwrite"},
    },
    "operations": {
        "filesystem": {"enabled": True, "mode": "readwrite"},
    },
    "content": {
        "filesystem": {"enabled": True, "mode": "readwrite"},
    },
    "general": None,
}


def _domain_to_system_capabilities(domain: str) -> dict | None:
    """Map a domain string to default system capabilities."""
    return _DOMAIN_TO_SYSTEM_CAPABILITIES.get(domain, _DOMAIN_TO_SYSTEM_CAPABILITIES["general"])


_KEYWORD_TO_CAPABILITIES: dict[str, list[str]] = {
    "api": ["python", "api", "backend"],
    "rest": ["python", "api", "backend"],
    "frontend": ["javascript", "react", "frontend"],
    "react": ["javascript", "react", "frontend"],
    "data": ["python", "data", "analytics"],
    "pipeline": ["python", "data", "etl"],
    "research": ["research", "analysis", "writing"],
    "report": ["research", "analysis", "writing"],
    "legal": ["legal", "writing", "compliance"],
    "strategy": ["strategy", "analysis", "writing"],
    "marketing": ["marketing", "writing", "design"],
}


def _infer_capabilities(description: str) -> list[str]:
    """Infer agent capabilities from a description string."""
    desc_lower = description.lower()
    caps: set[str] = set()
    for keyword, keyword_caps in _KEYWORD_TO_CAPABILITIES.items():
        if keyword in desc_lower:
            caps.update(keyword_caps)
    return list(caps) if caps else ["analysis", "reasoning", "general"]
