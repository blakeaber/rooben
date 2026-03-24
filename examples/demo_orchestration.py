#!/usr/bin/env python3
"""
Rooben Feature Demo — Runnable demonstration of every major framework feature.

Run this script directly (no API key required):

    python examples/demo_orchestration.py

This script demonstrates:
  1. Building specifications programmatically (Pydantic models)
  2. LLM planning (spec → workstream/task DAG decomposition)
  3. Full orchestration (concurrent dispatch, dependency ordering)
  4. MCP agent integration (tool-calling agentic loop)
  5. Budget enforcement (token/task limits)
  6. Output sanitization (automatic credential redaction)
  7. State inspection (reading workflow results after execution)

Every call uses mock providers so nothing hits a real API.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from typing import Any

# ============================================================================
# STEP 0: Imports — the key modules you'll use from rooben
# ============================================================================

from rooben.agents.llm_agent import LLMAgent
from rooben.agents.mcp_agent import MCPAgent
from rooben.agents.mcp_client import MCPClient, MCPToolInfo
from rooben.agents.registry import AgentRegistry
from rooben.domain import (
    Task,
    TaskResult,
    TaskStatus,
    WorkflowState,
    WorkflowStatus,
)
from rooben.planning.provider import GenerationResult
from rooben.orchestrator import Orchestrator
from rooben.planning.llm_planner import LLMPlanner
from rooben.security.budget import BudgetExceeded, BudgetTracker
from rooben.security.sanitizer import OutputSanitizer
from rooben.spec.loader import load_spec
from rooben.spec.models import (
    AcceptanceCriterion,
    AgentBudget,
    AgentSpec,
    AgentTransport,
    Constraint,
    ConstraintCategory,
    Deliverable,
    DeliverableType,
    GlobalBudget,
    MCPServerConfig,
    MCPTransportType,
    Specification,
    SuccessCriteria,
    TestRequirement,
    TestType,
    WorkflowHint,
)
from rooben.state.filesystem import FilesystemBackend
from rooben.verification.llm_judge import LLMJudgeVerifier


# ============================================================================
# MOCK PROVIDERS — Deterministic replacements for real LLM calls
# ============================================================================


class DemoLLMProvider:
    """
    Mock LLM provider that returns predetermined responses.

    The real AnthropicProvider calls Claude's API. This mock routes requests
    based on the system prompt content to return the right kind of response:
      - Planning requests → workstream/task DAG JSON
      - Agent execution → task output with artifacts
      - Verification → pass/fail judgment
      - MCP tool orchestration → tool calls then final result
    """

    def __init__(self) -> None:
        self.call_log: list[dict[str, str]] = []
        self._agent_call_count = 0

    def _wrap(self, text: str) -> GenerationResult:
        """Wrap a raw string in a GenerationResult for API compatibility."""
        return GenerationResult(text=text, model="demo-mock", provider="demo")

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
        self.call_log.append({"system": system[:100], "prompt": prompt[:100]})
        sys_lower = system.lower()

        # ── Planning request ──
        # The LLMPlanner sends a system prompt containing "planning engine".
        # It expects back a JSON with workstreams and tasks.
        if "planning engine" in sys_lower:
            return self._wrap(self._planning_response(prompt))

        # ── Verification (LLM Judge) request ──
        # The LLMJudgeVerifier sends "quality assurance judge" in its prompt.
        # It expects back JSON with passed, score, feedback.
        if "quality assurance judge" in sys_lower:
            return self._wrap(json.dumps({
                "passed": True,
                "score": 0.95,
                "feedback": "Output meets all acceptance criteria.",
            }))

        # ── MCP Agent request ──
        # The MCPAgent sends "available tools" or "no tools" in its prompt.
        # IMPORTANT: Check this BEFORE "autonomous agent" since the MCP
        # system prompt also contains "autonomous agent" in its first line.
        if "available tools" in sys_lower or "how to call tools" in sys_lower:
            return self._wrap(self._mcp_agent_response(prompt))
        if "no tools are currently available" in sys_lower:
            return self._wrap(self._mcp_agent_response(prompt))

        # ── Agent execution request ──
        # The LLMAgent sends "autonomous agent executing" in its system prompt.
        # It expects back JSON with output, artifacts, generated_tests.
        if "autonomous agent executing" in sys_lower:
            self._agent_call_count += 1
            return self._wrap(self._agent_response(prompt))

        return self._wrap(json.dumps({"output": "ok"}))

    def _planning_response(self, prompt: str) -> str:
        """
        Return a multi-workstream plan with dependencies.

        This simulates what the LLM planner produces: a DAG of tasks
        organized into workstreams, with explicit dependency edges.
        """
        return json.dumps({
            "workstreams": [
                {
                    "id": "ws-backend",
                    "name": "Backend Services",
                    "description": "Core API and data layer",
                    "tasks": [
                        {
                            # Task 1: No dependencies — will run first
                            "id": "task-models",
                            "title": "Define Data Models",
                            "description": "Create Pydantic models for User, Session, and Token",
                            "assigned_agent_id": "agent-backend",
                            "depends_on": [],
                            "acceptance_criteria_ids": ["AC-001"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                        {
                            # Task 2: Depends on models — will run after task 1
                            "id": "task-api",
                            "title": "Build REST API",
                            "description": "Implement FastAPI endpoints using the data models",
                            "assigned_agent_id": "agent-backend",
                            "depends_on": ["task-models"],
                            "acceptance_criteria_ids": ["AC-001", "AC-002"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-frontend",
                    "name": "Frontend",
                    "description": "Web UI components",
                    "tasks": [
                        {
                            # Task 3: No dependencies — runs in PARALLEL with task 1
                            "id": "task-ui",
                            "title": "Build Dashboard UI",
                            "description": "Create React dashboard with charts and tables",
                            "assigned_agent_id": "agent-frontend",
                            "depends_on": [],
                            "acceptance_criteria_ids": ["AC-003"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-testing",
                    "name": "Testing",
                    "description": "Integration tests",
                    "tasks": [
                        {
                            # Task 4: Depends on API + UI — fan-in join point
                            "id": "task-integration",
                            "title": "Write Integration Tests",
                            "description": "E2E tests that verify API ↔ UI integration",
                            "assigned_agent_id": "agent-testing",
                            "depends_on": ["task-api", "task-ui"],
                            "acceptance_criteria_ids": ["AC-004"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                    ],
                },
            ]
        })

    def _agent_response(self, prompt: str) -> str:
        """
        Return agent output with artifacts.

        Real agents produce code, documents, configs, etc. as artifacts.
        The artifacts dict maps filename → content.
        """
        if "Data Models" in prompt or "models" in prompt.lower():
            return json.dumps({
                "output": "Created User, Session, and Token Pydantic models",
                "artifacts": {
                    "models.py": (
                        "from pydantic import BaseModel\n\n"
                        "class User(BaseModel):\n"
                        "    id: int\n"
                        "    name: str\n"
                        "    email: str\n\n"
                        "class Session(BaseModel):\n"
                        "    user_id: int\n"
                        "    token: str\n"
                        "    expires_at: str\n"
                    ),
                },
                "generated_tests": [
                    {
                        "filename": "test_models.py",
                        "content": (
                            "from models import User\n\n"
                            "def test_user_creation():\n"
                            "    user = User(id=1, name='Alice', email='a@b.com')\n"
                            "    assert user.name == 'Alice'\n"
                        ),
                        "test_type": "unit",
                        "framework": "pytest",
                    }
                ],

            })

        if "REST API" in prompt or "FastAPI" in prompt:
            return json.dumps({
                "output": "Built FastAPI application with auth endpoints",
                "artifacts": {
                    "api.py": (
                        "from fastapi import FastAPI\n"
                        "from models import User\n\n"
                        "app = FastAPI()\n\n"
                        "@app.get('/users/{user_id}')\n"
                        "async def get_user(user_id: int):\n"
                        "    return User(id=user_id, name='Alice', email='a@b.com')\n"
                    ),
                },
                "generated_tests": [],

            })

        if "Dashboard" in prompt or "UI" in prompt:
            return json.dumps({
                "output": "Created React dashboard with metrics panels",
                "artifacts": {
                    "dashboard.tsx": (
                        "import React from 'react';\n\n"
                        "export const Dashboard = () => (\n"
                        "  <div className='dashboard'>\n"
                        "    <h1>Metrics Dashboard</h1>\n"
                        "    <div className='charts'>...</div>\n"
                        "  </div>\n"
                        ");\n"
                    ),
                },
                "generated_tests": [],

            })

        if "Integration" in prompt or "E2E" in prompt:
            return json.dumps({
                "output": "Wrote integration tests for API and UI",
                "artifacts": {
                    "test_integration.py": (
                        "import pytest\n\n"
                        "def test_user_flow():\n"
                        "    # Create user via API, verify in UI\n"
                        "    assert True  # placeholder\n"
                    ),
                },
                "generated_tests": [],

            })

        # Default response for any other task
        return json.dumps({
            "output": "Task completed",
            "artifacts": {"result.txt": "output"},
            "generated_tests": [],
        })

    def _mcp_agent_response(self, prompt: str) -> str:
        """
        MCP agent response — demonstrates tool-calling flow.

        On first call: requests tool invocation.
        On subsequent calls (after receiving tool results): returns final result.
        """
        if "Tool results:" in prompt:
            # Second turn: we received tool results, produce final output
            return json.dumps({
                "final_result": {
                    "output": "Research complete. Found 3 relevant frameworks.",
                    "artifacts": {
                        "research.md": "# Framework Analysis\n\n1. Django\n2. Flask\n3. FastAPI",
                    },
                    "generated_tests": [],
                }
            })
        else:
            # First turn: call a tool to gather information
            return json.dumps({
                "tool_calls": [
                    {
                        "server": "web-search",
                        "tool": "search",
                        "arguments": {"query": "best Python web frameworks 2025"},
                    }
                ]
            })


# ============================================================================
# MOCK MCP CLIENT — Simulates MCP server tool discovery and invocation
# ============================================================================


class MockMCPClient:
    """
    Mock MCP client for demonstration.

    In production, MCPClient connects to real MCP servers (via stdio or SSE)
    and discovers their tools dynamically. This mock simulates that behavior.
    """

    def __init__(self) -> None:
        self.tool_calls: list[dict[str, Any]] = []

    async def connect(self) -> None:
        pass  # Real client: establishes stdio/SSE connection

    async def list_tools(self) -> list[MCPToolInfo]:
        """
        Returns tool descriptions the LLM will see in its system prompt.

        Real MCP servers expose tools with JSON Schema input definitions.
        The MCPAgent formats these into the LLM's context so it knows
        what tools are available and how to call them.
        """
        return [
            MCPToolInfo(
                server_name="web-search",
                name="search",
                description="Search the web for information",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            ),
            MCPToolInfo(
                server_name="web-search",
                name="fetch_page",
                description="Fetch and extract text from a web page",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                    },
                    "required": ["url"],
                },
            ),
        ]

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        """
        Execute a tool on an MCP server and return the result.

        Real MCP client: sends JSON-RPC call to server, receives structured response.
        """
        self.tool_calls.append({
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments,
        })
        return f"Search results for '{arguments.get('query', '')}': Django, Flask, FastAPI"

    async def close(self) -> None:
        pass  # Real client: closes connection to server

    @property
    def connected_servers(self) -> list[str]:
        return ["web-search"]


# ============================================================================
# DEMO FUNCTIONS — Each demonstrates a specific feature
# ============================================================================


def banner(title: str) -> None:
    """Print a formatted section banner."""
    width = 70
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


# --------------------------------------------------------------------------
# Demo 1: Building Specifications Programmatically
# --------------------------------------------------------------------------


def demo_spec_construction() -> Specification:
    """
    DEMO 1: Build a specification using Pydantic models.

    Specifications are the single input to rooben. They can be loaded from
    YAML/JSON files (load_spec()) or constructed programmatically as shown here.

    A spec has two layers:
      - Structured fields: validated by Pydantic (deliverables, agents, criteria)
      - Semi-structured fields: free-text markdown for the LLM planner (goal, context)
    """
    banner("Demo 1: Specification Construction")

    spec = Specification(
        id="spec-demo-001",
        title="Full-Stack Web Application",

        # ── Semi-structured: the LLM planner reads these to understand intent ──
        goal=(
            "Build a full-stack web application with a Python API backend, "
            "React frontend dashboard, and comprehensive integration tests."
        ),
        context=(
            "The application manages user sessions and displays real-time "
            "metrics. The backend serves data via REST endpoints and the "
            "frontend renders live-updating charts."
        ),

        # ── Structured: concrete output artifacts ──
        deliverables=[
            Deliverable(
                id="D-001",
                name="Data Models",
                deliverable_type=DeliverableType.CODE,
                description="Pydantic models for User, Session, and Token",
                output_path="src/models.py",
                acceptance_criteria_ids=["AC-001"],
            ),
            Deliverable(
                id="D-002",
                name="REST API",
                deliverable_type=DeliverableType.API,
                description="FastAPI application using the data models",
                output_path="src/api.py",
                acceptance_criteria_ids=["AC-001", "AC-002"],
            ),
            Deliverable(
                id="D-003",
                name="Dashboard UI",
                deliverable_type=DeliverableType.APPLICATION,
                description="React dashboard with metrics charts",
                output_path="src/dashboard.tsx",
                acceptance_criteria_ids=["AC-003"],
            ),
            Deliverable(
                id="D-004",
                name="Integration Tests",
                deliverable_type=DeliverableType.CODE,
                description="E2E tests for API and UI integration",
                output_path="tests/test_integration.py",
                acceptance_criteria_ids=["AC-004"],
            ),
        ],

        # ── Structured: how success is measured ──
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="AC-001",
                    description="Data models validate input correctly",
                    verification="test",        # Will run pytest
                    priority="critical",
                ),
                AcceptanceCriterion(
                    id="AC-002",
                    description="API returns proper JSON responses",
                    verification="llm_judge",   # Will ask Claude to judge
                    priority="high",
                ),
                AcceptanceCriterion(
                    id="AC-003",
                    description="Dashboard renders metric panels",
                    verification="llm_judge",
                    priority="high",
                ),
                AcceptanceCriterion(
                    id="AC-004",
                    description="Integration tests pass with >90% coverage",
                    verification="test",
                    priority="critical",
                ),
            ],
            test_requirements=[
                TestRequirement(
                    id="TR-001",
                    description="Unit tests for data models",
                    test_type=TestType.UNIT,
                    target_deliverable="D-001",
                    # skeleton: pre-written test code the agent MUST implement/pass
                    skeleton=(
                        "def test_user_email_validation():\n"
                        "    from models import User\n"
                        "    user = User(id=1, name='Test', email='test@example.com')\n"
                        "    assert '@' in user.email\n"
                    ),
                ),
            ],
            completion_threshold=0.85,  # 85% of criteria must pass
        ),

        # ── Structured: constraints the planner must respect ──
        constraints=[
            Constraint(
                id="C-001",
                category=ConstraintCategory.TECHNOLOGY,
                description="Backend must use Python 3.11+ and FastAPI",
                hard=True,   # hard=True means failure if violated
            ),
            Constraint(
                id="C-002",
                category=ConstraintCategory.SECURITY,
                description="No hardcoded credentials in source code",
                hard=True,
            ),
        ],

        # ── Structured: available agents ──
        agents=[
            AgentSpec(
                id="agent-backend",
                name="Backend Developer",
                transport=AgentTransport.SUBPROCESS,
                endpoint="rooben.agents.llm_agent.LLMAgent",
                description="Writes Python backend code (FastAPI, Pydantic, SQLAlchemy)",
                capabilities=["python", "fastapi", "pydantic", "api"],
                max_concurrency=2,    # Can handle 2 tasks at once
                budget=AgentBudget(max_retries_per_task=3),
            ),
            AgentSpec(
                id="agent-frontend",
                name="Frontend Developer",
                transport=AgentTransport.SUBPROCESS,
                endpoint="rooben.agents.llm_agent.LLMAgent",
                description="Builds React UI components and dashboards",
                capabilities=["react", "typescript", "frontend", "charts"],
                max_concurrency=1,
            ),
            AgentSpec(
                id="agent-testing",
                name="Test Engineer",
                transport=AgentTransport.SUBPROCESS,
                endpoint="rooben.agents.llm_agent.LLMAgent",
                description="Writes pytest test suites for backend and integration",
                capabilities=["python", "pytest", "testing", "e2e"],
                max_concurrency=2,
            ),
        ],

        # ── Semi-structured: optional decomposition hints ──
        # The planner can use or ignore these. They suggest how to organize work.
        workflow_hints=[
            WorkflowHint(
                name="Data Layer",
                description="Build data models first — everything depends on them",
                suggested_agent_id="agent-backend",
            ),
            WorkflowHint(
                name="API Layer",
                description="Build API endpoints after models are ready",
                suggested_agent_id="agent-backend",
                depends_on=["Data Layer"],
            ),
            WorkflowHint(
                name="UI Layer",
                description="Dashboard can be built in parallel with API",
                suggested_agent_id="agent-frontend",
            ),
            WorkflowHint(
                name="Integration Testing",
                description="Tests need both API and UI to be complete",
                suggested_agent_id="agent-testing",
                depends_on=["API Layer", "UI Layer"],
            ),
        ],

        # ── Structured: global resource limits ──
        global_budget=GlobalBudget(
            max_total_tasks=20,         # Max tasks the planner can create
            max_concurrent_agents=5,    # Max agents running at once
            max_wall_seconds=600,       # 10 minute timeout
        ),
    )

    print(f"Specification: {spec.title}")
    print(f"  ID:            {spec.id}")
    print(f"  Deliverables:  {len(spec.deliverables)}")
    print(f"  Agents:        {len(spec.agents)}")
    print(f"  Criteria:      {len(spec.success_criteria.acceptance_criteria)}")
    print(f"  Constraints:   {len(spec.constraints)}")
    print(f"  Content hash:  {spec.content_hash()}")
    print(f"  Budget:        max {spec.global_budget.max_total_tasks} tasks, "
          f"{spec.global_budget.max_wall_seconds}s wall time")

    return spec


# --------------------------------------------------------------------------
# Demo 2: YAML Spec Loading
# --------------------------------------------------------------------------


def demo_yaml_loading() -> None:
    """
    DEMO 2: Load a specification from a YAML file.

    rooben supports both YAML and JSON spec files. The loader validates
    the spec against Pydantic models and raises clear errors on invalid input.
    """
    banner("Demo 2: YAML Specification Loading")

    spec = load_spec("examples/hello_api.yaml")
    print(f"Loaded: {spec.title}")
    print(f"  ID:           {spec.id}")
    print(f"  Goal:         {spec.goal[:80]}...")
    print(f"  Deliverables: {len(spec.deliverables)}")
    for d in spec.deliverables:
        print(f"    [{d.deliverable_type.value:15s}] {d.name} -> {d.output_path}")
    print(f"  Agents:       {len(spec.agents)}")
    for a in spec.agents:
        print(f"    [{a.transport.value:10s}] {a.name} (concurrency={a.max_concurrency})")
    print(f"  Criteria:     {len(spec.success_criteria.acceptance_criteria)}")
    for ac in spec.success_criteria.acceptance_criteria:
        print(f"    [{ac.verification:10s}] {ac.description[:60]}...")
    print(f"  Hints:        {len(spec.workflow_hints)}")
    for wh in spec.workflow_hints:
        deps = f" (after: {', '.join(wh.depends_on)})" if wh.depends_on else ""
        print(f"    {wh.name}{deps}")


# --------------------------------------------------------------------------
# Demo 3: Full Orchestration
# --------------------------------------------------------------------------


async def demo_full_orchestration(spec: Specification) -> WorkflowState:
    """
    DEMO 3: Run full orchestration — plan, dispatch, verify, complete.

    This is the primary workflow. The orchestrator:
      1. Sends the spec to the planner → gets a DAG of tasks
      2. Finds ready tasks (all deps satisfied) → dispatches concurrently
      3. Each agent executes its task → produces output + artifacts
      4. Output is sanitized (credentials redacted)
      5. Output is verified (pytest or LLM judge)
      6. On pass: mark complete. On fail: retry (up to max_retries)
      7. Loop until all tasks are complete or budget is exhausted
    """
    banner("Demo 3: Full Orchestration")

    provider = DemoLLMProvider()

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── Build components ──
        planner = LLMPlanner(provider=provider)

        # The AgentRegistry manages agent instances and their concurrency.
        # Normally you'd call registry.register_from_specs(spec.agents) which
        # creates SubprocessAgent/HTTPAgent/MCPAgent based on transport type.
        #
        # For this demo, we register LLMAgent instances directly with the
        # mock provider so everything runs in-process (no subprocess spawning).
        # This is the same pattern used in the test suite.
        registry = AgentRegistry(llm_provider=provider)
        for agent_spec in spec.agents:
            agent = LLMAgent(agent_id=agent_spec.id, provider=provider)
            registry._agents[agent_spec.id] = agent
            registry._semaphores[agent_spec.id] = asyncio.Semaphore(
                agent_spec.max_concurrency
            )

        # Filesystem backend persists state as JSON after every transition.
        # Other options: PostgresBackend, LinearBackend
        backend = FilesystemBackend(base_dir=tmpdir)

        # LLM judge verifier asks Claude to evaluate task output quality.
        # Alternative: TestRunnerVerifier runs pytest on generated tests.
        verifier = LLMJudgeVerifier(provider=provider)

        # ── Build and run orchestrator ──
        orchestrator = Orchestrator(
            planner=planner,
            agent_registry=registry,
            backend=backend,
            verifier=verifier,
            budget=spec.global_budget,
        )

        print("Starting orchestration...")
        print(f"  Spec: {spec.title}")
        print(f"  Budget: max {spec.global_budget.max_total_tasks} tasks, "
              f"{spec.global_budget.max_concurrent_agents} concurrent agents")
        print()

        # run() is the single entry point — it handles the entire lifecycle
        state = await orchestrator.run(spec)

    # ── Inspect results ──
    print("Orchestration complete!\n")

    # Workflows
    for wf in state.workflows.values():
        print(f"Workflow: {wf.id}")
        print(f"  Status:    {wf.status.value}")
        print(f"  Tasks:     {wf.completed_tasks} passed / {wf.total_tasks} total")

    # Workstreams
    print(f"\nWorkstreams ({len(state.workstreams)}):")
    for ws in state.workstreams.values():
        print(f"  {ws.name}: {len(ws.task_ids)} tasks")

    # Tasks with artifacts
    print(f"\nTasks ({len(state.tasks)}):")
    for task in state.tasks.values():
        agent = task.assigned_agent_id or "unassigned"
        deps = f" (depends on: {', '.join(task.depends_on)})" if task.depends_on else ""
        print(f"  [{task.status.value:10s}] {task.title} (agent: {agent}){deps}")

        if task.result and task.result.artifacts:
            for name, content in task.result.artifacts.items():
                lines = content.count('\n') + 1
                print(f"               artifact: {name} ({lines} lines)")

    return state


# --------------------------------------------------------------------------
# Demo 4: MCP Agent Integration
# --------------------------------------------------------------------------


async def demo_mcp_agent() -> None:
    """
    DEMO 4: MCP (Model Context Protocol) agent with tool calling.

    MCP agents connect to external tool servers and use an LLM to decide
    which tools to call. The agentic loop:
      1. Connect to MCP servers, discover available tools
      2. Build system prompt with tool schemas
      3. Send task description to LLM
      4. LLM outputs tool_calls → agent executes them
      5. Tool results fed back to LLM
      6. LLM outputs final_result → agent returns TaskResult
    """
    banner("Demo 4: MCP Agent (Tool-Calling Loop)")

    provider = DemoLLMProvider()
    mock_mcp = MockMCPClient()

    # Create an MCP agent with configured servers
    mcp_configs = [
        MCPServerConfig(
            name="web-search",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@anthropic/brave-search-mcp"],
            env={"BRAVE_API_KEY": "demo-key"},
        ),
    ]

    agent = MCPAgent(
        agent_id="research-agent",
        mcp_configs=mcp_configs,
        llm_provider=provider,
        max_turns=5,       # Max agentic loop iterations
        max_tokens=4096,   # Max tokens per LLM call
    )

    # Create a research task
    task = Task(
        id="task-research",
        workstream_id="ws-research",
        workflow_id="wf-research",
        title="Research Python Web Frameworks",
        description="Search the web for the top Python web frameworks and write a summary.",
        status=TaskStatus.PENDING,
        assigned_agent_id="research-agent",
        depends_on=[],
        acceptance_criteria_ids=["AC-001"],
        verification_strategy="llm_judge",
        skeleton_tests=[],
        attempt=0,
        max_retries=2,
    )

    print(f"Task: {task.title}")
    print(f"Agent: {agent.agent_id} (MCP transport)")
    print(f"MCP servers: {[c.name for c in mcp_configs]}")
    print(f"Max turns: 5")
    print()

    # Patch MCPClient methods to use our mock
    from unittest.mock import patch
    with patch.object(MCPClient, "connect", mock_mcp.connect), \
         patch.object(MCPClient, "list_tools", mock_mcp.list_tools), \
         patch.object(MCPClient, "call_tool", mock_mcp.call_tool), \
         patch.object(MCPClient, "close", mock_mcp.close):
        result = await agent.execute(task)

    print("Agentic loop completed:")
    print(f"  Output:     {result.output}")
    print(f"  Artifacts:  {list(result.artifacts.keys())}")
    print(f"  Error:      {result.error}")
    print(f"  Wall time:  {result.wall_seconds:.3f}s")

    print(f"\nTool calls made ({len(mock_mcp.tool_calls)}):")
    for call in mock_mcp.tool_calls:
        print(f"  {call['server']}/{call['tool']}({call['arguments']})")

    print(f"\nLLM calls made ({len(provider.call_log)}):")
    for i, call in enumerate(provider.call_log):
        print(f"  Turn {i+1}: system='{call['system'][:50]}...' prompt='{call['prompt'][:50]}...'")


# --------------------------------------------------------------------------
# Demo 5: Budget Enforcement
# --------------------------------------------------------------------------


async def demo_budget_enforcement() -> None:
    """
    DEMO 5: Budget enforcement — hitting resource limits.

    The BudgetTracker monitors:
      - max_total_tokens:  Total LLM tokens consumed
      - max_total_tasks:   Total tasks completed
      - max_wall_seconds:  Wall clock time
      - max_concurrent_agents: Parallel agent limit (semaphore)

    When any limit is breached, BudgetExceeded is raised and the
    orchestrator terminates gracefully.
    """
    banner("Demo 5: Budget Enforcement")

    # ── Token budget ──
    tracker = BudgetTracker(max_total_tokens=1000)
    print("Token budget: 1000 tokens")

    await tracker.record_tokens(500)
    print(f"  After 500 tokens: {tracker.tokens_used}/1000")

    await tracker.record_tokens(400)
    print(f"  After 400 more:   {tracker.tokens_used}/1000")

    try:
        await tracker.record_tokens(200)  # This exceeds the budget
    except BudgetExceeded as exc:
        print(f"  BUDGET EXCEEDED: {exc}")
        print(f"    Resource: {exc.resource}, Limit: {exc.limit}, Current: {exc.current}")

    # ── Task budget ──
    print()
    tracker2 = BudgetTracker(max_total_tasks=3)
    print("Task budget: 3 tasks")

    for i in range(3):
        await tracker2.record_task_completion()
        print(f"  Task {i+1} completed: {tracker2.tasks_completed}/3")

    try:
        await tracker2.record_task_completion()  # 4th task exceeds budget
    except BudgetExceeded as exc:
        print(f"  BUDGET EXCEEDED: {exc}")

    # ── Summary ──
    print(f"\nBudget summary: {tracker.summary()}")


# --------------------------------------------------------------------------
# Demo 6: Output Sanitization
# --------------------------------------------------------------------------


def demo_output_sanitization() -> None:
    """
    DEMO 6: Automatic credential redaction.

    The OutputSanitizer scans all agent output before it's persisted.
    It detects and redacts:
      - API keys (api_key=..., secret=..., token=...)
      - OpenAI keys (sk-...)
      - Anthropic keys (sk-ant-...)
      - GitHub PATs (ghp_...)
      - Slack tokens (xoxb-...)
      - Private keys (-----BEGIN PRIVATE KEY-----)
      - Environment variable values for sensitive vars
    """
    banner("Demo 6: Output Sanitization")

    sanitizer = OutputSanitizer()

    # Test various sensitive patterns
    test_cases = [
        (
            "Safe output with no secrets",
            "The API is running on port 8080",
        ),
        (
            "Hardcoded API key",
            "Set the header: Authorization: api_key=sk-proj-abc123def456ghi789jkl012mno345",
        ),
        (
            "Anthropic key in code",
            'client = Anthropic(api_key="sk-ant-api03-verylongkeyhere1234567890")',
        ),
        (
            "GitHub PAT",
            "git clone https://ghp_1234567890abcdefghijklmnopqrstuvwxyz@github.com/repo.git",
        ),
        (
            "Private key block",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----",
        ),
        (
            "Generic secret pattern",
            'password = "SuperSecret123!@#$%^&*()_+"',
        ),
    ]

    for label, text in test_cases:
        sanitized = sanitizer.sanitize(text)
        changed = sanitized != text
        status = "REDACTED" if changed else "clean"
        print(f"  [{status:8s}] {label}")
        if changed:
            # Show truncated before/after
            print(f"             Before: {text[:60]}...")
            print(f"             After:  {sanitized[:60]}...")
        print()

    # The sanitizer also has a check() method for reporting without modifying
    issues = sanitizer.check("Deploy with token=ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    print(f"  Issues found by check(): {len(issues)}")
    for issue in issues:
        print(f"    {issue}")


# --------------------------------------------------------------------------
# Demo 7: State Inspection
# --------------------------------------------------------------------------


def demo_state_inspection(state: WorkflowState) -> None:
    """
    DEMO 7: Inspecting workflow state after orchestration.

    WorkflowState is the aggregate root — it holds all workflows, workstreams,
    and tasks. It's what gets persisted to the state backend and what the
    orchestrator reads/writes during execution.
    """
    banner("Demo 7: State Inspection")

    # ── Workflow-level queries ──
    for wf_id, wf in state.workflows.items():
        print(f"Workflow: {wf_id}")
        print(f"  Spec ID:         {wf.spec_id}")
        print(f"  Status:          {wf.status.value}")
        print(f"  Progress:        {wf.completed_tasks}/{wf.total_tasks} tasks")
        is_complete = state.is_workflow_complete(wf_id)
        is_failed = state.is_workflow_failed(wf_id)
        print(f"  Complete?        {is_complete}")
        print(f"  Failed?          {is_failed}")
        print()

    # ── Task status distribution ──
    status_counts: dict[str, int] = {}
    for task in state.tasks.values():
        status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

    print("Task status distribution:")
    for status, count in sorted(status_counts.items()):
        bar = "#" * (count * 5)
        print(f"  {status:12s} {bar} ({count})")

    # ── Dependency graph ──
    print("\nDependency graph:")
    for task in state.tasks.values():
        if not task.depends_on:
            print(f"  {task.title} (root task)")
        else:
            dep_names = []
            for dep_id in task.depends_on:
                dep_task = state.tasks.get(dep_id)
                dep_names.append(dep_task.title if dep_task else dep_id)
            print(f"  {task.title} <- depends on: {', '.join(dep_names)}")

    # ── Artifact inventory ──
    print("\nArtifact inventory:")
    artifact_count = 0
    for task in state.tasks.values():
        if task.result and task.result.artifacts:
            for name, content in task.result.artifacts.items():
                size = len(content)
                print(f"  {name:30s} ({size:5d} bytes) from '{task.title}'")
                artifact_count += 1
    print(f"\nTotal artifacts produced: {artifact_count}")

    # ── Deduplication registry ──
    print(f"\nTask deduplication hashes: {len(state.task_hashes)} registered")


# ============================================================================
# MAIN — Run all demos
# ============================================================================


async def main() -> None:
    print()
    print("  ========================================")
    print("  Rooben — Feature Demonstration")
    print("  ========================================")
    print()
    print("  This demo exercises every major feature")
    print("  of the rooben orchestration framework")
    print("  using mock providers (no API key needed).")
    print()

    # Demo 1: Build a specification programmatically
    spec = demo_spec_construction()

    # Demo 2: Load a spec from YAML
    demo_yaml_loading()

    # Demo 3: Run full orchestration (plan → dispatch → verify → complete)
    state = await demo_full_orchestration(spec)

    # Demo 4: MCP agent with tool-calling agentic loop
    await demo_mcp_agent()

    # Demo 5: Budget enforcement (token, task limits)
    await demo_budget_enforcement()

    # Demo 6: Output sanitization (credential redaction)
    demo_output_sanitization()

    # Demo 7: State inspection (reading results after orchestration)
    demo_state_inspection(state)

    banner("All Demos Complete")
    print("All 7 feature demonstrations completed successfully.")
    print("See README.md for full documentation and API reference.\n")


if __name__ == "__main__":
    asyncio.run(main())
