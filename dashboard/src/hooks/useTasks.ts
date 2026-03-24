"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Task } from "@/lib/types";

export function useTasks(workflowId: string) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await apiFetch<{ tasks: Task[] }>(
        `/api/workflows/${workflowId}/tasks`
      );
      // Normalize: ensure attempt_feedback items have optional arrays
      const normalized = data.tasks.map((t) => ({
        ...t,
        attempt_feedback: (t.attempt_feedback ?? []).map((fb) => ({
          ...fb,
          suggested_improvements: fb.suggested_improvements ?? [],
          test_results: fb.test_results ?? [],
        })),
      }));
      setTasks(normalized);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const updateTask = async (taskId: string, data: Record<string, unknown>) => {
    await apiFetch(`/api/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    await refetch();
  };

  return { tasks, loading, error, refetch, updateTask };
}
