"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WorkflowSSEEvent } from "@/lib/types";

export function useWorkflowSSE(workflowId: string | null) {
  const [events, setEvents] = useState<WorkflowSSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptsRef = useRef(0);

  const connect = useCallback(() => {
    if (!workflowId) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8420";
    const url = `${apiUrl}/api/workflows/${encodeURIComponent(workflowId)}/events`;

    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
      attemptsRef.current = 0;
    };

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [...prev, data]);
      } catch {
        // Ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
      setConnected(false);
      attemptsRef.current += 1;

      // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
      const delay = Math.min(1000 * 2 ** attemptsRef.current, 30000);
      reconnectRef.current = setTimeout(connect, delay);
    };
  }, [workflowId]);

  useEffect(() => {
    connect();

    return () => {
      if (esRef.current) {
        esRef.current.close();
      }
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
      }
    };
  }, [connect]);

  const disconnect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
    setConnected(false);
  }, []);

  return { events, connected, error, disconnect };
}
