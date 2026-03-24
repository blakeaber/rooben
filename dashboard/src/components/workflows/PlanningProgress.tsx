"use client";

import { useCallback, useState } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";

type StepStatus = "waiting" | "active" | "done" | "retry";

interface Step {
  label: string;
  status: StepStatus;
  detail?: string;
}

const INITIAL_STEPS: Step[] = [
  { label: "Generating specification", status: "active" },
  { label: "Starting planner", status: "waiting" },
  { label: "Generating plan", status: "waiting" },
  { label: "Validating structure", status: "waiting" },
  { label: "Judging quality", status: "waiting" },
];

const STATUS_STYLES: Record<StepStatus, { dot: string; text: string; bg: string }> = {
  waiting: { dot: "var(--color-border-muted)", text: "var(--color-text-muted)", bg: "transparent" },
  active:  { dot: "#0d9488", text: "#0d9488", bg: "rgba(20, 184, 166, 0.1)" },
  done:    { dot: "#16a34a", text: "#16a34a", bg: "transparent" },
  retry:   { dot: "#d97706", text: "#d97706", bg: "rgba(217, 119, 6, 0.1)" },
};

interface PlanningProgressProps {
  workflowId: string;
}

export function PlanningProgress({ workflowId }: PlanningProgressProps) {
  const [steps, setSteps] = useState<Step[]>(INITIAL_STEPS);

  const onWsEvent = useCallback(
    (event: { type: string; workflow_id?: string; [key: string]: unknown }) => {
      if (event.workflow_id !== workflowId) return;

      // Handle spec generation events
      if (event.type === "workflow.spec_generating") {
        setSteps((prev) => {
          const next = prev.map((s) => ({ ...s }));
          next[0] = { ...next[0], status: "active" };
          return next;
        });
        return;
      }

      if (event.type === "workflow.spec_ready") {
        setSteps((prev) => {
          const next = prev.map((s) => ({ ...s }));
          next[0] = { ...next[0], status: "done" };
          next[1] = { ...next[1], status: "active" };
          return next;
        });
        return;
      }

      if (!event.type?.startsWith("planning.")) return;

      setSteps((prev) => {
        const next = prev.map((s) => ({ ...s }));
        // Mark spec generation as done when planning events arrive
        if (next[0].status !== "done") {
          next[0] = { ...next[0], status: "done" };
        }

        switch (event.type) {
          case "planning.started":
            next[1] = { ...next[1], status: "done" };
            next[2] = { ...next[2], status: "active" };
            break;

          case "planning.generating": {
            const isRetry = Boolean(event.is_retry);
            const iteration = (event.iteration as number) ?? 1;
            next[2] = {
              ...next[2],
              status: "active",
              detail: isRetry ? `Attempt ${iteration}` : undefined,
            };
            // Reset later steps on retry
            if (isRetry) {
              next[3] = { ...next[3], status: "waiting", detail: undefined };
              next[4] = { ...next[4], status: "waiting", detail: undefined };
            }
            break;
          }

          case "planning.checking":
            next[2] = { ...next[2], status: "done" };
            next[3] = { ...next[3], status: "active" };
            break;

          case "planning.judging": {
            const score = event.checker_score as number | undefined;
            next[3] = {
              ...next[3],
              status: "done",
              detail: score != null ? `Score: ${(score * 100).toFixed(0)}%` : undefined,
            };
            next[4] = { ...next[4], status: "active" };
            break;
          }

          case "planning.iteration_complete": {
            const issues = (event.issues_count as number) ?? 0;
            next[4] = {
              ...next[4],
              status: "retry",
              detail: `${issues} issue${issues !== 1 ? "s" : ""} — retrying`,
            };
            // Reset generating to active for next iteration
            next[2] = { ...next[2], status: "active", detail: undefined };
            break;
          }
        }

        return next;
      });
    },
    [workflowId],
  );

  useWebSocket(onWsEvent);

  return (
    <div
      className="rounded-md py-4 px-6"
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 0 }}>
        {steps.map((step, i) => {
          const style = STATUS_STYLES[step.status];
          const isLast = i === steps.length - 1;
          return (
            <div
              key={step.label}
              style={{
                display: "flex",
                alignItems: "flex-start",
                flex: isLast ? "0 0 auto" : 1,
                minWidth: 0,
              }}
            >
              {/* Dot + label (stacked) */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  flexShrink: 0,
                  width: 80,
                }}
              >
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    backgroundColor: style.dot,
                    flexShrink: 0,
                    boxShadow:
                      step.status === "active"
                        ? `0 0 0 3px ${style.dot}30`
                        : undefined,
                    animation:
                      step.status === "active"
                        ? "pulse-planning 1.5s ease-in-out infinite"
                        : undefined,
                  }}
                />
                <div
                  style={{
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 11,
                    fontWeight: 600,
                    color: style.text,
                    lineHeight: "14px",
                    textAlign: "center",
                    marginTop: 6,
                    backgroundColor: style.bg,
                    padding: style.bg !== "transparent" ? "2px 6px" : undefined,
                    borderRadius: 4,
                  }}
                >
                  {step.status === "done" && "\u2713 "}
                  {step.label}
                </div>
                {step.detail && (
                  <div
                    style={{
                      fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                      fontSize: 10,
                      color: "var(--color-text-muted)",
                      marginTop: 2,
                      textAlign: "center",
                    }}
                  >
                    {step.detail}
                  </div>
                )}
              </div>

              {/* Horizontal connecting line */}
              {!isLast && (
                <div
                  style={{
                    height: 2,
                    flex: 1,
                    backgroundColor: "var(--color-border)",
                    marginTop: 4,
                    minWidth: 12,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Pulse animation */}
      <style>{`
        @keyframes pulse-planning {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
