"""Shared utilities for LLM output parsing and prompt building."""

from __future__ import annotations

import json
from typing import Any

from rooben.domain import Task


def parse_llm_json(raw: str) -> dict[str, Any] | None:
    """Parse JSON from LLM output, stripping markdown fences if present.

    Returns the parsed dict, or None if parsing fails.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def parse_llm_json_multi(raw: str) -> list[dict[str, Any]]:
    """Parse one or more JSON objects from LLM output.

    LLMs sometimes emit multiple JSON objects in a single response
    (e.g. several tool_calls blocks followed by a final_result).
    Returns a list of parsed dicts, or an empty list if nothing parses.
    """
    cleaned = raw.strip()
    # Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # Fast path: single JSON object
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return [result]
        return []
    except json.JSONDecodeError:
        pass

    # Slow path: scan for top-level JSON objects by tracking brace depth
    objects: list[dict[str, Any]] = []
    i = 0
    while i < len(cleaned):
        if cleaned[i] == "{":
            depth = 0
            in_string = False
            escape_next = False
            start = i
            for j in range(i, len(cleaned)):
                ch = cleaned[j]
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    if in_string:
                        escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(cleaned[start : j + 1])
                            if isinstance(obj, dict):
                                objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                        i = j + 1
                        break
            else:
                # Unterminated brace — skip
                break
        else:
            i += 1

    return objects


def build_task_prompt(task: Task) -> str:
    """Build a standard prompt from a Task for LLM consumption.

    Includes prior attempt feedback when available (retry context).
    """
    parts = [
        f"# Task: {task.title}",
        f"\n## Description\n{task.description}",
    ]
    if task.acceptance_criteria_ids:
        parts.append(
            f"\n## Acceptance Criteria IDs\n{', '.join(task.acceptance_criteria_ids)}"
        )
    if task.skeleton_tests:
        parts.append("\n## Skeleton Tests (you MUST implement these)")
        for i, skel in enumerate(task.skeleton_tests, 1):
            parts.append(f"\n### Test {i}\n```python\n{skel}\n```")
    if task.attempt_feedback:
        parts.append("\n## Prior Attempt Feedback")
        parts.append(
            "The following feedback is from previous failed attempts. "
            "Use it to improve your output."
        )
        for fb in task.attempt_feedback:
            parts.append(f"\n### Attempt {fb.attempt} (score: {fb.score:.2f})")
            parts.append(fb.feedback)
            if fb.suggested_improvements:
                parts.append("**Suggested improvements**:")
                for imp in fb.suggested_improvements:
                    parts.append(f"- {imp}")
    return "\n".join(parts)
