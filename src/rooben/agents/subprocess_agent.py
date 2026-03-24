"""Subprocess agent — runs a Python callable in an isolated child process."""

from __future__ import annotations

import asyncio
import importlib
import json
import time

import structlog

from rooben.domain import Task, TaskResult

log = structlog.get_logger()

# The child process runner script — invoked as `python -c <this>`
_RUNNER_SCRIPT = '''
import importlib
import json
import sys

data = json.loads(sys.stdin.read())
module_path, func_name = data["callable"].rsplit(".", 1)
mod = importlib.import_module(module_path)
func = getattr(mod, func_name)
result = func(data["task"])
print(json.dumps(result))
'''


class SubprocessAgent:
    """
    Executes tasks by calling a Python function in a child process.

    The callable receives a dict (the task model) and must return a dict
    with keys: output, artifacts, error (optional).
    """

    def __init__(self, agent_id: str, callable_path: str, timeout: int = 300):
        self._agent_id = agent_id
        self._callable_path = callable_path
        self._timeout = timeout

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def execute(self, task: Task) -> TaskResult:
        start = time.monotonic()
        payload = json.dumps({
            "callable": self._callable_path,
            "task": task.model_dump(mode="json"),
        })

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", _RUNNER_SCRIPT,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=payload.encode()),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            log.error("subprocess_agent.timeout", agent_id=self._agent_id, task_id=task.id)
            return TaskResult(
                error=f"Task timed out after {self._timeout}s",
                wall_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            log.error("subprocess_agent.error", agent_id=self._agent_id, error=str(exc))
            return TaskResult(error=str(exc), wall_seconds=time.monotonic() - start)

        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            return TaskResult(
                error=f"Process exited with code {proc.returncode}: {stderr.decode()[:2000]}",
                wall_seconds=elapsed,
            )

        try:
            result_data = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return TaskResult(
                output=stdout.decode()[:5000],
                wall_seconds=elapsed,
            )

        return TaskResult(
            output=result_data.get("output", ""),
            artifacts=result_data.get("artifacts", {}),
            error=result_data.get("error"),
            wall_seconds=elapsed,
        )

    async def health_check(self) -> bool:
        try:
            module_path, func_name = self._callable_path.rsplit(".", 1)
            importlib.import_module(module_path)
            return True
        except Exception:
            return False
