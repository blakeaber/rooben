"use client";

import { useEffect, useState } from "react";

interface TaskProgress {
  taskId: string;
  title: string;
  status: string;
  phase?: string;
  attempt?: number;
  startedAt?: string;
}

interface ExecutionProgressProps {
  tasks: TaskProgress[];
}

const PHASE_LABELS: Record<string, string> = {
  executing: "Running",
  verifying: "Verifying",
  retrying: "Retrying",
};

const STATUS_STYLES: Record<string, { dot: string; label: string }> = {
  in_progress: { dot: "#0d9488", label: "In Progress" },
  verifying: { dot: "#d97706", label: "Verifying" },
  passed: { dot: "#16a34a", label: "Passed" },
  failed: { dot: "#dc2626", label: "Failed" },
  pending: { dot: "var(--color-border-muted)", label: "Pending" },
  blocked: { dot: "var(--color-border-muted)", label: "Blocked" },
  cancelled: { dot: "var(--color-text-muted)", label: "Cancelled" },
  skipped: { dot: "var(--color-text-muted)", label: "Skipped" },
};

function ElapsedTimer({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return (
    <span
      style={{
        color: "var(--color-text-muted)",
        fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
        fontSize: 10,
      }}
    >
      {mins > 0 ? `${mins}m ${secs}s` : `${secs}s`}
    </span>
  );
}

export function ExecutionProgress({ tasks }: ExecutionProgressProps) {
  const total = tasks.length;
  const completed = tasks.filter((t) => t.status === "passed").length;
  const failed = tasks.filter((t) => t.status === "failed").length;
  const active = tasks.filter((t) => ["in_progress", "verifying"].includes(t.status));
  const pct = total > 0 ? Math.round(((completed + failed) / total) * 100) : 0;

  return (
    <div>
      {/* Overall progress bar */}
      <div style={{ marginBottom: 12 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 4 }}>
          <span
            style={{
              color: "var(--color-text-secondary)",
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 11,
              fontWeight: 500,
            }}
          >
            {completed}/{total} tasks complete
            {failed > 0 && <span style={{ color: "#dc2626" }}> ({failed} failed)</span>}
          </span>
          <span
            style={{
              color: "var(--color-text-muted)",
              fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
              fontSize: 11,
            }}
          >
            {pct}%
          </span>
        </div>
        <div
          style={{
            height: 4,
            backgroundColor: "var(--color-border)",
            borderRadius: 2,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${pct}%`,
              backgroundColor: failed > 0 ? "#d97706" : "#0d9488",
              borderRadius: 2,
              transition: "width 0.5s ease",
            }}
          />
        </div>
      </div>

      {/* Active task rows */}
      {active.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {active.map((task) => {
            const style = STATUS_STYLES[task.status] || STATUS_STYLES.pending;
            const phaseLabel = task.phase ? PHASE_LABELS[task.phase] || task.phase : style.label;

            return (
              <div
                key={task.taskId}
                className="flex items-center gap-2"
                style={{
                  padding: "6px 0",
                  borderBottom: "1px solid var(--color-surface-3)",
                }}
              >
                {/* Pulsing dot */}
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    backgroundColor: style.dot,
                    flexShrink: 0,
                    animation: "pulse 1.5s ease-in-out infinite",
                  }}
                />
                <span
                  className="flex-1 truncate"
                  style={{
                    color: "var(--color-text-primary)",
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 12,
                  }}
                >
                  {task.title}
                </span>
                <span
                  style={{
                    color: style.dot,
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 10,
                    fontWeight: 500,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                  }}
                >
                  {phaseLabel}
                  {task.attempt && task.attempt > 1 && ` #${task.attempt}`}
                </span>
                {task.startedAt && <ElapsedTimer startedAt={task.startedAt} />}
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
