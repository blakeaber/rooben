"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface DiagnosticItem {
  category: string;
  severity: "error" | "warning" | "info";
  title: string;
  description: string;
  suggestion: string;
  affected_task_count: number;
  affected_task_ids: string[];
}

interface DiagnosticsResponse {
  workflow_id: string;
  diagnostics: DiagnosticItem[];
  recommendation: string;
  has_failures: boolean;
}

interface TaskInfo {
  id: string;
  title: string;
  status: string;
  assigned_agent_id: string | null;
  error?: string;
}

const SEVERITY_STYLES: Record<string, { bg: string; border: string; icon: string; accent: string }> = {
  error: {
    bg: "rgba(220, 38, 38, 0.08)",
    border: "rgba(220, 38, 38, 0.25)",
    icon: "!",
    accent: "#dc2626",
  },
  warning: {
    bg: "rgba(217, 119, 6, 0.08)",
    border: "rgba(217, 119, 6, 0.25)",
    icon: "⚠",
    accent: "#d97706",
  },
  info: {
    bg: "rgba(2, 132, 199, 0.08)",
    border: "rgba(2, 132, 199, 0.25)",
    icon: "i",
    accent: "#0284c7",
  },
};

export function ErrorSummary({ workflowId }: { workflowId: string }) {
  const [data, setData] = useState<DiagnosticsResponse | null>(null);
  const [tasks, setTasks] = useState<Map<string, TaskInfo>>(new Map());
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(() => {
    Promise.all([
      apiFetch<DiagnosticsResponse>(`/api/workflows/${workflowId}/diagnostics`),
      apiFetch<{ tasks: TaskInfo[] }>(`/api/workflows/${workflowId}/tasks`),
    ])
      .then(([diag, taskRes]) => {
        setData(diag);
        const map = new Map<string, TaskInfo>();
        for (const t of taskRes.tasks) map.set(t.id, t);
        setTasks(map);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [workflowId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading || !data || !data.has_failures) return null;

  const { diagnostics, recommendation } = data;
  if (diagnostics.length === 0) return null;

  // Show the most severe item prominently
  const primary = diagnostics[0];
  const style = SEVERITY_STYLES[primary.severity] || SEVERITY_STYLES.warning;

  return (
    <div
      className="mb-6 rounded-md overflow-hidden"
      style={{
        backgroundColor: style.bg,
        border: `1px solid ${style.border}`,
      }}
    >
      {/* Primary diagnostic */}
      <div className="p-4">
        <div className="flex items-start gap-3">
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 24,
              height: 24,
              borderRadius: "50%",
              backgroundColor: style.accent,
              color: "#ffffff",
              fontSize: 12,
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            {style.icon}
          </span>
          <div className="min-w-0 flex-1">
            <h3
              style={{
                color: style.accent,
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 14,
                fontWeight: 600,
                margin: 0,
              }}
            >
              {primary.title}
              {primary.affected_task_count > 0 && (
                <span style={{ fontWeight: 400, opacity: 0.8 }}>
                  {" "}
                  ({primary.affected_task_count} task{primary.affected_task_count !== 1 ? "s" : ""})
                </span>
              )}
            </h3>
            <p
              style={{
                color: "var(--color-text-primary)",
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 13,
                lineHeight: 1.5,
                margin: "4px 0 0",
              }}
            >
              {primary.description}
            </p>
            {/* Affected tasks for primary diagnostic */}
            {primary.affected_task_ids.length > 0 && (
              <AffectedTaskList taskIds={primary.affected_task_ids} tasks={tasks} />
            )}
          </div>
        </div>
      </div>

      {/* Expand toggle for additional diagnostics */}
      {(diagnostics.length > 1 || recommendation) && (
        <div
          style={{
            borderTop: `1px solid ${style.border}`,
            padding: "8px 16px",
          }}
        >
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: "none",
              border: "none",
              color: style.accent,
              cursor: "pointer",
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 12,
              fontWeight: 500,
              padding: 0,
            }}
          >
            {expanded ? "Hide details" : `Show details (${diagnostics.length} issue${diagnostics.length !== 1 ? "s" : ""})`}
          </button>

          {expanded && (
            <div style={{ marginTop: 12 }}>
              {diagnostics.slice(1).map((d, i) => {
                const s = SEVERITY_STYLES[d.severity] || SEVERITY_STYLES.warning;
                return (
                  <div
                    key={i}
                    style={{
                      padding: "8px 0",
                      borderTop: i > 0 ? `1px solid ${style.border}` : undefined,
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          backgroundColor: s.accent,
                          flexShrink: 0,
                        }}
                      />
                      <span
                        style={{
                          color: "var(--color-text-primary)",
                          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                          fontSize: 13,
                          fontWeight: 500,
                        }}
                      >
                        {d.title}
                        {d.affected_task_count > 0 && (
                          <span style={{ fontWeight: 400, color: "var(--color-text-muted)" }}>
                            {" "}
                            ({d.affected_task_count})
                          </span>
                        )}
                      </span>
                    </div>
                    <p
                      style={{
                        color: "var(--color-text-secondary)",
                        fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                        fontSize: 12,
                        margin: "2px 0 0 20px",
                      }}
                    >
                      {d.suggestion}
                    </p>
                    {d.affected_task_ids.length > 0 && (
                      <div style={{ marginLeft: 20, marginTop: 4 }}>
                        <AffectedTaskList taskIds={d.affected_task_ids} tasks={tasks} />
                      </div>
                    )}
                  </div>
                );
              })}

              {recommendation && (
                <div
                  style={{
                    marginTop: 8,
                    padding: "8px 12px",
                    backgroundColor: "rgba(255,255,255,0.6)",
                    borderRadius: 6,
                  }}
                >
                  <span
                    style={{
                      color: "var(--color-text-primary)",
                      fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                      fontSize: 11,
                    }}
                  >
                    {recommendation}
                  </span>
                </div>
              )}

              {/* CTA to verification inspector */}
              <div style={{ marginTop: 12, paddingTop: 8, borderTop: `1px solid ${style.border}` }}>
                <Link
                  href={`/workflows/${workflowId}/verification`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 12px",
                    borderRadius: 6,
                    backgroundColor: style.accent,
                    color: "#ffffff",
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 12,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Inspect failed tasks →
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  failed: "#dc2626",
  cancelled: "var(--color-text-muted)",
  pending: "var(--color-text-secondary)",
  in_progress: "#0d9488",
  passed: "#16a34a",
};

function AffectedTaskList({
  taskIds,
  tasks,
}: {
  taskIds: string[];
  tasks: Map<string, TaskInfo>;
}) {
  // Show at most 5 tasks inline, indicate overflow
  const visible = taskIds.slice(0, 5);
  const overflow = taskIds.length - visible.length;

  return (
    <div style={{ marginTop: 6 }}>
      {visible.map((id) => {
        const t = tasks.get(id);
        return (
          <div key={id} style={{ padding: "3px 0" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  backgroundColor: STATUS_COLORS[t?.status ?? ""] ?? "var(--color-text-muted)",
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  color: "var(--color-text-primary)",
                  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                  fontSize: 11,
                }}
              >
                {t?.title ?? id}
              </span>
              {t?.assigned_agent_id && (
                <span
                  style={{
                    color: "var(--color-text-muted)",
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 10,
                  }}
                >
                  {t.assigned_agent_id}
                </span>
              )}
              {t?.status && (
                <span
                  style={{
                    color: STATUS_COLORS[t.status] ?? "var(--color-text-secondary)",
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 10,
                    fontWeight: 600,
                    textTransform: "uppercase",
                  }}
                >
                  {t.status}
                </span>
              )}
            </div>
            {t?.error && (
              <p
                style={{
                  color: "var(--color-text-muted)",
                  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                  fontSize: 10,
                  margin: "1px 0 0 12px",
                  lineHeight: 1.4,
                }}
              >
                {t.error.length > 120 ? t.error.slice(0, 120) + "\u2026" : t.error}
              </p>
            )}
          </div>
        );
      })}
      {overflow > 0 && (
        <span
          style={{
            color: "var(--color-text-muted)",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 11,
            paddingLeft: 12,
          }}
        >
          +{overflow} more
        </span>
      )}
    </div>
  );
}
