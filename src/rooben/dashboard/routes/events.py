"""WebSocket event broadcast for live updates + per-workflow SSE subscriptions."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from rooben.dashboard.auth import validate_ws_token

router = APIRouter()


class EventBroadcaster:
    """Manages WebSocket connections and per-workflow SSE subscriptions."""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._workflow_queues: dict[str, list[asyncio.Queue]] = {}
        self._queue_lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, event: dict) -> None:
        """Send event to all connected WebSocket clients and matching SSE subscribers."""
        message = json.dumps(event, default=str)

        # WebSocket broadcast
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.discard(ws)

        # Per-workflow SSE dispatch
        workflow_id = event.get("workflow_id")
        if workflow_id:
            async with self._queue_lock:
                queues = self._workflow_queues.get(workflow_id, [])
                dead_queues = []
                for q in queues:
                    try:
                        q.put_nowait(event)
                    except asyncio.QueueFull:
                        dead_queues.append(q)
                for q in dead_queues:
                    queues.remove(q)

    async def subscribe(self, workflow_id: str) -> AsyncGenerator[dict, None]:
        """Subscribe to events for a specific workflow via SSE."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._queue_lock:
            if workflow_id not in self._workflow_queues:
                self._workflow_queues[workflow_id] = []
            self._workflow_queues[workflow_id].append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                # Stop on terminal events
                event_type = event.get("type", "")
                if event_type == "workflow.completed":
                    break
        finally:
            async with self._queue_lock:
                queues = self._workflow_queues.get(workflow_id, [])
                if queue in queues:
                    queues.remove(queue)
                if not queues:
                    self._workflow_queues.pop(workflow_id, None)

    async def broadcast_channel(self, channel: str, event: dict) -> None:
        """Send event to subscribers of a named channel."""
        async with self._queue_lock:
            queues = self._workflow_queues.get(f"ch:{channel}", [])
            dead_queues = []
            for q in queues:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.append(q)
            for q in dead_queues:
                queues.remove(q)

    async def subscribe_channel(self, channel: str) -> AsyncGenerator[dict, None]:
        """Subscribe to events on a named channel."""
        key = f"ch:{channel}"
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._queue_lock:
            if key not in self._workflow_queues:
                self._workflow_queues[key] = []
            self._workflow_queues[key].append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            async with self._queue_lock:
                queues = self._workflow_queues.get(key, [])
                if queue in queues:
                    queues.remove(queue)
                if not queues:
                    self._workflow_queues.pop(key, None)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Global broadcaster instance
broadcaster = EventBroadcaster()


@router.websocket("/ws/events")
async def websocket_events(ws: WebSocket, token: str | None = Query(default=None)):
    if not validate_ws_token(token):
        await ws.close(code=4001, reason="Invalid token")
        return

    await broadcaster.connect(ws)
    try:
        while True:
            # Keep connection alive, handle client pings
            await ws.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(ws)
