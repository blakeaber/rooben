"""Scratchpad accumulator for MCP agent compaction.

Tracks structured entries during the agentic loop and renders them as
a rich summary for compaction injection, or as full markdown for disk flush.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ScratchpadEntry:
    turn: int
    category: str       # file_write, file_read, tool_call, error, decision
    summary: str        # One-line summary
    detail: str = ""    # Optional extra context


class ScratchpadAccumulator:
    """Accumulates structured entries during the agentic loop.

    Pure data accumulator — no heuristic logic. Recording methods accept
    pre-extracted data; callers are responsible for extraction.
    """

    def __init__(self, workspace_dir: str | None = None):
        self._entries: list[ScratchpadEntry] = []
        self._workspace_dir = workspace_dir
        self._flushed = False

    def record_file_write(self, turn: int, path: str, purpose: str = "") -> None:
        summary = path
        if purpose:
            summary = f"{path} — {purpose}"
        self._entries.append(ScratchpadEntry(turn=turn, category="file_write", summary=summary))

    def record_file_read(self, turn: int, path: str) -> None:
        self._entries.append(ScratchpadEntry(turn=turn, category="file_read", summary=path))

    def record_tool_call(self, turn: int, server: str, tool: str, outcome: str) -> None:
        self._entries.append(ScratchpadEntry(
            turn=turn,
            category="tool_call",
            summary=f"{server}/{tool}",
            detail=outcome,
        ))

    def record_error(self, turn: int, error: str, resolution: str = "") -> None:
        detail = resolution if resolution else ""
        self._entries.append(ScratchpadEntry(
            turn=turn,
            category="error",
            summary=error[:200],
            detail=detail,
        ))

    def record_decision(self, turn: int, rationale: str) -> None:
        self._entries.append(ScratchpadEntry(turn=turn, category="decision", summary=rationale))

    @property
    def scratchpad_path(self) -> str | None:
        if not self._workspace_dir:
            return None
        return os.path.join(self._workspace_dir, ".scratchpad.md")

    @property
    def has_entries(self) -> bool:
        return len(self._entries) > 0

    def _by_category(self, category: str) -> list[ScratchpadEntry]:
        return [e for e in self._entries if e.category == category]

    def to_markdown(self) -> str:
        """Full scratchpad for disk — all entries, no truncation."""
        lines = ["# Agent Scratchpad", ""]

        file_writes = self._by_category("file_write")
        file_reads = self._by_category("file_read")
        tool_calls = self._by_category("tool_call")
        errors = self._by_category("error")
        decisions = self._by_category("decision")

        if file_writes:
            lines.append("## Files Written")
            for e in file_writes:
                lines.append(f"- Turn {e.turn}: {e.summary}")
            lines.append("")

        if file_reads:
            lines.append("## Files Read")
            for e in file_reads:
                lines.append(f"- Turn {e.turn}: {e.summary}")
            lines.append("")

        if decisions:
            lines.append("## Key Decisions")
            for e in decisions:
                lines.append(f"- Turn {e.turn}: {e.summary}")
            lines.append("")

        if errors:
            lines.append("## Errors")
            for e in errors:
                resolution = f" → {e.detail}" if e.detail else ""
                lines.append(f"- Turn {e.turn}: {e.summary}{resolution}")
            lines.append("")

        if tool_calls:
            lines.append("## Tool Calls")
            for e in tool_calls:
                detail = f": {e.detail}" if e.detail else ""
                lines.append(f"- Turn {e.turn}: {e.summary}{detail}")
            lines.append("")

        return "\n".join(lines)

    def to_compact_summary(self, max_chars: int = 3000) -> str:
        """Render a compact summary for compaction injection.

        Sections in priority order: progress > files > decisions > errors > tool calls.
        Lowest-priority sections are truncated first to stay within max_chars.
        """
        file_writes = self._by_category("file_write")
        file_reads = self._by_category("file_read")
        tool_calls = self._by_category("tool_call")
        errors = self._by_category("error")
        decisions = self._by_category("decision")

        total_tools = len(file_writes) + len(file_reads) + len(tool_calls)
        turns = set(e.turn for e in self._entries)
        max_turn = max(turns) if turns else 0

        # Build sections in priority order
        sections: list[str] = []

        # Header (always included)
        header = "[Conversation compacted — prior turns summarized]"
        progress = f"\n\n## Progress\nFiles created: {len(file_writes)} | Tool calls: {total_tools} | Turns: {max_turn}"
        sections.append(header + progress)

        # Files Written (high priority)
        if file_writes:
            lines = ["\n\n## Files Written"]
            for e in file_writes:
                lines.append(f"- {e.summary}")
            sections.append("\n".join(lines))

        # Key Decisions (medium priority)
        if decisions:
            lines = ["\n\n## Key Decisions"]
            for e in decisions:
                lines.append(f"- Turn {e.turn}: {e.summary}")
            sections.append("\n".join(lines))

        # Errors Resolved (medium-low priority)
        if errors:
            lines = ["\n\n## Errors Resolved"]
            for e in errors:
                resolution = f" → {e.detail}" if e.detail else ""
                lines.append(f"- Turn {e.turn}: {e.summary}{resolution}")
            sections.append("\n".join(lines))

        # Tool Calls (lowest priority)
        if tool_calls:
            lines = ["\n\n## Tool Calls"]
            for e in tool_calls:
                detail = f": {e.detail}" if e.detail else ""
                lines.append(f"- {e.summary}{detail}")
            sections.append("\n".join(lines))

        # Scratchpad reference
        if self._flushed and self.scratchpad_path:
            sections.append(f"\n\nFull scratchpad: {self.scratchpad_path} (read_file to access)")

        # Assemble, truncating lowest-priority sections first
        result = ""
        for section in sections:
            candidate = result + section
            if len(candidate) > max_chars:
                remaining = max_chars - len(result)
                if remaining > 50:  # Only include if meaningful amount fits
                    result += section[:remaining - 3] + "..."
                break
            result = candidate

        return result
