"""Shared dependencies for dashboard routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg
    from fastapi import Request

    from rooben.memory.learning_store import LearningStore
    from rooben.workspace.protocol import WorkspaceStorage


class DashboardDeps:
    """Container for shared dashboard dependencies."""

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        learning_store_path: str | None = None,
        learning_store: LearningStore | None = None,
        workspace_storage: WorkspaceStorage | None = None,
    ):
        self.pool = pool
        self.learning_store_path = learning_store_path
        self.learning_store = learning_store
        self.extras: dict[str, object] = {}

        # Workspace storage — defaults to LocalWorkspaceStorage if not provided
        if workspace_storage is not None:
            self.workspace_storage = workspace_storage
        else:
            from rooben.workspace.local import LocalWorkspaceStorage
            self.workspace_storage = LocalWorkspaceStorage()


# Global instance set during app lifespan
_deps: DashboardDeps | None = None


def get_deps() -> DashboardDeps:
    if _deps is None:
        raise RuntimeError("Dashboard not initialized")
    return _deps


def set_deps(deps: DashboardDeps) -> None:
    global _deps
    _deps = deps


def user_context(request: Request) -> dict | None:
    """Extract tenant-scoping context from the request user, if set by Pro auth."""
    from rooben.dashboard.models.user import ANONYMOUS_USER

    user = getattr(request.state, "current_user", ANONYMOUS_USER)
    if user and user.org_id:
        return {"user_id": user.id, "org_id": user.org_id}
    return None
