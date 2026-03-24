#!/usr/bin/env python3
"""Control group: single-focus tasks that should NOT trigger spawning."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Import the run_once function from the main experiment
from run_spawn_experiment import run_once  # noqa: E402

SINGLE_FOCUS_TASKS = [
    "Write a Python function that implements the merge sort algorithm with comprehensive error handling and type hints.",
    "Create a FastAPI REST endpoint that accepts a CSV file upload, validates the schema, and returns summary statistics as JSON.",
    "Implement a Redis-based rate limiter middleware for an Express.js application that supports sliding window and token bucket algorithms.",
]


async def main():
    print("Control Group: Single-focus tasks (should NOT spawn)")
    print()

    results = []
    for i, task in enumerate(SINGLE_FOCUS_TASKS):
        print(f"--- Control {i+1}/{len(SINGLE_FOCUS_TASKS)}: {task[:70]}... ---")
        r = await run_once(i + 1, task)
        results.append(r)
        tag = "SPAWN" if r.has_spawn_spec else "no-spawn"
        print(f"  [{tag}] {r.wall_seconds:.1f}s")

    spawns = sum(1 for r in results if r.has_spawn_spec)
    print(f"\nControl group: {spawns}/{len(results)} spawned (should be 0)")
    if spawns == 0:
        print("PASS: Agent correctly avoids spawning for single-focus tasks")
    else:
        print("WARN: Agent is over-spawning — prompt may be too aggressive")


if __name__ == "__main__":
    asyncio.run(main())
