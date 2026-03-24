"""Learning store — stub for OSS (no cross-run learning persistence)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Learning:
    """A single learning entry (no-op in OSS)."""
    id: str = ""
    agent_id: str = ""
    workflow_id: str = ""
    task_id: str = ""
    content: str = ""
    project_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


class LearningStore:
    """No-op learning store for OSS — all methods return empty results."""

    async def query(self, **kwargs) -> list[Learning]:
        return []

    async def store(self, learning: Learning) -> None:
        pass

    def generate_id(self) -> str:
        return "learn-stub"
