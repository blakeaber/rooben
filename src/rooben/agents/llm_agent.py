"""LLM agent — uses a language model to execute tasks directly."""

from __future__ import annotations

import time

import structlog

from rooben.domain import GeneratedTest, Task, TaskResult
from rooben.planning.provider import LLMProvider

log = structlog.get_logger()

AGENT_SYSTEM_PROMPT = """\
You are an autonomous agent executing a task within a larger workflow.

Your job:
1. Read the task description carefully.
2. Produce the requested output (code, text, config, etc.).
3. If skeleton tests are provided, implement them fully so they pass.
4. If no skeleton tests are provided but the task involves code, generate
   appropriate tests (pytest for backend, playwright-style for frontend).

Output strict JSON:
{
  "output": "summary of what you produced",
  "artifacts": {
    "filename.ext": "file content as string",
    ...
  },
  "generated_tests": [
    {
      "filename": "test_something.py",
      "content": "test code",
      "test_type": "unit",
      "framework": "pytest"
    }
  ]
}

Output ONLY the JSON object. No markdown fences, no commentary.
"""


class LLMAgent:
    """Executes tasks using an LLM provider."""

    def __init__(self, agent_id: str, provider: LLMProvider, max_tokens: int = 8192):
        self._agent_id = agent_id
        self._provider = provider
        self._max_tokens = max_tokens

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def execute(self, task: Task) -> TaskResult:
        import json

        start = time.monotonic()
        prompt = self._build_prompt(task)

        try:
            gen_result = await self._provider.generate(
                system=AGENT_SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=self._max_tokens,
            )
            raw = gen_result.text
        except Exception as exc:
            log.error("llm_agent.generation_failed", agent_id=self._agent_id, error=str(exc))
            return TaskResult(
                error=f"LLM generation failed: {exc}",
                wall_seconds=time.monotonic() - start,
            )

        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:])
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return TaskResult(
                output=raw[:5000],
                wall_seconds=time.monotonic() - start,
            )

        generated_tests = [
            GeneratedTest(**t) for t in data.get("generated_tests", [])
        ]

        return TaskResult(
            output=data.get("output", ""),
            artifacts=data.get("artifacts", {}),
            generated_tests=generated_tests,
            wall_seconds=time.monotonic() - start,
        )

    async def health_check(self) -> bool:
        try:
            await self._provider.generate(
                system="Reply with 'ok'.",
                prompt="health check",
                max_tokens=10,
            )
            return True
        except Exception:
            return False

    def _build_prompt(self, task: Task) -> str:
        parts = [
            f"# Task: {task.title}",
            f"\n## Description\n{task.description}",
        ]
        if task.acceptance_criteria_ids:
            parts.append(
                f"\n## Acceptance Criteria IDs\n{', '.join(task.acceptance_criteria_ids)}"
            )
        if task.skeleton_tests:
            parts.append("\n## Skeleton Tests (you MUST implement these)")
            for i, skel in enumerate(task.skeleton_tests, 1):
                parts.append(f"\n### Test {i}\n```python\n{skel}\n```")
        return "\n".join(parts)
