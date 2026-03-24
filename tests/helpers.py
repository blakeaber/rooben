"""Test helper functions — mock agent callable and task lookup utilities."""

from __future__ import annotations

from rooben.domain import Task, WorkflowState


def find_task(state: WorkflowState, *keywords: str) -> Task:
    """Find a task whose title contains all keywords (case-insensitive).

    Raises ValueError if no match is found.
    """
    for t in state.tasks.values():
        lower = t.title.lower()
        if all(kw.lower() in lower for kw in keywords):
            return t
    titles = [t.title for t in state.tasks.values()]
    raise ValueError(f"No task matching {keywords!r} in {titles}")


def mock_agent_callable(task: dict) -> dict:
    """A mock agent callable for testing SubprocessAgent."""
    return {
        "output": f"Completed: {task['title']}",
        "artifacts": {"result.py": "# generated code\nprint('hello')"},
        "error": None,
    }
