"""LocalWorkspaceStorage — filesystem-backed workspace storage for OSS."""

from __future__ import annotations

import fnmatch
import io
import os
import shutil
import zipfile
from pathlib import Path
from typing import AsyncIterator

from rooben.workspace.protocol import FileEntry

ZIP_EXCLUDE_PATTERNS = [
    "node_modules/",
    ".git/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "*.pyc",
    ".DS_Store",
    "*.egg-info/",
]

_ZIP_CHUNK_SIZE = 64 * 1024  # 64KB chunks for streaming


def _should_exclude(rel_path: str, exclude: list[str]) -> bool:
    """Check if a relative path matches any exclude pattern."""
    for pattern in exclude:
        if pattern.endswith("/"):
            # Directory pattern — check if any path component matches
            dir_name = pattern.rstrip("/")
            parts = rel_path.replace("\\", "/").split("/")
            if dir_name in parts:
                return True
        elif fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
            os.path.basename(rel_path), pattern
        ):
            return True
    return False


class LocalWorkspaceStorage:
    """Filesystem-backed workspace storage."""

    async def list_files(self, workspace_dir: str) -> list[FileEntry]:
        ws_path = Path(workspace_dir)
        if not ws_path.is_dir():
            return []

        entries: list[FileEntry] = []
        for root, _dirs, filenames in os.walk(ws_path):
            # Skip excluded directories in-place
            rel_root = str(Path(root).relative_to(ws_path))
            if _should_exclude(rel_root + "/", ZIP_EXCLUDE_PATTERNS):
                continue
            for fname in filenames:
                full = Path(root) / fname
                rel = str(full.relative_to(ws_path))
                if _should_exclude(rel, ZIP_EXCLUDE_PATTERNS):
                    continue
                try:
                    stat = full.stat()
                    entries.append(FileEntry(
                        path=rel,
                        size_bytes=stat.st_size,
                        source="disk",
                    ))
                except OSError:
                    continue

        entries.sort(key=lambda e: e.path)
        return entries

    async def read_file(self, workspace_dir: str, path: str) -> bytes:
        ws_path = Path(workspace_dir)
        resolved = (ws_path / path).resolve()
        # Path traversal guard
        if not str(resolved).startswith(str(ws_path.resolve())):
            raise ValueError("Path traversal not allowed")
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return resolved.read_bytes()

    async def stream_zip(
        self,
        workspace_dir: str,
        exclude: list[str] | None = None,
    ) -> AsyncIterator[bytes]:
        effective_exclude = exclude if exclude is not None else ZIP_EXCLUDE_PATTERNS
        ws_path = Path(workspace_dir)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if ws_path.is_dir():
                for root, dirs, filenames in os.walk(ws_path):
                    # Prune excluded directories in-place to avoid descending
                    rel_root = str(Path(root).relative_to(ws_path))
                    dirs[:] = [
                        d for d in dirs
                        if not _should_exclude(
                            (rel_root + "/" + d if rel_root != "." else d) + "/",
                            effective_exclude,
                        )
                    ]
                    for fname in filenames:
                        full = Path(root) / fname
                        rel = str(full.relative_to(ws_path))
                        if _should_exclude(rel, effective_exclude):
                            continue
                        zf.write(full, rel)

        buf.seek(0)
        while True:
            chunk = buf.read(_ZIP_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

    async def cleanup(self, workspace_dir: str) -> None:
        ws_path = Path(workspace_dir)
        if ws_path.is_dir():
            shutil.rmtree(ws_path)

    async def workspace_size(self, workspace_dir: str) -> int:
        ws_path = Path(workspace_dir)
        if not ws_path.is_dir():
            return 0
        total = 0
        for root, _dirs, filenames in os.walk(ws_path):
            for fname in filenames:
                try:
                    total += (Path(root) / fname).stat().st_size
                except OSError:
                    continue
        return total
