"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Workflow } from "@/lib/types";

export function useWorkflows(status?: string) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      const data = await apiFetch<{ workflows: Workflow[]; total: number }>(
        `/api/workflows?${params}`
      );
      setWorkflows(data.workflows);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    refetch();
    const interval = setInterval(refetch, 5000);
    return () => clearInterval(interval);
  }, [refetch]);

  return { workflows, total, loading, error, refetch };
}
