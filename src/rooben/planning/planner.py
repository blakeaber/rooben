"""Planner protocol — the interface every planner must implement."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from rooben.domain import WorkflowState
from rooben.spec.models import Specification


class Planner(Protocol):
    """Decomposes a Specification into a populated WorkflowState."""

    async def plan(
        self,
        spec: Specification,
        workflow_id: str,
        event_callback: Callable[[str, dict], Any] | None = None,
    ) -> WorkflowState:
        """
        Given a specification and a workflow ID, produce a WorkflowState
        containing workstreams and tasks that, when completed, satisfy the spec.
        """
        ...
