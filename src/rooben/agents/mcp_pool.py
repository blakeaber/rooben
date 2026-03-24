"""MCP connection pool — reuses long-lived MCP server subprocesses across tasks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import deque

import structlog

from rooben.agents.mcp_client import MCPClient, MCPToolInfo
from rooben.spec.models import MCPServerConfig

log = structlog.get_logger()

MAX_IDLE_AGE = 300  # 5 minutes — evict connections idle longer than this


def _config_key(configs: list[MCPServerConfig], workspace_dir: str | None = None) -> str:
    """Generate a stable key for a set of MCP configs + workspace."""
    data = json.dumps(
        [c.model_dump(mode="json") for c in sorted(configs, key=lambda c: c.name)],
        sort_keys=True,
    )
    if workspace_dir:
        data += f"|{workspace_dir}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


class PooledConnection:
    """A pooled MCP client with cached tool info."""

    def __init__(self, client: MCPClient, tools: list[MCPToolInfo], key: str):
        self.client = client
        self.tools = tools
        self.key = key
        self.in_use = False
        self.last_used: float = time.monotonic()


class MCPConnectionPool:
    """Pools long-lived MCP server subprocesses keyed by config hash.

    Agents check out connections, use them for the duration of a task,
    and check them back in for reuse by subsequent tasks.
    """

    def __init__(self, max_idle: int = 5) -> None:
        self._pools: dict[str, deque[PooledConnection]] = {}
        self._max_idle = max_idle
        self._lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()

    async def checkout(
        self, configs: list[MCPServerConfig]
    ) -> tuple[MCPClient, list[MCPToolInfo]]:
        """Get a connected MCP client, reusing from pool if available.

        Evicts connections that are stale (idle > MAX_IDLE_AGE) or have
        dead server sessions before returning them.
        """
        if not configs:
            return MCPClient([]), []

        key = _config_key(configs)

        async with self._lock:
            pool = self._pools.get(key)
            while pool:
                conn = pool.popleft()
                now = time.monotonic()

                # Evict stale connections
                age = now - conn.last_used
                if age > MAX_IDLE_AGE:
                    log.info(
                        "mcp_pool.evicted_stale",
                        key=key[:8],
                        age_seconds=round(age, 1),
                    )
                    await conn.client.close()
                    continue

                # Evict connections with dead servers
                if conn.client.dead_servers:
                    log.info(
                        "mcp_pool.evicted_dead",
                        key=key[:8],
                        dead_servers=list(conn.client.dead_servers),
                    )
                    await conn.client.close()
                    continue

                conn.in_use = True
                log.debug("mcp_pool.reused", key=key[:8], servers=len(configs))
                return conn.client, conn.tools

        # No pooled connection — create new one (serialized to avoid npm races)
        client = MCPClient(configs)
        async with self._connect_lock:
            await client.connect()
            tools = await client.list_tools()

        log.info(
            "mcp_pool.created",
            key=key[:8],
            servers=client.connected_servers,
            tools=len(tools),
        )
        return client, tools

    async def checkin(
        self, configs: list[MCPServerConfig], client: MCPClient, tools: list[MCPToolInfo]
    ) -> None:
        """Return a connection to the pool for reuse.

        Refuses to pool connections with dead servers — closes them instead.
        """
        if not configs:
            return

        key = _config_key(configs)

        # Don't pool connections with dead servers
        if client.dead_servers:
            log.info(
                "mcp_pool.refused_dead",
                key=key[:8],
                dead_servers=list(client.dead_servers),
            )
            await client.close()
            return

        async with self._lock:
            pool = self._pools.setdefault(key, deque())
            if len(pool) < self._max_idle:
                conn = PooledConnection(client=client, tools=tools, key=key)
                conn.last_used = time.monotonic()
                pool.append(conn)
                log.debug("mcp_pool.returned", key=key[:8])
                return

        # Pool full — close excess connection
        await client.close()
        log.debug("mcp_pool.closed_excess", key=key[:8])

    async def close_all(self) -> None:
        """Shut down all pooled connections."""
        async with self._lock:
            for key, pool in self._pools.items():
                for conn in pool:
                    try:
                        await conn.client.close()
                    except Exception as exc:
                        log.debug("mcp_pool.close_error", key=key[:8], error=str(exc))
                pool.clear()
            self._pools.clear()
        log.info("mcp_pool.closed_all")

    @property
    def stats(self) -> dict[str, int]:
        """Return pool statistics."""
        total = sum(len(pool) for pool in self._pools.values())
        return {"pools": len(self._pools), "idle_connections": total}
