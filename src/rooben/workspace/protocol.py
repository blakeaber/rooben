"""WorkspaceStorage protocol — abstract workspace file storage."""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from pydantic import BaseModel


class FileEntry(BaseModel):
    """Metadata for a single file in a workspace."""
    path: str
    size_bytes: int
    source: str = "disk"  # "disk" or "artifact"


class WorkspaceStorage(Protocol):
    """Abstract workspace file storage.

    OSS provides LocalWorkspaceStorage (local filesystem).
    Pro can register S3WorkspaceStorage via rooben.extensions entry points.
    """

    async def list_files(self, workspace_dir: str) -> list[FileEntry]:
        """List all files in a workspace directory."""
        ...

    async def read_file(self, workspace_dir: str, path: str) -> bytes:
        """Read a single file's content."""
        ...

    async def stream_zip(
        self,
        workspace_dir: str,
        exclude: list[str] | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream a ZIP archive of the workspace, excluding patterns."""
        ...

    async def cleanup(self, workspace_dir: str) -> None:
        """Remove a workspace directory."""
        ...

    async def workspace_size(self, workspace_dir: str) -> int:
        """Return total bytes used by this workspace."""
        ...
