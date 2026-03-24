"""CodebaseIndex — AST-based repository scanning for context injection."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path

import structlog

log = structlog.get_logger()


@dataclass
class FileEntry:
    """Index entry for a single file."""
    path: str
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    docstring: str = ""
    line_count: int = 0


class CodebaseIndex:
    """
    AST-based repository index for keyword-driven context injection.

    Scans Python files, extracts function/class names and docstrings,
    and serves relevant file summaries to the ContextBuilder.
    """

    def __init__(self, root_path: str, ignore_dirs: set[str] | None = None):
        self._root = Path(root_path)
        self._ignore_dirs = ignore_dirs or {
            ".git", "__pycache__", ".venv", "venv", "node_modules",
            ".mypy_cache", ".pytest_cache", ".tox", "dist", "build",
            ".eggs", "*.egg-info",
        }
        self._entries: dict[str, FileEntry] = {}

    def scan(self) -> None:
        """Walk directory and parse .py files with ast."""
        self._entries.clear()
        for root, dirs, files in os.walk(self._root):
            # Filter ignored directories
            dirs[:] = [
                d for d in dirs
                if d not in self._ignore_dirs and not d.endswith(".egg-info")
            ]
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                filepath = Path(root) / filename
                try:
                    entry = self._parse_file(filepath)
                    rel_path = str(filepath.relative_to(self._root))
                    self._entries[rel_path] = entry
                except Exception:
                    continue

    def update(self, filepath: str, content: str) -> None:
        """Update a single file entry without full rescan."""
        try:
            tree = ast.parse(content)
            entry = self._extract_info(tree, content)
            entry.path = filepath
            self._entries[filepath] = entry
        except Exception:
            pass

    def query(self, keywords: list[str], budget_tokens: int = 2000) -> str:
        """
        Find files relevant to keywords, render summaries within token budget.

        Returns a formatted string suitable for prompt injection.
        """
        if not self._entries or not keywords:
            return ""

        # Score each file by keyword overlap
        kw_lower = [k.lower() for k in keywords]
        scored: list[tuple[float, str, FileEntry]] = []

        for path, entry in self._entries.items():
            score = self._relevance_score(entry, kw_lower)
            if score > 0:
                scored.append((score, path, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Render top entries within budget
        parts: list[str] = []
        used_chars = 0
        char_budget = budget_tokens * 4  # Rough chars-per-token

        for score, path, entry in scored:
            summary = self._render_entry(path, entry)
            if used_chars + len(summary) > char_budget:
                break
            parts.append(summary)
            used_chars += len(summary)

        return "\n".join(parts) if parts else ""

    def serialize(self) -> dict:
        """Serialize the index to a dict."""
        return {
            path: {
                "path": entry.path,
                "classes": entry.classes,
                "functions": entry.functions,
                "docstring": entry.docstring,
                "line_count": entry.line_count,
            }
            for path, entry in self._entries.items()
        }

    @classmethod
    def deserialize(cls, data: dict, root_path: str) -> "CodebaseIndex":
        """Deserialize from a dict."""
        index = cls(root_path)
        for path, entry_data in data.items():
            index._entries[path] = FileEntry(**entry_data)
        return index

    @property
    def file_count(self) -> int:
        return len(self._entries)

    def _parse_file(self, filepath: Path) -> FileEntry:
        """Parse a single Python file."""
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
        entry = self._extract_info(tree, content)
        entry.path = str(filepath)
        return entry

    def _extract_info(self, tree: ast.Module, content: str) -> FileEntry:
        """Extract class/function names and docstrings from an AST."""
        classes: list[str] = []
        functions: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Only top-level and class-level functions
                functions.append(node.name)

        # Module-level docstring
        docstring = ast.get_docstring(tree) or ""

        return FileEntry(
            path="",
            classes=classes,
            functions=functions,
            docstring=docstring[:200],
            line_count=content.count("\n") + 1,
        )

    def _relevance_score(self, entry: FileEntry, keywords: list[str]) -> float:
        """Score a file entry by keyword overlap."""
        searchable = " ".join([
            entry.path.lower(),
            " ".join(c.lower() for c in entry.classes),
            " ".join(f.lower() for f in entry.functions),
            entry.docstring.lower(),
        ])
        return sum(1 for kw in keywords if kw in searchable)

    def _render_entry(self, path: str, entry: FileEntry) -> str:
        """Render a file entry as a compact summary."""
        parts = [f"### {path} ({entry.line_count} lines)"]
        if entry.docstring:
            parts.append(f"  {entry.docstring[:100]}")
        if entry.classes:
            parts.append(f"  Classes: {', '.join(entry.classes)}")
        if entry.functions:
            # Show first 10 functions
            fns = entry.functions[:10]
            if len(entry.functions) > 10:
                fns.append(f"... +{len(entry.functions) - 10} more")
            parts.append(f"  Functions: {', '.join(fns)}")
        return "\n".join(parts)
