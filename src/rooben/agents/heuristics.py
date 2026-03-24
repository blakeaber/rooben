"""Heuristic extractors for MCP agent scratchpad entries.

Each function is a named heuristic that extracts structured data from
unstructured agent output. They are intentionally simple and imperfect —
the goal is to capture useful signal, not achieve perfect recall.

These are separated from the accumulator so they can be tested, tuned,
and replaced independently.
"""

from __future__ import annotations

import re

_DECISION_KEYWORDS = re.compile(
    r"\b(because|chose|instead of|decided)\b|\b(plan|approach|decision|rationale):",
    re.IGNORECASE,
)

_WRITE_TOOLS = frozenset({"write_file", "create_file", "edit_file"})
_READ_TOOLS = frozenset({"read_file"})

_ERROR_PATTERNS = re.compile(
    r"(?:^|\b)(Error|error:|ENOENT|failed|Permission denied|EPERM|FileNotFoundError|IsADirectoryError)",
    re.MULTILINE,
)


def extract_decisions_from_llm_output(raw: str, max_decisions: int = 3) -> list[str]:
    """Extract decision rationale lines from an LLM assistant response.

    Heuristic: scans for lines containing planning/decision keywords
    ("because", "chose", "instead of", "plan:", "approach:", "decided")
    or numbered list items following a line that mentions "plan" or "steps".

    Known limitations:
    - Misses decisions expressed as implicit assumptions
    - May pick up incidental uses of keywords in code comments
    - Only captures explicit single-line rationales, not multi-sentence reasoning

    Returns up to max_decisions short excerpts (<=120 chars each).
    """
    if not raw:
        return []

    decisions: list[str] = []
    lines = raw.split("\n")
    in_plan_block = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            in_plan_block = False
            continue

        # Detect plan block headers
        lower = stripped.lower()
        if "plan" in lower or "steps" in lower:
            in_plan_block = True

        # Numbered items in a plan block
        if in_plan_block and re.match(r"^\d+[\.\)]\s", stripped):
            excerpt = stripped[:120]
            decisions.append(excerpt)
            if len(decisions) >= max_decisions:
                return decisions
            continue

        # Keyword match
        if _DECISION_KEYWORDS.search(stripped):
            # Skip lines that look like code (indented with spaces/tabs or contain common code patterns)
            if stripped.startswith(("{", "}", '"', "'")) or "import " in stripped:
                continue
            excerpt = stripped[:120]
            decisions.append(excerpt)
            if len(decisions) >= max_decisions:
                return decisions

    return decisions


def classify_tool_call(tool_name: str, arguments: dict) -> str:
    """Classify a tool call into a scratchpad category.

    Heuristic: maps tool names to entry categories:
    - write_file, create_file, edit_file -> "file_write"
    - read_file -> "file_read"
    - Everything else -> "tool_call"

    Returns the category string.
    """
    if tool_name in _WRITE_TOOLS:
        return "file_write"
    if tool_name in _READ_TOOLS:
        return "file_read"
    return "tool_call"


def extract_tool_outcome(tool_name: str, result_str: str, max_chars: int = 100) -> str:
    """Extract a concise outcome summary from a tool result.

    Heuristic: for write tools, extracts "Successfully wrote..." line.
    For errors, extracts first error line. Otherwise takes first max_chars.

    Returns a one-line outcome string.
    """
    if not result_str:
        return "(empty result)"

    # Check for errors first
    if is_error_result(result_str):
        for line in result_str.split("\n"):
            line = line.strip()
            if line and _ERROR_PATTERNS.search(line):
                return line[:max_chars]
        return result_str.split("\n")[0].strip()[:max_chars]

    # For write tools, look for success message
    if tool_name in _WRITE_TOOLS:
        for line in result_str.split("\n"):
            if "Successfully" in line or "wrote" in line.lower():
                return line.strip()[:max_chars]

    # Default: first line, truncated
    first_line = result_str.split("\n")[0].strip()
    if len(first_line) > max_chars:
        return first_line[:max_chars - 3] + "..."
    return first_line


def is_error_result(result_str: str) -> bool:
    """Detect whether a tool result indicates an error.

    Heuristic: checks for "Error", "error:", "ENOENT", "failed",
    "Permission denied" at line starts or after common prefixes.
    """
    if not result_str:
        return False
    return bool(_ERROR_PATTERNS.search(result_str))


# ---------------------------------------------------------------------------
# Tool capability taxonomy
# ---------------------------------------------------------------------------


class ToolCapability:
    """Semantic capability categories for MCP tools.

    Used to classify tools by their description (not name, which is arbitrary).
    For example, "Tavily" is a search tool despite the name not containing "search".
    """
    SEARCH = "search"           # URL/content discovery (Brave, Tavily, DuckDuckGo, etc.)
    FETCH = "fetch"             # HTTP content retrieval
    FILESYSTEM = "filesystem"   # File read/write
    SHELL = "shell"             # Command execution
    MEMORY = "memory"           # Persistent knowledge storage


_CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    ToolCapability.SEARCH: ["search", "query", "find results", "web results", "lookup"],
    ToolCapability.FETCH: ["fetch", "http", "download", "retrieve", "read url", "web page"],
    ToolCapability.FILESYSTEM: ["file", "read_file", "write_file", "directory", "create_file"],
    ToolCapability.SHELL: ["shell", "command", "execute", "run", "bash", "terminal"],
    ToolCapability.MEMORY: ["memory", "knowledge graph", "remember", "store knowledge"],
}


def classify_tool_capability(description: str) -> str | None:
    """Classify a tool into a capability category by its description.

    Heuristic: matches keywords against the tool's description text,
    not its name. This handles tools like "Tavily" that perform search
    but don't have "search" in their name.

    Returns the ToolCapability constant, or None if unclassified.
    """
    desc_lower = description.lower()
    for capability, keywords in _CAPABILITY_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return capability
    return None


def has_capability(tools: list, capability: str) -> bool:
    """Check if any tool in the list matches a capability category.

    Accepts MCPToolInfo objects (with .description attribute).
    """
    for tool in tools:
        desc = getattr(tool, "description", "")
        if classify_tool_capability(desc) == capability:
            return True
    return False


def is_research_capable(tools: list) -> bool:
    """True when tool set includes both search and fetch capabilities."""
    return (
        has_capability(tools, ToolCapability.SEARCH)
        and has_capability(tools, ToolCapability.FETCH)
    )


# ---------------------------------------------------------------------------
# Fetch failure detection
# ---------------------------------------------------------------------------

_FETCH_BLOCKED_PATTERNS = re.compile(
    r"(?:robots\.txt|403 Forbidden|Access Denied|Forbidden|"
    r"paywall|subscription required|sign.in.required)",
    re.IGNORECASE,
)


def is_fetch_blocked(tool_result: str) -> bool:
    """Check if a fetch tool result indicates the URL is blocked.

    Heuristic: scans the first 2000 chars for common block indicators
    (robots.txt, 403, paywall, etc.).
    """
    return bool(_FETCH_BLOCKED_PATTERNS.search(tool_result[:2000]))


# ---------------------------------------------------------------------------
# Research strategy prompt note
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Output feasibility estimation
# ---------------------------------------------------------------------------

CHARS_PER_PAGE = 2500  # ~500 words at 5 chars/word

_PAGE_PATTERN = re.compile(r"(\d+)[- ]?(?:page|pg)\b", re.IGNORECASE)
_WORD_PATTERN = re.compile(r"(\d[\d,]*)\s+words?\b", re.IGNORECASE)
_FILE_PATTERN = re.compile(
    r"(?:create|generate|produce)\s+(\d+)\s+(?:file|component|module|endpoint)",
    re.IGNORECASE,
)


def estimate_requested_output_chars(description: str) -> int:
    """Estimate requested output size in chars from a task description.

    Heuristic: scans for explicit size indicators (page counts, word counts,
    file counts) and returns the largest estimated char count. Returns 0 if
    no explicit size indicators are found.
    """
    max_chars = 0
    for match in _PAGE_PATTERN.finditer(description):
        max_chars = max(max_chars, int(match.group(1)) * CHARS_PER_PAGE)
    for match in _WORD_PATTERN.finditer(description):
        word_count = int(match.group(1).replace(",", ""))
        max_chars = max(max_chars, word_count * 5)  # ~5 chars/word
    for match in _FILE_PATTERN.finditer(description):
        max_chars = max(max_chars, int(match.group(1)) * 2000)  # ~2K chars/file avg
    return max_chars


RESEARCH_STRATEGY_NOTE = """\
## Research Strategy
1. ALWAYS search first to discover URLs before fetching. Run 3-5 varied queries.
2. From search results, select the 10-15 most promising URLs.
3. Prefer .com, .org, .gov, .edu — avoid known-paywalled academic databases.
4. If a fetch returns robots.txt, 403, or Access Denied: SKIP immediately.
   Do NOT retry the same URL or any other page on that domain.
5. After each failed fetch, search for the same information on alternative sites.
6. Track source count. Once you have enough successful sources, proceed to synthesis.
"""
