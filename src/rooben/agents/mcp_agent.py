"""MCP agent — uses MCP server tools orchestrated by an LLM to execute tasks."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from rooben.agents.mcp_pool import MCPConnectionPool

from rooben.agents.heuristics import (
    classify_tool_call,
    extract_decisions_from_llm_output,
    extract_tool_outcome,
    is_error_result,
)
from rooben.agents.mcp_client import MCPClient, MCPToolInfo
from rooben.agents.scratchpad import ScratchpadAccumulator
from rooben.domain import ArtifactManifestEntry, GeneratedTest, Task, TaskResult, TokenUsage
from rooben.planning.provider import LLMProvider
from rooben.spec.models import MCPServerConfig
from rooben.utils import build_task_prompt, parse_llm_json, parse_llm_json_multi

log = structlog.get_logger()


@dataclass(frozen=True)
class AgentExecutionConfig:
    """Tuning knobs for the MCP agent execution loop."""

    max_continuation_rounds: int = 3
    compaction_threshold: int = 20_000       # token chars triggering context compaction
    backfill_total_budget: int = 200_000     # max chars for scratchpad backfill
    backfill_per_file: int = 50_000          # max chars per file in backfill
    max_write_calls_per_turn: int = 2        # enforce one-file-per-turn heuristic
    turn0_max_tokens: int = 12_288           # constrain first turn to force tool usage
    max_tool_result_chars: int = 12_000      # truncate individual tool results
    wrap_up_threshold: float = 0.8           # fraction of max_turns to inject wrap-up nudge
    compaction_retained_chars: int = 8_000   # max chars retained per message after compaction
    retry_max_tokens: int = 32_768           # escalated token limit after JSON parse failures

MCP_AGENT_SYSTEM_PROMPT = """\
You are an autonomous agent executing a task within a larger workflow.
You have access to external tools via MCP (Model Context Protocol) servers.

Your job:
1. Read the task description carefully.
2. Use the available tools to gather data, perform actions, or produce artifacts.
3. Produce the requested output (code, text, config, etc.).
4. If skeleton tests are provided, implement them fully so they pass.

## Available Tools

{tool_descriptions}

## How to Call Tools

When you need to call a tool, output JSON with a "tool_calls" array:
{{
  "tool_calls": [
    {{
      "server": "server-name",
      "tool": "tool-name",
      "arguments": {{"param": "value"}}
    }}
  ]
}}

## How to Return Final Results

When you have completed the task, output JSON with a "final_result" key:
{{
  "final_result": {{
    "output": "summary of what you produced",
    "artifacts": {{
      "filename.ext": "file content as string"
    }},
    "generated_tests": [
      {{
        "filename": "test_something.py",
        "content": "test code",
        "test_type": "unit",
        "framework": "pytest"
      }}
    ],
    "learnings": ["any discoveries that would help future tasks"]
  }}
}}

## Output Rules

1. Write ONE file per tool_calls response. After each write, STOP and wait for
   confirmation before writing the next file. Do NOT batch multiple write_file
   calls in a single response.
2. NEVER include file contents in your final_result artifacts — write all files
   to disk first, then return final_result with a summary and empty artifacts.
3. Your output token limit is {max_tokens} tokens (~{max_chars} characters).
   Plan your output to fit. If a task requires multiple files, write them one
   at a time across multiple turns.
4. Start by making a plan (list files you'll create), then write them sequentially.
5. Before writing a file, ensure ALL parent directories exist. The create_directory
   tool only creates ONE level at a time. For nested paths like /workspace/src/api/models/,
   you must create each directory sequentially: /workspace/src, /workspace/src/api,
   /workspace/src/api/models.
{research_note}{workspace_note}
IMPORTANT: Output ONLY JSON in each response. No markdown fences, no commentary.
Either output tool_calls to invoke tools, or final_result when done.
"""

NO_TOOLS_SYSTEM_PROMPT = """\
You are an autonomous agent executing a task within a larger workflow.

NOTE: MCP servers were configured but no tools are currently available.
Proceed with the task using your own knowledge.

Output strict JSON:
{{
  "final_result": {{
    "output": "summary of what you produced",
    "artifacts": {{
      "filename.ext": "file content as string"
    }},
    "generated_tests": [],
    "learnings": []
  }}
}}

Output ONLY the JSON object. No markdown fences, no commentary.
"""


class MCPAgent:
    """
    Executes tasks using MCP server tools, driven by an LLM.

    The agent operates in an agentic loop:
    1. Connects to configured MCP servers and discovers available tools.
    2. Sends the task + tool descriptions to the LLM.
    3. The LLM decides which tools to call (or outputs final result).
    4. Tool calls are executed and results fed back to the LLM.
    5. Repeats until the LLM produces a final result or max_turns is reached.
    """

    # Serialize MCP server connections to avoid npx/npm cache lock contention
    # when multiple agents spawn subprocess-based servers concurrently.
    _connect_lock: asyncio.Lock | None = None

    @classmethod
    def _get_connect_lock(cls) -> asyncio.Lock:
        """Lazily create the connection lock within the current event loop."""
        if cls._connect_lock is None:
            cls._connect_lock = asyncio.Lock()
        return cls._connect_lock

    def __init__(
        self,
        agent_id: str,
        mcp_configs: list[MCPServerConfig],
        llm_provider: LLMProvider,
        max_turns: int = 25,
        max_tokens: int = 16384,
        connection_pool: MCPConnectionPool | None = None,
        execution_config: AgentExecutionConfig | None = None,
    ):
        self._agent_id = agent_id
        self._mcp_configs = mcp_configs
        self._provider = llm_provider
        self._max_turns = max_turns
        self._max_tokens = max_tokens
        self._pool = connection_pool
        self._config = execution_config or AgentExecutionConfig()

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def execute(self, task: Task) -> TaskResult:
        start = time.monotonic()

        # When no MCP servers configured, run agentic loop without tools
        if not self._mcp_configs:
            log.info("mcp_agent.no_servers", agent_id=self._agent_id)
            return await self._agentic_loop(task, client=None, tools=[], start=start)

        # Use connection pool if available (R-3.6)
        if self._pool is not None:
            return await self._execute_pooled(task, start)

        # Fallback: per-task connection with serialization lock
        client = MCPClient(self._mcp_configs)
        try:
            async with self._get_connect_lock():
                await client.connect()
                tools = await client.list_tools()
                log.info(
                    "mcp_agent.connected",
                    agent_id=self._agent_id,
                    servers=client.connected_servers,
                    tools=len(tools),
                )
        except Exception as exc:
            log.error("mcp_agent.connect_failed", agent_id=self._agent_id, error=str(exc))
            return TaskResult(
                error=f"MCP connection failed: {exc}",
                wall_seconds=time.monotonic() - start,
            )

        try:
            result = await self._agentic_loop(task, client, tools, start)
        finally:
            await client.close()

        return result

    async def _execute_pooled(self, task: Task, start: float) -> TaskResult:
        """Execute using the connection pool."""
        pool: MCPConnectionPool = self._pool  # type: ignore[assignment]

        try:
            client, tools = await pool.checkout(self._mcp_configs)
            log.info(
                "mcp_agent.pool_checkout",
                agent_id=self._agent_id,
                tools=len(tools),
            )
        except Exception as exc:
            if "cancel scope" in str(exc).lower():
                # anyio cancel scope bug across async task boundaries —
                # fall back to a direct (non-pooled) connection.
                log.warning(
                    "mcp_agent.pool_cancel_scope_fallback",
                    agent_id=self._agent_id,
                )
                client = MCPClient(self._mcp_configs)
                async with self._get_connect_lock():
                    await client.connect()
                    tools = await client.list_tools()
                try:
                    return await self._agentic_loop(task, client, tools, start)
                finally:
                    await client.close()
            log.error("mcp_agent.pool_checkout_failed", agent_id=self._agent_id, error=str(exc))
            return TaskResult(
                error=f"MCP pool checkout failed: {exc}",
                wall_seconds=time.monotonic() - start,
            )

        try:
            result = await self._agentic_loop(task, client, tools, start)
        finally:
            # Don't pool connections with dead servers — close instead
            if client.dead_servers:
                log.info(
                    "mcp_agent.closing_dead_connection",
                    agent_id=self._agent_id,
                    dead_servers=list(client.dead_servers),
                )
                try:
                    await client.close()
                except Exception:
                    pass
            else:
                try:
                    await pool.checkin(self._mcp_configs, client, tools)
                except Exception:
                    log.debug("mcp_agent.checkin_failed", agent_id=self._agent_id, exc_info=True)

        return result

    async def _agentic_loop(
        self,
        task: Task,
        client: MCPClient | None,
        tools: list[MCPToolInfo],
        start: float,
    ) -> TaskResult:
        """Run the LLM ↔ tool-call loop until a final result is produced."""
        system_prompt = self._build_system_prompt(tools)
        # Multi-turn message list: alternating user/assistant messages
        messages: list[dict[str, str]] = [
            {"role": "user", "content": self._build_task_prompt(task)},
        ]
        accumulated_usage = TokenUsage()
        truncation_fragments: list[str] = []
        nudge_fragment: str | None = None  # Stashed fragment from tool-nudge turn
        written_files: list[str] = []  # Paths written via filesystem write_file tool
        scratchpad = ScratchpadAccumulator(
            workspace_dir=self._extract_workspace_dir()
        )

        post_nudge = False  # Track if we just cleared a nudge
        invalid_json_count = 0  # Track consecutive invalid JSON responses

        # Check if provider supports multi-turn
        has_multi = hasattr(self._provider, "generate_multi")

        _wrap_up_sent = False

        for turn in range(self._max_turns):
            # Turn budget warning — tell agent to wrap up before hitting the limit
            if (
                not _wrap_up_sent
                and turn >= int(self._max_turns * self._config.wrap_up_threshold)
                and client is not None
            ):
                _wrap_up_sent = True
                remaining = self._max_turns - turn
                messages.append({"role": "user", "content": (
                    f"[SYSTEM] You have {remaining} turns remaining before the turn limit. "
                    "STOP gathering data and produce your final_result NOW. "
                    "Synthesize everything you have collected so far into the final output."
                )})
                log.info("mcp_agent.wrap_up_nudge", turn=turn, remaining=remaining)

            # Compact old messages if context is too large
            msg_texts = [m["content"] for m in messages]
            if self._estimate_tokens(msg_texts) > self._config.compaction_threshold:
                if scratchpad.has_entries and client is not None:
                    await self._flush_scratchpad(client, scratchpad)
                messages = self._compact_messages(messages, scratchpad)
                msg_texts = [m["content"] for m in messages]
                log.info("mcp_agent.conversation_compacted", turn=turn)

            # Dynamic max_tokens: don't exceed context window
            input_estimate = self._estimate_tokens(msg_texts) + self._estimate_tokens([system_prompt])
            effective_max = max(4096, min(self._max_tokens, 200_000 - input_estimate - 5000))
            # Turn 0: constrain output to force tool usage instead of dumping content
            if turn == 0 and client is not None:
                effective_max = min(effective_max, self._config.turn0_max_tokens)
            # Post-nudge escalation: give extra room for tool_calls JSON
            if post_nudge:
                effective_max = min(self._max_tokens * 2, self._config.retry_max_tokens)
                post_nudge = False

            try:
                if has_multi:
                    gen_result = await self._provider.generate_multi(
                        system=system_prompt,
                        messages=messages,
                        max_tokens=effective_max,
                    )
                else:
                    # Fallback: concatenate all messages into single prompt
                    prompt = "\n\n---\n\n".join(m["content"] for m in messages)
                    gen_result = await self._provider.generate(
                        system=system_prompt,
                        prompt=prompt,
                        max_tokens=effective_max,
                    )
            except asyncio.TimeoutError:
                log.error("mcp_agent.llm_timeout", turn=turn, agent_id=self._agent_id)
                return TaskResult(
                    error=f"LLM generation timed out on turn {turn}. Prompt may be too large.",
                    token_usage=accumulated_usage.total,
                    token_usage_detailed=accumulated_usage,
                    wall_seconds=time.monotonic() - start,
                )
            except Exception as exc:
                log.error("mcp_agent.llm_failed", turn=turn, error=str(exc))
                return TaskResult(
                    error=f"LLM generation failed on turn {turn}: {exc}",
                    token_usage=accumulated_usage.total,
                    token_usage_detailed=accumulated_usage,
                    wall_seconds=time.monotonic() - start,
                )

            accumulated_usage = accumulated_usage + gen_result.usage
            raw = gen_result.text

            # Handle truncation: if response was cut off, ask LLM to continue
            if gen_result.truncated:
                log.warning("mcp_agent.truncated", turn=turn, length=len(raw))

                # Guard: cap continuation attempts
                if len(truncation_fragments) >= self._config.max_continuation_rounds:
                    log.error("mcp_agent.max_continuations", turn=turn)
                    scratchpad.record_error(turn, "Max continuation rounds exceeded")
                    truncation_fragments.append(raw)
                    combined = "".join(truncation_fragments)
                    truncation_fragments.clear()
                    data = self._parse_json(combined) or self._try_repair_json(combined)
                    if data and "final_result" in data:
                        return self._build_task_result(data["final_result"], start, accumulated_usage)
                    return TaskResult(
                        output=combined[:5000],
                        error="Response exceeded maximum continuation rounds",
                        token_usage=accumulated_usage.total,
                        token_usage_detailed=accumulated_usage,
                        wall_seconds=time.monotonic() - start,
                    )

                has_tools = client is not None and len(tools) > 0

                if has_tools and not truncation_fragments and nudge_fragment is None:
                    # First truncation for tool-equipped agent: nudge to use tools
                    nudge_fragment = raw  # Stash in case nudge fails
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content":
                        "STOP. Your response was truncated because it exceeded the token limit. "
                        "Do NOT include large file contents in your JSON response. "
                        "Instead, use your filesystem tools to write files to disk, "
                        "then return a final_result with just a summary and empty artifacts."
                    })
                    continue
                else:
                    # No tools, or nudge already failed: accumulate fragments
                    if nudge_fragment is not None:
                        truncation_fragments.append(nudge_fragment)
                        nudge_fragment = None
                    truncation_fragments.append(raw)
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content":
                        "Your previous response was truncated at the token limit. "
                        "Output ONLY the remaining text from exactly where you stopped. "
                        "Do not repeat any text. Do not add preamble. "
                        "Continue the JSON from the exact cutoff point."
                    })
                    continue

            # Non-truncated response: clear nudge state
            if nudge_fragment is not None:
                post_nudge = True
            nudge_fragment = None

            # Concatenate accumulated fragments if this completes a truncated sequence
            if truncation_fragments:
                truncation_fragments.append(raw)
                raw = "".join(truncation_fragments)
                truncation_fragments.clear()
                log.info("mcp_agent.fragments_joined", turn=turn, total_length=len(raw))

            # Parse LLM response — handle single or multi-JSON responses
            blocks = parse_llm_json_multi(raw)
            if not blocks:
                # Try single-object parse with repair fallback
                data = self._parse_json(raw)
                if data is None:
                    data = self._try_repair_json(raw)
                    if data is not None:
                        log.info("mcp_agent.json_repaired", turn=turn)
                if data is None:
                    invalid_json_count += 1
                    scratchpad.record_error(turn, f"Invalid JSON response: {raw[:100]}")
                    if invalid_json_count > 2:
                        log.warning("mcp_agent.invalid_json_exhausted", turn=turn)
                        return TaskResult(
                            output=raw[:5000],
                            token_usage=accumulated_usage.total,
                            token_usage_detailed=accumulated_usage,
                            wall_seconds=time.monotonic() - start,
                        )
                    log.warning("mcp_agent.invalid_json", turn=turn, raw=raw[:200])
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": (
                        "Your response was not valid JSON. Remember: output ONLY a JSON object "
                        "with either a \"tool_calls\" array or a \"final_result\" object. "
                        "No markdown, no prose. Try again."
                    )})
                    continue
                blocks = [data]

            if len(blocks) > 1:
                log.info("mcp_agent.multi_json", turn=turn, count=len(blocks))

            # Extract decisions from LLM output
            for rationale in extract_decisions_from_llm_output(raw):
                scratchpad.record_decision(turn, rationale)

            # Process all blocks: execute tool calls, collect final_result
            final_data: dict[str, Any] | None = None
            executed_tools = False
            for block in blocks:
                if "tool_calls" in block and client is not None:
                    tool_results, new_files = await self._execute_tool_calls(
                        client, block["tool_calls"]
                    )
                    written_files.extend(new_files)

                    # Record each tool call in scratchpad
                    for call in block["tool_calls"]:
                        t_server = call.get("server", "")
                        t_tool = call.get("tool", "")
                        t_args = call.get("arguments", {})
                        category = classify_tool_call(t_tool, t_args)
                        outcome = extract_tool_outcome(t_tool, tool_results)
                        if category == "file_write":
                            purpose = t_args.get("purpose", "")
                            scratchpad.record_file_write(turn, t_args.get("path", t_tool), purpose)
                        elif category == "file_read":
                            scratchpad.record_file_read(turn, t_args.get("path", t_tool))
                        else:
                            scratchpad.record_tool_call(turn, t_server, t_tool, outcome)
                        # Record errors from tool results
                        if is_error_result(tool_results):
                            scratchpad.record_error(turn, extract_tool_outcome(t_tool, tool_results))

                    # Add assistant response then tool results as user message
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": f"Tool results:\n{tool_results}"})
                    executed_tools = True
                elif "final_result" in block:
                    final_data = block

            if final_data is not None:
                result = self._build_task_result(final_data["final_result"], start, accumulated_usage)
                # Backfill artifacts from files written via MCP tools
                if written_files and client is not None:
                    await self._backfill_artifacts(client, result, written_files)
                # Build file manifest (authoritative record of produced files)
                if written_files:
                    self._build_file_manifest(result, written_files)
                return result

            if executed_tools:
                continue

            # Single block, unexpected structure — treat as final
            log.warning("mcp_agent.unexpected_response", turn=turn, keys=list(blocks[0].keys()))
            return self._build_task_result(blocks[0], start, accumulated_usage)

        # Max turns reached
        log.warning("mcp_agent.max_turns_reached", agent_id=self._agent_id, turns=self._max_turns)
        return TaskResult(
            output="Max tool-call turns reached without producing final result",
            error="Exceeded maximum agentic loop turns",
            token_usage=accumulated_usage.total,
            token_usage_detailed=accumulated_usage,
            wall_seconds=time.monotonic() - start,
        )

    @staticmethod
    def _estimate_tokens(parts: list[str]) -> int:
        """Conservative token estimate: ~3 chars per token for code/JSON-heavy content."""
        return sum(len(s) for s in parts) // 3

    def _compact_messages(
        self,
        messages: list[dict[str, str]],
        scratchpad: ScratchpadAccumulator | None = None,
    ) -> list[dict[str, str]]:
        """Compact multi-turn messages, keeping first and last 2, summarizing middle."""
        if len(messages) <= 4:
            return messages

        first = messages[0]  # Initial task prompt (user)
        last_two = messages[-2:]  # Most recent context

        # Use scratchpad summary if available; otherwise fall back to message parsing
        if scratchpad is not None and scratchpad.has_entries:
            summary = scratchpad.to_compact_summary()
        else:
            middle = messages[1:-2]
            summary = self._build_fallback_summary(middle)

        # Truncate retained messages to prevent compacted result from still being too large
        max_retained_chars = self._config.compaction_retained_chars
        last_two_trimmed = []
        for msg in last_two:
            content = msg["content"]
            if len(content) > max_retained_chars:
                content = content[:max_retained_chars] + "\n... [truncated for context management]"
            last_two_trimmed.append({"role": msg["role"], "content": content})

        # Build compacted message list — ensure user/assistant alternation
        result = [first]
        # If first is user and last_two starts with user, need assistant between
        if last_two_trimmed[0]["role"] == "user":
            result.append({"role": "assistant", "content": summary})
        else:
            result.append({"role": "user", "content": summary})
        result.extend(last_two_trimmed)

        # Validate alternation: merge consecutive same-role messages
        return self._fix_message_alternation(result)

    @staticmethod
    def _build_fallback_summary(middle: list[dict[str, str]]) -> str:
        """Build a compaction summary by parsing raw messages (legacy fallback)."""
        files_written: list[str] = []
        errors: list[str] = []
        tool_count = 0

        for msg in middle:
            content = msg["content"]
            if "Tool results:" in content:
                tool_count += 1
                for line in content.split("\n"):
                    if "write_file" in line and "Successfully" in line:
                        if "wrote to" in line:
                            path = line.split("wrote to")[-1].strip()
                            files_written.append(path)
            if "error" in content.lower() and msg["role"] == "user":
                for line in content.split("\n"):
                    if "error" in line.lower():
                        errors.append(line.strip()[:100])
                        break

        summary_parts = ["[Conversation compacted — prior turns summarized]"]
        if files_written:
            unique_files = list(dict.fromkeys(files_written))[:20]
            summary_parts.append(f"Files written so far: {', '.join(unique_files)}")
        if errors:
            summary_parts.append(f"Errors encountered: {'; '.join(errors[:3])}")
        summary_parts.append(f"Tool interactions: {tool_count}")

        return "\n".join(summary_parts)

    @staticmethod
    def _fix_message_alternation(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Ensure messages alternate user/assistant. Merge consecutive same-role."""
        if not messages:
            return messages
        fixed: list[dict[str, str]] = [messages[0]]
        for msg in messages[1:]:
            if msg["role"] == fixed[-1]["role"]:
                # Merge into previous
                fixed[-1] = {
                    "role": msg["role"],
                    "content": fixed[-1]["content"] + "\n\n" + msg["content"],
                }
            else:
                fixed.append(msg)
        return fixed

    async def _call_tool_with_retry(
        self,
        client: MCPClient,
        server: str,
        tool: str,
        arguments: dict[str, Any],
        max_retries: int = 2,
    ) -> str:
        """Call an MCP tool with automatic reconnection on dead sessions.

        If the result indicates a dead session ([SESSION_DEAD]),
        attempts to reconnect the server and retry the call.
        Falls back to a fresh pool connection if reconnection fails.
        """
        result = await client.call_tool(server, tool, arguments)

        if not str(result).startswith("[SESSION_DEAD]"):
            return result

        # Session is dead — attempt reconnection
        log.warning(
            "mcp_agent.tool_session_dead",
            agent_id=self._agent_id,
            server=server,
            tool=tool,
        )

        for attempt in range(max_retries):
            reconnected = await client.reconnect_server(server)
            if reconnected:
                log.info(
                    "mcp_agent.tool_reconnected",
                    agent_id=self._agent_id,
                    server=server,
                    attempt=attempt + 1,
                )
                result = await client.call_tool(server, tool, arguments)
                if not str(result).startswith("[SESSION_DEAD]"):
                    return result

        # Reconnection failed — try pool checkout if available
        if self._pool is not None:
            pool: MCPConnectionPool = self._pool  # type: ignore[assignment]
            try:
                new_client, _ = await pool.checkout(self._mcp_configs)
                result = await new_client.call_tool(server, tool, arguments)
                log.info(
                    "mcp_agent.tool_pool_fallback",
                    agent_id=self._agent_id,
                    server=server,
                )
                # We can't swap the client reference mid-loop, so just return the result
                return result
            except Exception as exc:
                log.error(
                    "mcp_agent.tool_pool_fallback_failed",
                    agent_id=self._agent_id,
                    error=str(exc),
                )

        return result

    async def _execute_tool_calls(
        self, client: MCPClient, tool_calls: list[dict[str, Any]]
    ) -> tuple[str, list[str]]:
        """Execute a batch of tool calls and format results.

        Enforces self._config.max_write_calls_per_turn to prevent the model from
        batching too many file writes in a single response. Excess write
        calls are skipped with a message telling the agent to continue.

        Returns (formatted_results, list_of_written_file_paths).
        """
        results: list[str] = []
        written_files: list[str] = []
        write_count = 0
        deferred_count = 0
        for i, call in enumerate(tool_calls):
            server = call.get("server", "")
            tool = call.get("tool", "")
            arguments = call.get("arguments", {})

            # Enforce write limit per turn
            is_write = tool in ("write_file", "create_file", "edit_file")
            if is_write:
                write_count += 1
                if write_count > self._config.max_write_calls_per_turn:
                    deferred_count += 1
                    continue  # Skip — will be prompted to continue

            log.info(
                "mcp_agent.calling_tool",
                agent_id=self._agent_id,
                server=server,
                tool=tool,
            )

            result = await self._call_tool_with_retry(client, server, tool, arguments)

            # Auto-create parent directories on write failure
            if is_write and "Parent directory does not exist" in str(result) and "path" in arguments:
                parent = "/".join(arguments["path"].split("/")[:-1])
                if parent:
                    await self._ensure_directories(client, server, parent)
                    result = await self._call_tool_with_retry(client, server, tool, arguments)

            # Auto-create parent directories for create_directory failure
            if tool == "create_directory" and "Parent directory does not exist" in str(result) and "path" in arguments:
                await self._ensure_directories(client, server, arguments["path"])
                result = "Successfully created directory (with parents)"

            # Annotate blocked fetch results so the agent skips immediately
            result_str = str(result)
            from rooben.agents.heuristics import is_fetch_blocked
            if server == "fetch" and is_fetch_blocked(result_str):
                result_str += (
                    "\n[SYSTEM] This URL/domain is blocked. "
                    "Skip it and search for alternative sources."
                )

            # Truncate oversized tool results to prevent context explosion
            if len(result_str) > self._config.max_tool_result_chars:
                half = self._config.max_tool_result_chars // 2
                result_str = (
                    result_str[:half]
                    + f"\n\n... [truncated {len(result_str) - self._config.max_tool_result_chars} chars] ...\n\n"
                    + result_str[-half:]
                )
            results.append(f"[{i + 1}] {server}/{tool}: {result_str}")

            # Track files written via filesystem tools
            if tool in ("write_file", "create_file") and "path" in arguments:
                written_files.append(arguments["path"])

        if deferred_count > 0:
            log.info("mcp_agent.writes_deferred", count=deferred_count)
            results.append(
                f"\n[SYSTEM] {deferred_count} additional write calls were deferred. "
                "Write ONE file per turn. Continue writing the remaining files."
            )

        return "\n\n".join(results), written_files

    async def _ensure_directories(
        self, client: MCPClient, server: str, dir_path: str
    ) -> None:
        """Create directory and all parents, one level at a time."""
        parts = dir_path.split("/")
        for i in range(1, len(parts) + 1):
            partial = "/".join(parts[:i])
            if not partial:
                continue
            try:
                await client.call_tool(server, "create_directory", {"path": partial})
            except Exception:
                pass  # Directory may already exist

    async def _backfill_artifacts(
        self, client: MCPClient, result: TaskResult, written_files: list[str]
    ) -> None:
        """Read files written via MCP tools back into result.artifacts.

        This ensures the verifier can see what the agent actually produced,
        even when files were written to disk instead of returned in artifacts.
        Enforces per-file and total budget limits to prevent context explosion.
        """
        total_chars = 0
        for path in written_files:
            if path in result.artifacts:
                continue  # Already present
            if total_chars >= self._config.backfill_total_budget:
                result.artifacts[path] = "(content omitted — total artifact budget exceeded)"
                continue
            try:
                content = await client.call_tool("filesystem", "read_file", {"path": path})
                if len(content) > self._config.backfill_per_file:
                    content = content[:self._config.backfill_per_file] + "\n... (truncated)"
                total_chars += len(content)
                result.artifacts[path] = content
            except Exception as exc:
                log.debug("mcp_agent.backfill_read_failed", path=path, error=str(exc))

    def _build_file_manifest(
        self, result: TaskResult, written_files: list[str]
    ) -> None:
        """Populate result.file_manifest from written_files paths.

        Uses os.stat() for sizes. Caps at 500 entries. This is separate
        from backfill — manifest records what exists without reading content.
        """
        import os
        _MAX_MANIFEST_ENTRIES = 500
        seen: set[str] = set()

        for path in written_files:
            if path in seen or len(result.file_manifest) >= _MAX_MANIFEST_ENTRIES:
                break
            seen.add(path)
            try:
                stat = os.stat(path)
                ext = os.path.splitext(path)[1].lstrip(".")
                result.file_manifest.append(ArtifactManifestEntry(
                    path=path,
                    size_bytes=stat.st_size,
                    file_type=ext,
                ))
            except OSError:
                # File may be inside a container — record with size 0
                ext = os.path.splitext(path)[1].lstrip(".")
                result.file_manifest.append(ArtifactManifestEntry(
                    path=path,
                    size_bytes=0,
                    file_type=ext,
                ))

    def _build_system_prompt(self, tools: list[MCPToolInfo]) -> str:
        """Build the system prompt with available tool descriptions."""
        if not tools:
            return NO_TOOLS_SYSTEM_PROMPT

        from rooben.agents.heuristics import RESEARCH_STRATEGY_NOTE, is_research_capable

        tool_descriptions = json.dumps(
            [t.to_prompt_dict() for t in tools],
            indent=2,
        )

        # Extract workspace directory from filesystem MCP server config
        workspace_note = ""
        workspace_dir = self._extract_workspace_dir()
        if workspace_dir:
            workspace_note = (
                f"\nIMPORTANT: Your workspace directory is: {workspace_dir}\n"
                "ALL file paths MUST use absolute paths within this directory.\n"
                "Do NOT call list_allowed_directories — you already know the workspace path.\n"
                "When using the shell execute_command tool, ALWAYS prefix your command with:\n"
                f"  cd {workspace_dir} && <your command>\n"
                "Start writing files immediately using this path as the root."
            )

        # Inject research strategy when agent has both search + fetch tools
        research_note = RESEARCH_STRATEGY_NOTE if is_research_capable(tools) else ""

        return MCP_AGENT_SYSTEM_PROMPT.format(
            tool_descriptions=tool_descriptions,
            workspace_note=workspace_note,
            research_note=research_note,
            max_tokens=self._max_tokens,
            max_chars=self._max_tokens * 4,
        )

    def _build_task_prompt(self, task: Task) -> str:
        """Build the initial task prompt."""
        return task.enriched_prompt or build_task_prompt(task)

    def _parse_json(self, raw: str) -> dict[str, Any] | None:
        """Try to parse JSON from LLM output, stripping markdown fences."""
        return parse_llm_json(raw)

    def _try_repair_json(self, raw: str) -> dict[str, Any] | None:
        """Attempt to repair truncated JSON by trying common closing sequences."""
        cleaned = raw.strip()
        # Strip markdown fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n", 1)
            cleaned = lines[1] if len(lines) > 1 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].rstrip()

        for suffix in ["}", '"}', '"}}', '"}]}', '"]}}']:
            try:
                result = json.loads(cleaned + suffix)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                continue
        return None

    def _build_task_result(
        self, data: dict[str, Any], start: float, usage: TokenUsage
    ) -> TaskResult:
        """Convert parsed JSON into a TaskResult."""
        generated_tests = [
            GeneratedTest(**t) for t in data.get("generated_tests", [])
        ]
        return TaskResult(
            output=data.get("output", ""),
            artifacts=data.get("artifacts", {}),
            generated_tests=generated_tests,
            learnings=data.get("learnings", []),
            token_usage=usage.total,
            token_usage_detailed=usage,
            wall_seconds=time.monotonic() - start,
        )

    def _extract_workspace_dir(self) -> str | None:
        """Extract workspace directory from MCP server configs.

        Checks stdio configs (cfg.args[-1]) and gateway/SSE configs
        (X-MCP-Args header) for the filesystem server's allowed directory.
        """
        for cfg in self._mcp_configs:
            if "filesystem" not in cfg.name:
                continue
            # Stdio transport: last arg is typically the allowed directory
            if cfg.args:
                return cfg.args[-1]
            # Gateway/SSE: check headers
            if hasattr(cfg, "headers") and cfg.headers:
                mcp_args = cfg.headers.get("X-MCP-Args", "")
                if mcp_args:
                    # X-MCP-Args is comma-separated; last entry is the dir
                    parts = [p.strip() for p in mcp_args.split(",")]
                    if parts:
                        return parts[-1]
        return None

    async def _flush_scratchpad(
        self, client: MCPClient, scratchpad: ScratchpadAccumulator
    ) -> None:
        """Write scratchpad to disk via the agent's MCP filesystem tools.

        Fire-and-forget — failure is non-fatal.
        """
        path = scratchpad.scratchpad_path
        if not path:
            return
        try:
            fs_server = next(
                (c.name for c in self._mcp_configs if "filesystem" in c.name), None
            )
            if fs_server:
                await client.call_tool(fs_server, "write_file", {
                    "path": path,
                    "content": scratchpad.to_markdown(),
                })
                scratchpad._flushed = True
        except Exception as exc:
            log.debug("mcp_agent.scratchpad_flush_failed", error=str(exc))

    async def health_check(self) -> bool:
        """Check connectivity to MCP servers and LLM provider."""
        if not self._mcp_configs:
            # No servers — health is just LLM availability
            try:
                await self._provider.generate(
                    system="Reply with 'ok'.",
                    prompt="health check",
                    max_tokens=10,
                )
                return True
            except Exception:
                return False
        try:
            client = MCPClient(self._mcp_configs)
            await client.connect()
            connected = len(client.connected_servers) > 0
            await client.close()
            return connected
        except Exception:
            return False
