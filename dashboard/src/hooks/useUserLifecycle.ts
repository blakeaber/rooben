"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { PersonalDashboard } from "@/lib/types";

export type LifecycleStage = "new" | "exploring" | "active" | "power";

function deriveStage(data: PersonalDashboard | null): LifecycleStage {
  if (!data) return "new";
  const total = data.workflows.total;
  if (total === 0) return "new";
  // Any terminal result (completed or failed) → show full dashboard
  const terminal = (data.workflows.completed ?? 0) + (data.workflows.failed ?? 0);
  if (terminal > 0) {
    if (total >= 10) return "power";
    if (data.workflows.completed >= 1) return "active";
    // Has terminal results (all failed) — still show full dashboard
    return "active";
  }
  // Only in-progress/pending workflows — still exploring
  return "exploring";
}

export function useUserLifecycle() {
  const [stage, setStage] = useState<LifecycleStage>("new");
  const [dashboard, setDashboard] = useState<PersonalDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const prevStage = useRef<LifecycleStage>("new");

  useEffect(() => {
    let cancelled = false;
    apiFetch<PersonalDashboard>("/api/me/dashboard")
      .then((data) => {
        if (cancelled) return;
        setDashboard(data);
        const newStage = deriveStage(data);
        prevStage.current = newStage;
        setStage(newStage);
      })
      .catch(() => {
        if (!cancelled) {
          setStage("new");
          setDashboard(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { stage, dashboard, loading };
}
