"""LearningStoreProtocol — shared interface for learning stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from rooben.memory.learning_store import Learning


@runtime_checkable
class LearningStoreProtocol(Protocol):
    """Protocol that both LearningStore and PostgresLearningStore implement."""

    async def store(self, learning: Learning) -> None: ...

    async def query(
        self,
        agent_id: str | None = None,
        keywords: list[str] | None = None,
        limit: int = 5,
        query_text: str | None = None,
        project_id: str | None = None,
    ) -> list[Learning]: ...

    async def increment_success(self, learning_id: str) -> None: ...

    async def curate(self) -> int: ...

    def generate_id(self) -> str: ...

    @property
    def count(self) -> int: ...
