"""Workspace storage abstraction — filesystem access for workflow outputs."""

from rooben.workspace.protocol import FileEntry, WorkspaceStorage
from rooben.workspace.local import LocalWorkspaceStorage

__all__ = ["FileEntry", "WorkspaceStorage", "LocalWorkspaceStorage"]
