"""Agent protocol — the contract all agents must implement."""

from __future__ import annotations

from typing import Protocol

from rooben.domain import Task, TaskResult


class AgentProtocol(Protocol):
    """An agent that can execute a task and return a result."""

    @property
    def agent_id(self) -> str: ...

    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task and return a result.

        The agent should:
        1. Read the task description and acceptance criteria
        2. Produce output (code, text, artifacts)
        3. If skeleton_tests are present, implement and run them
        4. Return a TaskResult with output, artifacts, and generated tests
        """
        ...

    async def health_check(self) -> bool:
        """Return True if the agent is available and ready."""
        ...
