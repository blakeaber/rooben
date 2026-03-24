"""HTTP agent — delegates task execution to a remote API endpoint."""

from __future__ import annotations

import time

import httpx
import structlog

from rooben.domain import Task, TaskResult

log = structlog.get_logger()


class HTTPAgent:
    """
    Sends tasks to a remote HTTP agent and returns the result.

    Uses HTTP POST /execute with task JSON.
    """

    def __init__(
        self,
        agent_id: str,
        base_url: str,
        timeout: int = 300,
        headers: dict[str, str] | None = None,
    ):
        self._agent_id = agent_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = headers or {}

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def execute(self, task: Task) -> TaskResult:
        """Execute a task via HTTP POST."""
        return await self._execute_legacy(task)

    async def _execute_legacy(self, task: Task) -> TaskResult:
        """Execute via legacy HTTP POST /execute."""
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/execute",
                    json={"task": task.model_dump(mode="json")},
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.TimeoutException:
                return TaskResult(
                    error=f"HTTP agent timed out after {self._timeout}s",
                    wall_seconds=time.monotonic() - start,
                )
            except httpx.HTTPStatusError as exc:
                return TaskResult(
                    error=f"HTTP {exc.response.status_code}: {exc.response.text[:1000]}",
                    wall_seconds=time.monotonic() - start,
                )
            except Exception as exc:
                return TaskResult(
                    error=f"HTTP agent error: {exc}",
                    wall_seconds=time.monotonic() - start,
                )

        return TaskResult(
            output=data.get("output", ""),
            artifacts=data.get("artifacts", {}),
            error=data.get("error"),
            wall_seconds=time.monotonic() - start,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
