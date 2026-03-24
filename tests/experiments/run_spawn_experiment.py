#!/usr/bin/env python3
"""
Spawn telemetry experiment — Phase 1c (lightweight).

Tests whether the improved spawn_spec prompt causes agents to return spawn_spec
in their final_result, without running full workflow execution.

Sends the MCP agent system prompt + a spawn-likely task description directly to
the LLM 5 times and checks whether spawn_spec is populated.

Usage:
    python tests/experiments/run_spawn_experiment.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Load .env from project root
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


NUM_RUNS = 5

# The system prompt from mcp_agent.py, but with no actual tools (forces LLM to
# decide based on prompt alone whether to spawn or complete directly)
SYSTEM_PROMPT_TEMPLATE = """\
You are an autonomous agent executing a task within a larger workflow.
You have access to external tools via MCP (Model Context Protocol) servers.

Your job:
1. Read the task description carefully.
2. Use the available tools to gather data, perform actions, or produce artifacts.
3. Produce the requested output (code, text, config, etc.).
4. If skeleton tests are provided, implement them fully so they pass.

## Available Tools

(No tools available in this test context — focus on planning your approach.)

## How to Return Final Results

When you have completed the task, output JSON with a "final_result" key:
{{
  "final_result": {{
    "output": "summary of what you produced",
    "artifacts": {{}},
    "generated_tests": [],
    "learnings": [],
    "spawn_spec": null
  }}
}}

## Sub-Workflow Spawning (optional)

The "spawn_spec" field is optional (default null). Use it ONLY when the task
genuinely requires creating 2+ independent deliverables that are each substantial
enough to warrant a separate agent with parallel execution.

Example — when a task asks you to build a full-stack application:

{{
  "final_result": {{
    "output": "Task requires multiple independent components — spawning sub-workflow.",
    "artifacts": {{}},
    "generated_tests": [],
    "learnings": [],
    "spawn_spec": {{
      "title": "Full-stack user management app",
      "goal": "Build backend API, frontend UI, and deployment config as parallel workstreams",
      "deliverables": [
        {{
          "name": "Backend API",
          "deliverable_type": "code",
          "description": "FastAPI service with auth and CRUD endpoints"
        }},
        {{
          "name": "Frontend UI",
          "deliverable_type": "code",
          "description": "React app with login, dashboard, and settings pages"
        }},
        {{
          "name": "Deployment config",
          "deliverable_type": "config",
          "description": "Docker and nginx configuration for production deployment"
        }}
      ],
      "context": "Parent task requested a complete web application. Decomposing into parallel workstreams."
    }}
  }}
}}

When to spawn: The task explicitly requires 2+ independent deliverables that are
each substantial enough to warrant a separate agent (e.g., backend + frontend,
API + documentation, or multiple microservices).

When NOT to spawn: The task is a single focused deliverable, even if complex.
Most tasks should be completed directly — only spawn when parallel decomposition
provides clear value.

## Output Rules

Since no tools are available, return your final_result immediately.
Decide: should this task be completed directly, or should it spawn sub-workflows?

IMPORTANT: Output ONLY JSON in your response. No markdown fences, no commentary.
Return a final_result JSON object.
"""

# Task descriptions — mix of spawn-likely and single-focus
SPAWN_LIKELY_TASKS = [
    # Task 1: Classic multi-component full-stack app
    """Build a complete task management web application with:
    (1) a Python FastAPI backend with user authentication (JWT), task CRUD endpoints, and SQLite database,
    (2) a React frontend with login page, task dashboard with filtering/sorting, and settings page,
    (3) Docker Compose configuration for running the full stack with nginx reverse proxy.
    Each component should be independently testable and deployable.""",

    # Task 2: Multi-service architecture
    """Create a real-time notification system consisting of:
    (1) A notification API service (FastAPI) that receives notification requests and stores them in PostgreSQL,
    (2) A WebSocket gateway service that pushes real-time updates to connected clients,
    (3) An email/SMS delivery worker that processes queued notifications via Celery,
    (4) A React admin dashboard for monitoring notification delivery status and analytics.
    Each service should have its own Dockerfile and they should communicate via Redis pub/sub.""",

    # Task 3: Data pipeline + API + UI
    """Build an analytics platform with:
    (1) A data ingestion pipeline that reads CSV/JSON files, validates schemas, and loads into a data warehouse,
    (2) A REST API that exposes aggregated metrics and supports custom date range queries,
    (3) A dashboard frontend that visualizes key metrics with charts and allows drill-down.
    The pipeline and API are independent backend components, the frontend consumes the API.""",

    # Task 4: Backend + comprehensive docs (2 deliverables)
    """Create a REST API for a bookstore inventory system AND comprehensive API documentation:
    (1) FastAPI backend with endpoints for books, authors, categories, and inventory management with PostgreSQL,
    (2) A standalone documentation site using MkDocs with API reference, tutorials, code examples, and deployment guide.
    Both deliverables are substantial and independent.""",

    # Task 5: Multi-platform deployment
    """Build a URL shortener service with:
    (1) A Go backend API that handles URL shortening, redirection, and click analytics,
    (2) A React frontend with URL submission form, link management dashboard, and analytics charts,
    (3) Terraform infrastructure-as-code for deploying to AWS (API Gateway + Lambda + DynamoDB + CloudFront + S3).
    Each component is independently developed and deployed.""",
]


@dataclass
class RunResult:
    run_number: int
    task_description: str = ""
    has_spawn_spec: bool = False
    spawn_spec: dict | None = None
    raw_output: str = ""
    wall_seconds: float = 0.0
    error: str = ""


async def run_once(run_number: int, task_desc: str) -> RunResult:
    """Send a single spawn-likely task to the LLM and check for spawn_spec."""
    from rooben.planning.provider import AnthropicProvider

    result = RunResult(run_number=run_number, task_description=task_desc[:80])

    model = os.environ.get("ROOBEN_MODEL", "claude-sonnet-4-20250514")
    provider = AnthropicProvider(model=model)

    prompt = f"""## Task

{task_desc}

## Instructions

Analyze this task. If it has 2+ substantial independent deliverables that would benefit
from parallel agent execution, return a spawn_spec. Otherwise, return a plan summary
with spawn_spec as null.

Return ONLY a JSON final_result object."""

    start = time.monotonic()
    try:
        gen = await provider.generate(
            system=SYSTEM_PROMPT_TEMPLATE,
            prompt=prompt,
            max_tokens=4096,
        )
        result.raw_output = gen.text
        result.wall_seconds = time.monotonic() - start

        # Parse response
        from rooben.utils import parse_llm_json
        data = parse_llm_json(gen.text)
        if data and "final_result" in data:
            fr = data["final_result"]
            spawn = fr.get("spawn_spec")
            if spawn and isinstance(spawn, dict) and spawn.get("deliverables"):
                result.has_spawn_spec = True
                result.spawn_spec = spawn
        elif data and "spawn_spec" in data:
            spawn = data["spawn_spec"]
            if spawn and isinstance(spawn, dict):
                result.has_spawn_spec = True
                result.spawn_spec = spawn
    except Exception as exc:
        result.error = str(exc)
        result.wall_seconds = time.monotonic() - start

    return result


async def main():
    model = os.environ.get("ROOBEN_MODEL", "claude-sonnet-4-20250514")
    print("Spawn Telemetry Experiment (Lightweight)")
    print(f"Model: {model}")
    print(f"Runs: {NUM_RUNS}")
    print()

    results: list[RunResult] = []
    for i in range(NUM_RUNS):
        task = SPAWN_LIKELY_TASKS[i % len(SPAWN_LIKELY_TASKS)]
        print(f"--- Run {i+1}/{NUM_RUNS}: {task[:70]}... ---")
        r = await run_once(i + 1, task)
        results.append(r)
        spawn_str = "SPAWN" if r.has_spawn_spec else "no-spawn"
        print(f"  [{spawn_str}] {r.wall_seconds:.1f}s", end="")
        if r.has_spawn_spec and r.spawn_spec:
            n_del = len(r.spawn_spec.get("deliverables", []))
            print(f" | deliverables={n_del} title={r.spawn_spec.get('title', '')!r}")
        elif r.error:
            print(f" | ERROR: {r.error[:100]}")
        else:
            print()

    # Summary
    total = len(results)
    spawns = sum(1 for r in results if r.has_spawn_spec)
    errors = sum(1 for r in results if r.error)
    spawn_rate = spawns / (total - errors) if (total - errors) > 0 else 0.0

    print(f"\n{'='*70}")
    print("SPAWN TELEMETRY EXPERIMENT — RESULTS")
    print(f"{'='*70}")
    for r in results:
        tag = "SPAWN" if r.has_spawn_spec else ("ERROR" if r.error else "no-spawn")
        print(f"  Run {r.run_number}: [{tag}] {r.wall_seconds:.1f}s — {r.task_description}")
        if r.has_spawn_spec and r.spawn_spec:
            for d in r.spawn_spec.get("deliverables", []):
                print(f"    - {d.get('name', '?')}: {d.get('description', '')[:60]}")

    print("\n--- Summary ---")
    print(f"  Total runs: {total}")
    print(f"  Errors: {errors}")
    print(f"  Spawn attempts: {spawns}/{total - errors} valid runs")
    print(f"  Spawn rate: {spawn_rate:.0%}")

    print("\n--- Phase 2 Decision ---")
    if spawn_rate >= 0.5:
        print(f"  RECOMMENDATION: GO — spawn triggers at {spawn_rate:.0%} (>= 50%)")
        print("  Proceed with reduced P9.5 scope (4-5 hours)")
    else:
        print(f"  RECOMMENDATION: NO-GO — spawn triggers at {spawn_rate:.0%} (< 50%)")
        print("  Remove sub-workflow code and skip P9.5 entirely")

    # Save results
    output_path = Path(__file__).parent / "spawn_experiment_results.json"
    output = {
        "model": model,
        "total_runs": total,
        "errors": errors,
        "runs_with_spawn": spawns,
        "spawn_rate": spawn_rate,
        "recommendation": "go" if spawn_rate >= 0.5 else "no-go",
        "runs": [
            {
                "run_number": r.run_number,
                "task": r.task_description,
                "has_spawn_spec": r.has_spawn_spec,
                "spawn_spec": r.spawn_spec,
                "wall_seconds": r.wall_seconds,
                "error": r.error,
            }
            for r in results
        ],
    }
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
