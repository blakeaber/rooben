"use client";

import { useEffect, useRef, useState } from "react";

interface WSEvent {
  type: string;
  task_id?: string;
  workflow_id?: string;
  status?: string;
  [key: string]: unknown;
}

// ─── Shared singleton WebSocket ─────────────────────────────────────────────

type Listener = (event: WSEvent) => void;

let sharedWs: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
const listeners = new Set<Listener>();
let subscriberCount = 0;
let sharedConnected = false;

function getWsUrl(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  let wsUrl: string;
  if (apiUrl) {
    wsUrl = apiUrl.replace(/^http/, "ws") + "/ws/events";
  } else {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    wsUrl = `${protocol}//${window.location.host}/ws/events`;
  }
  const token = localStorage.getItem("rooben_api_key");
  if (token) {
    wsUrl += `?token=${encodeURIComponent(token)}`;
  }
  return wsUrl;
}

function ensureConnection() {
  if (sharedWs && (sharedWs.readyState === WebSocket.OPEN || sharedWs.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    const ws = new WebSocket(getWsUrl());
    sharedWs = ws;

    ws.onopen = () => {
      sharedConnected = true;
    };

    ws.onclose = () => {
      sharedConnected = false;
      sharedWs = null;
      // Only reconnect if there are active subscribers
      if (subscriberCount > 0) {
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(ensureConnection, 3000);
      }
    };

    ws.onerror = () => {
      // Suppress — onclose handles reconnection
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSEvent;
        for (const listener of listeners) {
          listener(data);
        }
      } catch {
        // ignore malformed messages
      }
    };
  } catch {
    // WebSocket constructor can throw if URL is invalid
    if (subscriberCount > 0) {
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(ensureConnection, 3000);
    }
  }
}

function teardownIfUnused() {
  if (subscriberCount > 0) return;
  clearTimeout(reconnectTimer);
  reconnectTimer = undefined;
  if (sharedWs) {
    const ws = sharedWs;
    sharedWs = null;
    sharedConnected = false;
    ws.onclose = null;
    ws.onerror = null;
    ws.onmessage = null;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
  }
}

// ─── Hook ───────────────────────────────────────────────────────────────────

export function useWebSocket(onEvent?: (event: WSEvent) => void) {
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    const listener: Listener = (event) => {
      onEventRef.current?.(event);
    };
    listeners.add(listener);
    subscriberCount++;
    ensureConnection();

    // Poll connected state (lightweight — just reads a boolean)
    const interval = setInterval(() => {
      setConnected(sharedConnected);
    }, 1000);
    setConnected(sharedConnected);

    return () => {
      listeners.delete(listener);
      subscriberCount--;
      clearInterval(interval);
      // Defer teardown to allow Strict Mode remount
      setTimeout(teardownIfUnused, 100);
    };
  }, []);

  return { connected };
}
