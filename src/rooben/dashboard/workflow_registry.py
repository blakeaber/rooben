"""Track running orchestrator instances for lifecycle management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RunningWorkflow:
    workflow_id: str
    orchestrator: Any  # Orchestrator
    task: asyncio.Task
    started_at: datetime = field(default_factory=datetime.utcnow)


class WorkflowRegistry:
    """Global registry of in-flight workflow executions."""

    def __init__(self) -> None:
        self._instances: dict[str, RunningWorkflow] = {}

    def register(self, workflow_id: str, orchestrator: Any, task: asyncio.Task) -> None:
        self._instances[workflow_id] = RunningWorkflow(
            workflow_id=workflow_id,
            orchestrator=orchestrator,
            task=task,
        )

    def unregister(self, workflow_id: str) -> None:
        self._instances.pop(workflow_id, None)

    def get(self, workflow_id: str) -> RunningWorkflow | None:
        return self._instances.get(workflow_id)

    def list_running(self) -> list[str]:
        return list(self._instances.keys())


_registry: WorkflowRegistry | None = None


def get_registry() -> WorkflowRegistry:
    global _registry
    if _registry is None:
        _registry = WorkflowRegistry()
    return _registry
