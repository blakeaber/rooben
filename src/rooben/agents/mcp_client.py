"""MCP client — manages connections to MCP servers and provides tool invocation."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

import structlog

from rooben.spec.models import MCPServerConfig, MCPTransportType

log = structlog.get_logger()


def _check_mcp_installed() -> None:
    """Raise a clear error if the mcp package is not installed."""
    try:
        import mcp  # noqa: F401
    except ImportError:
        raise ImportError(
            "The 'mcp' package is required for MCP agent support. "
            "Install it with: pip install 'mcp[cli]'"
        )


class MCPToolInfo:
    """Describes a tool exposed by an MCP server."""

    def __init__(self, server_name: str, name: str, description: str, input_schema: dict[str, Any]):
        self.server_name = server_name
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_prompt_dict(self) -> dict[str, Any]:
        """Format for inclusion in an LLM prompt."""
        return {
            "server": self.server_name,
            "tool": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }


class MCPClient:
    """
    Manages connections to one or more MCP servers and invokes their tools.

    Usage::

        client = MCPClient(configs)
        async with client:
            tools = await client.list_tools()
            result = await client.call_tool("server-name", "tool-name", {"arg": "value"})
    """

    def __init__(self, configs: list[MCPServerConfig]):
        self._configs = configs
        self._sessions: dict[str, Any] = {}  # server_name → ClientSession
        self._exit_stack: AsyncExitStack | None = None
        self._dead_sessions: set[str] = set()

    async def __aenter__(self) -> MCPClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def connect(self) -> None:
        """Establish connections to all configured MCP servers."""
        _check_mcp_installed()
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        self._exit_stack = AsyncExitStack()

        for config in self._configs:
            try:
                if config.transport_type == MCPTransportType.STDIO:
                    if not config.command:
                        log.warning(
                            "mcp_client.skip_no_command",
                            server=config.name,
                        )
                        continue
                    from mcp import StdioServerParameters

                    server_params = StdioServerParameters(
                        command=config.command,
                        args=config.args,
                        env=config.env if config.env else None,
                    )
                    read_stream, write_stream = await self._exit_stack.enter_async_context(
                        stdio_client(server_params)
                    )
                elif config.transport_type == MCPTransportType.SSE:
                    if not config.url:
                        log.warning(
                            "mcp_client.skip_no_url",
                            server=config.name,
                        )
                        continue
                    from mcp.client.sse import sse_client

                    sse_kwargs: dict[str, Any] = {}
                    if config.headers:
                        sse_kwargs["headers"] = config.headers
                    read_stream, write_stream = await self._exit_stack.enter_async_context(
                        sse_client(config.url, **sse_kwargs)
                    )
                else:
                    log.warning(
                        "mcp_client.unknown_transport",
                        server=config.name,
                        transport=config.transport_type,
                    )
                    continue

                session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                self._sessions[config.name] = session
                log.info(
                    "mcp_client.connected",
                    server=config.name,
                    transport=config.transport_type.value,
                )

            except Exception as exc:
                log.error(
                    "mcp_client.connection_failed",
                    server=config.name,
                    error=str(exc),
                )

    async def list_tools(self) -> list[MCPToolInfo]:
        """Discover all tools from all connected servers."""
        tools: list[MCPToolInfo] = []
        for server_name, session in self._sessions.items():
            try:
                result = await session.list_tools()
                for tool in result.tools:
                    tools.append(
                        MCPToolInfo(
                            server_name=server_name,
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                        )
                    )
            except Exception as exc:
                log.error(
                    "mcp_client.list_tools_failed",
                    server=server_name,
                    error=str(exc),
                )
        return tools

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        """
        Call a tool on a specific MCP server.

        Returns the text content of the result, or an error message.
        If the session is dead, returns a [SESSION_DEAD] sentinel immediately.
        """
        if server_name in self._dead_sessions:
            return f"[SESSION_DEAD] MCP server '{server_name}' connection is dead"

        session = self._sessions.get(server_name)
        if session is None:
            return f"Error: MCP server '{server_name}' is not connected"

        try:
            result = await session.call_tool(tool_name, arguments)
            # Extract text from result content
            parts: list[str] = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                elif hasattr(content, "data"):
                    parts.append(f"[binary data: {len(content.data)} bytes]")
                else:
                    parts.append(str(content))

            output = "\n".join(parts) if parts else "(empty result)"

            if result.isError:
                return f"Tool error: {output}"
            return output

        except Exception as exc:
            if self._is_connection_dead(exc):
                self._dead_sessions.add(server_name)
                log.error(
                    "mcp_client.session_dead",
                    server=server_name,
                    error_type=type(exc).__name__,
                )
                return f"[SESSION_DEAD] MCP server '{server_name}' connection died: {exc}"

            log.error(
                "mcp_client.call_tool_failed",
                server=server_name,
                tool=tool_name,
                error=str(exc),
            )
            return f"Error calling tool '{tool_name}': {exc}"

    @staticmethod
    def _is_connection_dead(exc: Exception) -> bool:
        """Classify whether an exception indicates a dead/broken connection."""
        exc_type = type(exc).__name__

        # Broken pipe, connection reset, incomplete read
        dead_types = {
            "BrokenPipeError",
            "ConnectionResetError",
            "ConnectionRefusedError",
            "ConnectionAbortedError",
            "IncompleteReadError",
            "ConnectionError",
        }
        if exc_type in dead_types or isinstance(exc, ConnectionError):
            return True

        # Empty error string often means the SSE connection dropped
        if str(exc) == "":
            return True

        # Check for common connection-death messages
        msg = str(exc).lower()
        dead_phrases = [
            "broken pipe",
            "connection reset",
            "connection refused",
            "connection closed",
            "eof",
            "incomplete read",
            "stream ended",
        ]
        return any(phrase in msg for phrase in dead_phrases)

    async def reconnect_server(self, server_name: str) -> bool:
        """Attempt to reconnect a dead MCP server session.

        Returns True on success, False on failure.
        """
        config = next((c for c in self._configs if c.name == server_name), None)
        if config is None:
            log.error("mcp_client.reconnect_failed", server=server_name, error="config not found")
            return False

        log.info("mcp_client.reconnecting", server=server_name)

        # Close old session if it exists
        old_session = self._sessions.pop(server_name, None)
        if old_session is not None:
            try:
                # Best-effort close — session may already be broken
                pass
            except Exception:
                pass

        try:
            _check_mcp_installed()
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client

            # Need a fresh exit stack for the new connection
            if self._exit_stack is None:
                self._exit_stack = AsyncExitStack()

            if config.transport_type == MCPTransportType.STDIO:
                if not config.command:
                    log.error("mcp_client.reconnect_failed", server=server_name, error="no command")
                    return False
                from mcp import StdioServerParameters

                server_params = StdioServerParameters(
                    command=config.command,
                    args=config.args,
                    env=config.env if config.env else None,
                )
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
            elif config.transport_type == MCPTransportType.SSE:
                if not config.url:
                    log.error("mcp_client.reconnect_failed", server=server_name, error="no url")
                    return False
                from mcp.client.sse import sse_client

                sse_kwargs: dict[str, Any] = {}
                if config.headers:
                    sse_kwargs["headers"] = config.headers
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    sse_client(config.url, **sse_kwargs)
                )
            else:
                log.error("mcp_client.reconnect_failed", server=server_name, error="unknown transport")
                return False

            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            self._sessions[server_name] = session
            self._dead_sessions.discard(server_name)

            log.info("mcp_client.reconnected", server=server_name)
            return True

        except Exception as exc:
            log.error(
                "mcp_client.reconnect_failed",
                server=server_name,
                error=str(exc),
            )
            return False

    @property
    def dead_servers(self) -> set[str]:
        """Names of servers with dead connections."""
        return set(self._dead_sessions)

    async def close(self) -> None:
        """Close all MCP server connections."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._sessions.clear()

    @property
    def connected_servers(self) -> list[str]:
        """Names of currently connected servers."""
        return list(self._sessions.keys())
