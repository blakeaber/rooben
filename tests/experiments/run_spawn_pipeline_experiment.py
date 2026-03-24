"""
End-to-end spawn rate experiment.

Tests the full pipeline: planner decomposes specs → agent receives planner-generated
task → does the agent return spawn_spec?

Phase 1: Run LLMPlanner.plan() on 6 specs across 3 categories.
Phase 2: For each planner-generated task, probe the LLM with the agent system prompt
         (including spawn guidance). Single LLM call per task. Check for spawn_spec.

Usage:
    python -m tests.experiments.run_spawn_pipeline_experiment
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dotenv import load_dotenv

load_dotenv()

from rooben.domain import Task  # noqa: E402
from rooben.planning.llm_planner import LLMPlanner  # noqa: E402
from rooben.planning.provider import AnthropicProvider  # noqa: E402
from rooben.spec.models import (  # noqa: E402
    AcceptanceCriterion,
    AgentSpec,
    AgentTransport,
    Deliverable,
    DeliverableType,
    Specification,
    SuccessCriteria,
    TestRequirement,
    TestType,
)
from rooben.utils import build_task_prompt, parse_llm_json  # noqa: E402


# ---------------------------------------------------------------------------
# Spawn guidance text (extracted from MCP_AGENT_SYSTEM_PROMPT lines 76-121)
# ---------------------------------------------------------------------------

SPAWN_GUIDANCE = """\

## Sub-Workflow Spawning (optional)

The "spawn_spec" field is optional (default null). Use it ONLY when the task
genuinely requires creating 2+ independent deliverables that are each substantial
enough to warrant a separate agent with parallel execution.

Example — when a task asks you to build a full-stack application:

{
  "final_result": {
    "output": "Task requires multiple independent components — spawning sub-workflow.",
    "artifacts": {},
    "generated_tests": [],
    "learnings": [],
    "spawn_spec": {
      "title": "Full-stack user management app",
      "goal": "Build backend API, frontend UI, and deployment config as parallel workstreams",
      "deliverables": [
        {
          "name": "Backend API",
          "deliverable_type": "code",
          "description": "FastAPI service with auth and CRUD endpoints"
        },
        {
          "name": "Frontend UI",
          "deliverable_type": "code",
          "description": "React app with login, dashboard, and settings pages"
        },
        {
          "name": "Deployment config",
          "deliverable_type": "config",
          "description": "Docker and nginx configuration for production deployment"
        }
      ],
      "context": "Parent task requested a complete web application. Decomposing into parallel workstreams."
    }
  }
}

When to spawn: The task explicitly requires 2+ independent deliverables that are
each substantial enough to warrant a separate agent (e.g., backend + frontend,
API + documentation, or multiple microservices).

When NOT to spawn: The task is a single focused deliverable, even if complex.
Most tasks should be completed directly — only spawn when parallel decomposition
provides clear value.
"""

# Probe system prompt: NO_TOOLS base + spawn guidance
PROBE_SYSTEM_PROMPT = """\
You are an autonomous agent executing a task within a larger workflow.

NOTE: MCP servers were configured but no tools are currently available.
Proceed with the task using your own knowledge.

Output strict JSON:
{
  "final_result": {
    "output": "summary of what you produced",
    "artifacts": {
      "filename.ext": "file content as string"
    },
    "generated_tests": [],
    "learnings": [],
    "spawn_spec": null
  }
}
""" + SPAWN_GUIDANCE + """
Output ONLY the JSON object. No markdown fences, no commentary.
"""


# ---------------------------------------------------------------------------
# Spec factory functions
# ---------------------------------------------------------------------------

def _make_agent(agent_id: str, name: str, desc: str, caps: list[str]) -> AgentSpec:
    return AgentSpec(
        id=agent_id,
        name=name,
        transport=AgentTransport.MCP,
        description=desc,
        capabilities=caps,
    )


def spec_a1_hello_api() -> Specification:
    """Category A (simple): Hello World REST API."""
    return Specification(
        id="exp-a1",
        title="Hello World REST API",
        goal="Build a single-endpoint REST API that returns 'Hello, World!' on GET /hello.",
        context="Minimal API for testing. No database, no auth.",
        deliverables=[
            Deliverable(
                id="D-1",
                name="Hello API",
                deliverable_type=DeliverableType.API,
                description="FastAPI app with one GET /hello endpoint returning JSON greeting.",
            ),
        ],
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="GET /hello returns 200 with greeting JSON"),
            ],
        ),
        agents=[_make_agent("agent-backend", "Backend Dev", "Builds Python backend services", ["python", "fastapi"])],
    )


def spec_a2_md_cli() -> Specification:
    """Category A (simple): Markdown-to-HTML CLI."""
    return Specification(
        id="exp-a2",
        title="Markdown-to-HTML CLI",
        goal="Build a CLI tool that converts a markdown file to HTML and writes the output.",
        context="Simple file conversion utility. Single input, single output.",
        deliverables=[
            Deliverable(
                id="D-1",
                name="MD-to-HTML CLI",
                deliverable_type=DeliverableType.CODE,
                description="Python CLI using argparse that reads .md and writes .html using markdown lib.",
            ),
        ],
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="CLI converts sample.md to valid HTML"),
            ],
        ),
        agents=[_make_agent("agent-cli", "CLI Dev", "Builds Python CLI tools", ["python", "cli"])],
    )


def spec_b1_task_manager() -> Specification:
    """Category B (complex, well-structured): Full-Stack Task Manager."""
    return Specification(
        id="exp-b1",
        title="Full-Stack Task Manager",
        goal="Build a full-stack task management app with backend API, frontend UI, and Docker deployment.",
        context="Standard CRUD app with user auth, task CRUD, and a React frontend.",
        deliverables=[
            Deliverable(
                id="D-1",
                name="Backend API",
                deliverable_type=DeliverableType.API,
                description="FastAPI backend with SQLite, user auth (JWT), and task CRUD endpoints.",
            ),
            Deliverable(
                id="D-2",
                name="Frontend UI",
                deliverable_type=DeliverableType.CODE,
                description="React app with login, task list, create/edit/delete task views.",
            ),
            Deliverable(
                id="D-3",
                name="Docker Config",
                deliverable_type=DeliverableType.INFRASTRUCTURE,
                description="Dockerfile and docker-compose.yml for running the full stack.",
            ),
        ],
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="API endpoints return correct responses"),
                AcceptanceCriterion(id="AC-002", description="Frontend renders task list from API"),
                AcceptanceCriterion(id="AC-003", description="Docker compose brings up both services"),
            ],
            test_requirements=[
                TestRequirement(id="TR-001", description="API unit tests", test_type=TestType.UNIT),
            ],
        ),
        agents=[
            _make_agent("agent-backend", "Backend Dev", "Builds Python backend services", ["python", "fastapi", "sql"]),
            _make_agent("agent-frontend", "Frontend Dev", "Builds React frontends", ["react", "typescript", "css"]),
        ],
    )


def spec_b2_realtime_dashboard() -> Specification:
    """Category B (complex, well-structured): Realtime Dashboard."""
    return Specification(
        id="exp-b2",
        title="Realtime Analytics Dashboard",
        goal="Build a realtime analytics dashboard with a WebSocket data pipeline, visualization frontend, and monitoring.",
        context="Ingest streaming events via WebSocket, aggregate metrics, display live charts.",
        deliverables=[
            Deliverable(
                id="D-1",
                name="Data Pipeline",
                deliverable_type=DeliverableType.CODE,
                description="Python WebSocket server that ingests events and computes rolling aggregates.",
            ),
            Deliverable(
                id="D-2",
                name="Dashboard Frontend",
                deliverable_type=DeliverableType.APPLICATION,
                description="React dashboard with live-updating charts using recharts and WebSocket client.",
            ),
            Deliverable(
                id="D-3",
                name="Monitoring Config",
                deliverable_type=DeliverableType.INFRASTRUCTURE,
                description="Prometheus metrics exporter and Grafana dashboard JSON.",
            ),
        ],
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="WebSocket server handles 100+ concurrent connections"),
                AcceptanceCriterion(id="AC-002", description="Dashboard displays live-updating charts"),
                AcceptanceCriterion(id="AC-003", description="Prometheus endpoint exposes key metrics"),
            ],
        ),
        agents=[
            _make_agent("agent-backend", "Backend Dev", "Builds Python backend and data pipelines", ["python", "websocket", "asyncio"]),
            _make_agent("agent-frontend", "Frontend Dev", "Builds React frontends with data viz", ["react", "recharts", "websocket"]),
            _make_agent("agent-devops", "DevOps", "Infrastructure and monitoring", ["docker", "prometheus", "grafana"]),
        ],
    )


def spec_c1_saas_analytics() -> Specification:
    """Category C (vague/broad): SaaS Analytics Platform."""
    return Specification(
        id="exp-c1",
        title="SaaS Analytics Platform",
        goal="Build a SaaS analytics platform that helps businesses understand their data.",
        context="The platform should handle data ingestion, processing, visualization, user management, billing, and reporting. Make it production-ready.",
        deliverables=[
            Deliverable(
                id="D-1",
                name="Analytics Platform",
                deliverable_type=DeliverableType.APPLICATION,
                description="Complete SaaS analytics platform with all necessary components.",
            ),
        ],
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="Platform ingests and visualizes data"),
            ],
        ),
        agents=[_make_agent("agent-fullstack", "Full-Stack Dev", "Builds complete web applications", ["python", "react", "sql", "devops"])],
    )


def spec_c2_enterprise_crm() -> Specification:
    """Category C (vague/broad): Enterprise CRM System."""
    return Specification(
        id="exp-c2",
        title="Enterprise CRM System",
        goal="Build an enterprise CRM system for managing customer relationships, sales pipelines, and support tickets.",
        context="Should support multi-tenancy, role-based access, custom fields, reporting, email integration, and API access. Needs to scale to thousands of users.",
        deliverables=[
            Deliverable(
                id="D-1",
                name="CRM Backend",
                deliverable_type=DeliverableType.APPLICATION,
                description="Complete CRM backend with all business logic, data models, and integrations.",
            ),
            Deliverable(
                id="D-2",
                name="CRM Frontend",
                deliverable_type=DeliverableType.APPLICATION,
                description="Full CRM user interface with dashboards, pipeline views, and admin panels.",
            ),
        ],
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", description="CRM supports CRUD for contacts, deals, and tickets"),
                AcceptanceCriterion(id="AC-002", description="Role-based access control works correctly"),
            ],
        ),
        agents=[
            _make_agent("agent-backend", "Backend Dev", "Builds scalable backend systems", ["python", "sql", "api"]),
            _make_agent("agent-frontend", "Frontend Dev", "Builds enterprise UIs", ["react", "typescript"]),
        ],
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    task_id: str
    task_title: str
    spec_id: str
    category: str
    has_spawn: bool
    spawn_spec: dict | None
    raw_response: str
    tokens_used: int


@dataclass
class ExperimentResults:
    specs_planned: int = 0
    total_tasks: int = 0
    total_probes: int = 0
    probes_with_spawn: int = 0
    by_category: dict = field(default_factory=dict)
    probe_results: list[ProbeResult] = field(default_factory=list)
    plan_summaries: list[dict] = field(default_factory=list)
    total_tokens: int = 0
    wall_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

CATEGORIES = {
    "exp-a1": "A-simple",
    "exp-a2": "A-simple",
    "exp-b1": "B-complex",
    "exp-b2": "B-complex",
    "exp-c1": "C-vague",
    "exp-c2": "C-vague",
}


async def plan_spec(
    spec: Specification, provider: AnthropicProvider
) -> list[Task]:
    """Run LLMPlanner on a spec, return generated tasks."""
    planner = LLMPlanner(provider, max_checker_iterations=3)
    workflow_id = f"wf-{spec.id}"
    state = await planner.plan(spec, workflow_id)
    return list(state.tasks.values())


async def probe_task(
    task: Task, category: str, provider: AnthropicProvider
) -> ProbeResult:
    """Send a single LLM call proobeng whether the agent would spawn."""
    prompt = build_task_prompt(task)
    result = await provider.generate(
        system=PROBE_SYSTEM_PROMPT,
        prompt=prompt,
        max_tokens=2048,
    )

    data = parse_llm_json(result.text)
    has_spawn = False
    spawn_spec = None

    if data:
        fr = data.get("final_result", data)
        spawn_spec = fr.get("spawn_spec")
        has_spawn = spawn_spec is not None and spawn_spec != "null" and bool(spawn_spec)

    return ProbeResult(
        task_id=task.id,
        task_title=task.title,
        spec_id=task.workflow_id.replace("wf-", ""),
        category=category,
        has_spawn=has_spawn,
        spawn_spec=spawn_spec if has_spawn else None,
        raw_response=result.text[:500],
        tokens_used=result.usage.total,
    )


async def main():
    start = time.monotonic()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    provider = AnthropicProvider(model="claude-sonnet-4-20250514", api_key=api_key)
    results = ExperimentResults()

    # Spec factories in order
    spec_factories = [
        spec_a1_hello_api,
        spec_a2_md_cli,
        spec_b1_task_manager,
        spec_b2_realtime_dashboard,
        spec_c1_saas_analytics,
        spec_c2_enterprise_crm,
    ]

    # Phase 1: Plan all specs
    print("=" * 60)
    print("PHASE 1: Planning specs")
    print("=" * 60)

    all_tasks: list[tuple[Task, str]] = []  # (task, category)

    for factory in spec_factories:
        spec = factory()
        category = CATEGORIES[spec.id]
        print(f"\n  Planning {spec.id} ({category}): {spec.title}...")

        try:
            tasks = await plan_spec(spec, provider)
            print(f"    → {len(tasks)} tasks generated")
            results.plan_summaries.append({
                "spec_id": spec.id,
                "category": category,
                "title": spec.title,
                "task_count": len(tasks),
                "task_titles": [t.title for t in tasks],
            })
            for t in tasks:
                all_tasks.append((t, category))
            results.specs_planned += 1
        except Exception as e:
            print(f"    ✗ Planning failed: {e}")
            results.plan_summaries.append({
                "spec_id": spec.id,
                "category": category,
                "title": spec.title,
                "error": str(e),
            })

    results.total_tasks = len(all_tasks)
    print(f"\nTotal tasks to probe: {results.total_tasks}")

    # Phase 2: Probe all tasks
    print("\n" + "=" * 60)
    print("PHASE 2: Proobeng tasks for spawn_spec")
    print("=" * 60)

    for i, (task, category) in enumerate(all_tasks, 1):
        print(f"  [{i}/{len(all_tasks)}] {category} | {task.title[:50]}...", end=" ", flush=True)
        try:
            probe = await probe_task(task, category, provider)
            results.probe_results.append(probe)
            results.total_tokens += probe.tokens_used
            results.total_probes += 1
            if probe.has_spawn:
                results.probes_with_spawn += 1
                print(f"→ SPAWN ({probe.tokens_used} tok)")
            else:
                print(f"→ no spawn ({probe.tokens_used} tok)")
        except Exception as e:
            print(f"→ ERROR: {e}")

    results.wall_seconds = time.monotonic() - start

    # Compute per-category stats
    for cat in ["A-simple", "B-complex", "C-vague"]:
        cat_probes = [p for p in results.probe_results if p.category == cat]
        cat_spawns = [p for p in cat_probes if p.has_spawn]
        results.by_category[cat] = {
            "total": len(cat_probes),
            "spawned": len(cat_spawns),
            "rate": len(cat_spawns) / len(cat_probes) if cat_probes else 0,
        }

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\nSpecs planned: {results.specs_planned}/6")
    print(f"Total tasks:   {results.total_tasks}")
    print(f"Tasks probed:  {results.total_probes}")
    print(f"Total tokens:  {results.total_tokens:,}")
    print(f"Wall time:     {results.wall_seconds:.1f}s")

    print("\nPer-category spawn rates:")
    for cat, stats in results.by_category.items():
        pct = stats["rate"] * 100
        print(f"  {cat:12s}: {stats['spawned']}/{stats['total']} ({pct:.0f}%)")

    overall_rate = results.probes_with_spawn / results.total_probes if results.total_probes else 0
    print(f"\n  {'Overall':12s}: {results.probes_with_spawn}/{results.total_probes} ({overall_rate * 100:.0f}%)")

    # Decision recommendation
    print("\n" + "-" * 60)
    a_rate = results.by_category.get("A-simple", {}).get("rate", 0)
    b_rate = results.by_category.get("B-complex", {}).get("rate", 0)
    c_rate = results.by_category.get("C-vague", {}).get("rate", 0)

    if overall_rate == 0:
        print("RECOMMENDATION: REMOVE spawn_spec — 0% spawn rate across all categories.")
        print("spawn_spec is dead code in the full pipeline. Skip P9.5.")
    elif b_rate > 0:
        print("RECOMMENDATION: KEEP spawn_spec — spawning triggered for well-structured specs.")
        print("Proceed with reduced P9.5.")
    elif c_rate > 0 and b_rate == 0:
        print("RECOMMENDATION: DEBATABLE — spawning only triggered for vague specs.")
        print("Consider improving planner decomposition instead. Lean toward removal.")
    if a_rate > 0:
        print("WARNING: Simple specs triggered spawning — possible false positives.")
    print("-" * 60)

    # Log spawned tasks
    spawned = [p for p in results.probe_results if p.has_spawn]
    if spawned:
        print("\nSpawned tasks:")
        for p in spawned:
            print(f"  [{p.category}] {p.task_title}")
            if p.spawn_spec:
                print(f"    spawn deliverables: {[d.get('name', '?') for d in p.spawn_spec.get('deliverables', [])]}")

    # Save results
    output_path = Path(__file__).parent / "spawn_pipeline_results.json"
    output_data = {
        "experiment": "spawn_pipeline_e2e",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "specs_planned": results.specs_planned,
        "total_tasks": results.total_tasks,
        "total_probes": results.total_probes,
        "probes_with_spawn": results.probes_with_spawn,
        "overall_spawn_rate": overall_rate,
        "by_category": results.by_category,
        "plan_summaries": results.plan_summaries,
        "probe_results": [
            {
                "task_id": p.task_id,
                "task_title": p.task_title,
                "spec_id": p.spec_id,
                "category": p.category,
                "has_spawn": p.has_spawn,
                "spawn_spec": p.spawn_spec,
                "tokens_used": p.tokens_used,
            }
            for p in results.probe_results
        ],
        "total_tokens": results.total_tokens,
        "wall_seconds": results.wall_seconds,
    }
    output_path.write_text(json.dumps(output_data, indent=2))
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
