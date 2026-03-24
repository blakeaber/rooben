"use client";

import { useMemo, useState, useEffect } from "react";
import type { LifecycleStage } from "@/hooks/useUserLifecycle";
import type { PersonalDashboard } from "@/lib/types";
import type { HintData } from "@/components/hints/ContextualHint";

interface UseHintsParams {
  page: "home" | "workflow_detail" | "org";
  stage: LifecycleStage;
  dashboard?: PersonalDashboard | null;
  workflowCompleted?: boolean;
  workflowFailed?: boolean;
}

export function useHints({
  page,
  stage,
  dashboard,
  workflowCompleted,
  workflowFailed,
}: UseHintsParams): HintData[] {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const allHints = useMemo(() => {
    const hints: HintData[] = [];

    if (page === "home") {
      if (
        stage === "exploring" &&
        dashboard &&
        dashboard.workflows.completed >= 1
      ) {
        hints.push({
          id: "post_first_cost",
          message:
            "Check Cost & Tokens in the workflow detail page for a breakdown of what your first workflow cost.",
        });
      }
    }

    if (page === "workflow_detail") {
      if (workflowCompleted) {
        hints.push({
          id: "post_workflow_cost",
          message:
            "Check the telemetry cards above for a detailed breakdown of this workflow's cost and token usage.",
        });
      }
    }

    return hints;
  }, [page, stage, dashboard, workflowCompleted, workflowFailed]);

  // Sync dismissed state from localStorage after mount (avoids SSR mismatch)
  useEffect(() => {
    const ids = new Set<string>();
    for (const h of allHints) {
      if (localStorage.getItem(`hint_dismissed_${h.id}`) === "true") {
        ids.add(h.id);
      }
    }
    if (ids.size > 0) setDismissed(ids);
  }, [allHints]);

  return allHints.filter((h) => !dismissed.has(h.id));
}
