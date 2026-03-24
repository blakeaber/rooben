"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { StatusBadge } from "@/components/workflows/StatusBadge";
import { BudgetGauge } from "@/components/shared/BudgetGauge";
import { TaskDAG } from "@/components/dag/TaskDAG";
import { useTasks } from "@/hooks/useTasks";
import { useWebSocket } from "@/hooks/useWebSocket";
import { apiFetch } from "@/lib/api";
import { ErrorSummary } from "@/components/workflows/ErrorSummary";
import { ExportBar } from "@/components/workflows/ExportBar";
import { ExecutionProgress } from "@/components/output/ExecutionProgress";
import { TimelineView } from "@/components/workflows/TimelineView";
import { PlanQualityCard } from "@/components/workflows/PlanQualityCard";
import { PlanningProgress } from "@/components/workflows/PlanningProgress";
import { WorkflowChat } from "@/components/workflows/WorkflowChat";
import { ContextualHint } from "@/components/hints/ContextualHint";
import { useHints } from "@/hooks/useHints";
import { useUserLifecycle } from "@/hooks/useUserLifecycle";
import type { Workflow, Workstream, WorkstreamStatus } from "@/lib/types";

// ─── Types ───────────────────────────────────────────────────────────────────

interface WorkflowDetail {
  workflow: Workflow & {
    total_cost_usd: number;
    total_input_tokens: number;
    total_output_tokens: number;
    is_live?: boolean;
  };
  workstreams: Workstream[];
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function TelemetryCard({
  label,
  value,
  accent,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
  mono?: boolean;
}) {
  return (
    <div
      className="rounded-md p-3 flex flex-col gap-1 min-w-0"
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <span
        style={{
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span
        className="truncate"
        style={{
          color: accent ?? "var(--color-text-primary)",
          fontFamily: mono ? 'var(--font-mono, "JetBrains Mono", monospace)' : 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        {value}
      </span>
    </div>
  );
}

/** Workstream status left-border accent color */
const WS_BORDER: Record<WorkstreamStatus | string, string> = {
  pending:     "#d1d5db",
  in_progress: "#0d9488",
  completed:   "#16a34a",
  failed:      "#dc2626",
  cancelled:   "#9ca3af",
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function WorkflowDetailPage() {
  const params     = useParams();
  const workflowId = params.id as string;

  const [detail, setDetail]   = useState<WorkflowDetail | null>(null);
  const [fetchErr, setFetchErr] = useState<string | null>(null);
  const { tasks, refetch: refreshTasks } = useTasks(workflowId);

  const fetchDetail = useCallback(() => {
    apiFetch<WorkflowDetail>(`/api/workflows/${workflowId}`)
      .then(setDetail)
      .catch((err: unknown) => {
        setFetchErr(err instanceof Error ? err.message : "Failed to load workflow");
      });
  }, [workflowId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // Live updates via WebSocket
  const onWsEvent = useCallback(
    (event: { type: string; workflow_id?: string; [key: string]: unknown }) => {
      if (event.workflow_id !== workflowId) return;
      // Planning + spec generation events are ephemeral — handled by PlanningProgress component
      if (event.type?.startsWith("planning.")) return;
      if (event.type === "workflow.spec_generating" || event.type === "workflow.spec_ready") return;
      fetchDetail();
      refreshTasks();
    },
    [workflowId, fetchDetail, refreshTasks],
  );
  useWebSocket(onWsEvent);

  const { stage } = useUserLifecycle();
  const detailHints = useHints({
    page: "workflow_detail",
    stage,
    workflowCompleted: detail?.workflow.status === "completed",
    workflowFailed: detail?.workflow.status === "failed",
  });

  // ── Loading / error states ──────────────────────────────────────────────────
  if (fetchErr) {
    return (
      <div className="flex items-center justify-center py-24">
        <span
          style={{
            color: "#dc2626",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 14,
          }}
        >
          Error: {fetchErr}
        </span>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex items-center justify-center py-24">
        <span
          style={{
            color: "var(--color-text-muted)",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 14,
          }}
        >
          Loading...
        </span>
      </div>
    );
  }

  const wf          = detail.workflow;
  const totalTokens = Number(wf.total_input_tokens ?? 0) + Number(wf.total_output_tokens ?? 0);
  const costUsd     = Number(wf.total_cost_usd ?? 0);
  const shortId     = wf.id.slice(0, 12);

  const taskPct = wf.total_tasks > 0
    ? Math.round((wf.completed_tasks / wf.total_tasks) * 100)
    : 0;

  const isPlanning = wf.status === "planning";

  return (
    <div
      style={{
        backgroundColor: "var(--color-surface-1)",
        minHeight: "100vh",
        padding: "0 0 48px",
      }}
    >
      <Header
        title={`Workflow ${shortId}...`}
        breadcrumbs={[
          { label: "Workflows", href: "/" },
          { label: shortId },
        ]}
      />

      {/* ── Contextual hints ── */}
      {detailHints.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
          {detailHints.map((hint) => (
            <ContextualHint key={hint.id} hint={hint} />
          ))}
        </div>
      )}

      {/* ── Orphan warning (non-terminal status with no live orchestrator) ── */}
      {(wf.status === "in_progress" || wf.status === "planning") && wf.is_live === false && (
        <div
          className="mb-4 rounded-md p-3"
          style={{
            backgroundColor: "var(--color-amber-dim, rgba(217,119,6,0.08))",
            border: "1px solid #d97706",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 13,
              color: "#d97706",
            }}
          >
            This workflow appears stale — no active orchestrator is running it. It may have been orphaned by a container restart.
          </span>
          <button
            onClick={async () => {
              await apiFetch(`/api/workflows/${workflowId}/cancel`, { method: "POST" });
              fetchDetail();
            }}
            style={{
              flexShrink: 0,
              padding: "5px 12px",
              borderRadius: 6,
              border: "1px solid #d97706",
              backgroundColor: "var(--color-base)",
              color: "#d97706",
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Cancel & Retry
          </button>
        </div>
      )}

      {!isPlanning && (
        <div className="animate-fade-in-up stagger-1">
          {/* ── Error summary (only renders if failures exist) ─────── */}
          <ErrorSummary workflowId={workflowId} />

          {/* ── Execution progress (only for active workflows) ─────── */}
          {wf.status === "in_progress" && tasks.length > 0 && (
            <div
              className="mb-6 rounded-md p-4"
              style={{
                backgroundColor: "var(--color-base)",
                border: "1px solid var(--color-border)",
                boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
              }}
            >
              <ExecutionProgress
                tasks={tasks.map((t) => ({
                  taskId: t.id,
                  title: t.title,
                  status: t.status,
                  startedAt: t.started_at ?? undefined,
                  attempt: t.attempt,
                }))}
              />
            </div>
          )}
        </div>
      )}

      {/* ── Cancel button (active workflows) ────────────────────── */}
      {(wf.status === "planning" || wf.status === "in_progress") && (
        <div className="mb-4 flex justify-end">
          <button
            onClick={async () => {
              if (!confirm("Cancel this workflow? Running tasks will be stopped.")) return;
              await apiFetch(`/api/workflows/${workflowId}/cancel`, { method: "POST" });
              fetchDetail();
            }}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              border: "1px solid #dc2626",
              backgroundColor: "var(--color-base)",
              color: "#dc2626",
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
            }}
          >
            Cancel Workflow
          </button>
        </div>
      )}

      {/* ── Telemetry readout strip ──────────────────────────────── */}
      <div className="mb-2">
        <SectionLabel>Overview</SectionLabel>
      </div>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <TelemetryCard
          label="Status"
          value={<StatusBadge status={wf.status} />}
        />
        <TelemetryCard
          label="Spec"
          value={wf.spec_id}
          mono
        />
        <TelemetryCard
          label="Cost"
          value={`$${costUsd.toFixed(4)}`}
          accent="#16a34a"
          mono
        />
        <TelemetryCard
          label="Tokens"
          value={totalTokens.toLocaleString()}
          accent="#0d9488"
          mono
        />
        <TelemetryCard
          label="Tasks"
          value={`${wf.completed_tasks} / ${wf.total_tasks}`}
          accent={wf.failed_tasks > 0 ? "#dc2626" : "var(--color-text-primary)"}
          mono
        />
        <TelemetryCard
          label="Replans"
          value={wf.replan_count}
          accent={wf.replan_count > 0 ? "#d97706" : "var(--color-text-primary)"}
          mono
        />
      </div>

      {/* ── Planning progress (horizontal, shown during planning phase) ── */}
      {wf.status === "planning" && (
        <div className="mb-6">
          <PlanningProgress workflowId={workflowId} />
        </div>
      )}

      {!isPlanning && (
        <div className="animate-fade-in-up stagger-1">
          {/* ── Workstream cards ─────────────────────────────────────── */}
          <div className="mb-2">
            <SectionLabel>Workstreams ({detail.workstreams.length})</SectionLabel>
          </div>
          {detail.workstreams.length === 0 ? (
            <div
              className="rounded-md py-8 text-center"
              style={{
                backgroundColor: "var(--color-base)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-muted)",
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 14,
              }}
            >
              No workstreams
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {detail.workstreams.map((ws) => {
                const wsColor = WS_BORDER[ws.status] ?? WS_BORDER.pending;
                const wsTaskIds = ws.task_ids ?? [];
                // Match task IDs to loaded task data for names + statuses
                const wsTasks = wsTaskIds
                  .map((tid) => tasks.find((t) => t.id === tid))
                  .filter(Boolean);
                return (
                  <div
                    key={ws.id}
                    className="rounded-md p-3"
                    style={{
                      backgroundColor: "var(--color-base)",
                      border: "1px solid var(--color-border)",
                      borderLeft: `3px solid ${wsColor}`,
                      boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                    }}
                  >
                    {/* Header row */}
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span
                        className="truncate"
                        style={{
                          color: "var(--color-text-primary)",
                          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                          fontSize: 13,
                          fontWeight: 600,
                        }}
                        title={ws.name}
                      >
                        {ws.name}
                      </span>
                      <StatusBadge status={ws.status} />
                    </div>

                    {/* Description */}
                    {ws.description && (
                      <p
                        className="mb-2 line-clamp-2"
                        style={{
                          color: "var(--color-text-secondary)",
                          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                          fontSize: 12,
                          lineHeight: 1.5,
                        }}
                      >
                        {ws.description}
                      </p>
                    )}

                    {/* Task list */}
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 3,
                        marginTop: ws.description ? 0 : 4,
                      }}
                    >
                      {wsTasks.length > 0 ? (
                        wsTasks.map((t) => (
                          <div
                            key={t!.id}
                            className="flex items-center gap-1.5"
                            style={{
                              fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                              fontSize: 11,
                              color: "var(--color-text-secondary)",
                            }}
                          >
                            <StatusDot status={t!.status} />
                            <span className="truncate" title={t!.title}>
                              {t!.title}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div
                          style={{
                            color: "var(--color-text-muted)",
                            fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                            fontSize: 11,
                          }}
                        >
                          {wsTaskIds.length} task{wsTaskIds.length !== 1 ? "s" : ""}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {!isPlanning && (
        <div className="animate-fade-in-up stagger-2">
          {/* ── DAG panel ────────────────────────────────────────────── */}
          <div className="mb-2 mt-6 flex items-center justify-between">
            <SectionLabel>Task Dependency Graph</SectionLabel>
            <div className="flex items-center gap-2">
              <Link
                href={`/workflows/${workflowId}/spec`}
                style={{
                  color: "#7c3aed",
                  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                  fontSize: 12,
                  fontWeight: 500,
                  textDecoration: "none",
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-base)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                }}
              >
                Specification
              </Link>
              <Link
                href={`/workflows/${workflowId}/verification`}
                style={{
                  color: "#0d9488",
                  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                  fontSize: 12,
                  fontWeight: 500,
                  textDecoration: "none",
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-base)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                }}
              >
                Verification Inspector →
              </Link>
            </div>
          </div>
          <div className="mb-6">
            {tasks.length > 0 ? (
              <TaskDAG workflowId={workflowId} tasks={tasks} />
            ) : (
              <div
                className="rounded-md py-12 text-center"
                style={{
                  backgroundColor: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)",
                  fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                  fontSize: 13,
                }}
              >
                Waiting for plan...
              </div>
            )}
          </div>
        </div>
      )}

      {!isPlanning && (
        <div className="animate-fade-in-up stagger-3">
          {/* ── Execution Timeline ──────────────────────────────────── */}
          <div className="mb-2">
            <SectionLabel>Execution Timeline</SectionLabel>
          </div>
          <div className="mb-6">
            <TimelineView workflowId={workflowId} />
          </div>
        </div>
      )}

      {!isPlanning && (
        <div className="animate-fade-in-up stagger-4">
          {/* ── Resource Utilization + Plan Quality (2-col) ──────────── */}
          <div className="mb-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <div className="mb-2">
                <SectionLabel>Resource Utilization</SectionLabel>
              </div>
              <div
                className="flex flex-wrap justify-center gap-8 rounded-md py-6"
                style={{
                  backgroundColor: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                }}
              >
                <BudgetGauge
                  label="Task Completion"
                  used={wf.completed_tasks}
                  max={wf.total_tasks || 1}
                  variant="progress"
                />
                <BudgetGauge
                  label="Token Budget"
                  used={totalTokens}
                  max={1_000_000}
                  unit=" tok"
                />
                <BudgetGauge
                  label="Cost Budget"
                  used={costUsd}
                  max={10}
                  unit=" USD"
                />
              </div>
            </div>
            <div>
              <div className="mb-2">
                <SectionLabel>Plan Quality</SectionLabel>
              </div>
              <PlanQualityCard workflow={wf} />
            </div>
          </div>
        </div>
      )}

      {!isPlanning && (
        <div className="animate-fade-in-up stagger-5">
          {/* ── Save as Template (completed workflows) ─────────────── */}
          {wf.status === "completed" && (
            <div className="mt-6 mb-2">
              <SaveAsTemplateButton workflowId={workflowId} />
            </div>
          )}

          {/* ── Export & sharing bar ────────────────────────────────── */}
          <div className="mt-6 mb-2">
            <SectionLabel>Export & Share</SectionLabel>
          </div>
          <ExportBar workflowId={workflowId} />

          {/* ── Workflow Chat ─────────────────────────────────────────── */}
          <div className="mt-6 mb-2">
            <SectionLabel>Chat</SectionLabel>
          </div>
          <WorkflowChat workflowId={workflowId} />
        </div>
      )}
    </div>
  );
}

// ─── Section label ────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2
      className="mb-3 flex items-center gap-2"
      style={{
        color: "var(--color-text-secondary)",
        fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
      }}
    >
      {/* Left accent rule */}
      <span
        style={{
          display: "inline-block",
          width: 3,
          height: 14,
          backgroundColor: "#0d9488",
          borderRadius: 2,
          flexShrink: 0,
        }}
        aria-hidden="true"
      />
      {children}
    </h2>
  );
}

// ─── Status dot for task list ────────────────────────────────────────────────

const STATUS_DOT_COLOR: Record<string, string> = {
  pending: "#9ca3af",
  blocked: "#d97706",
  ready: "#0d9488",
  in_progress: "#0d9488",
  verifying: "#7c3aed",
  passed: "#16a34a",
  failed: "#dc2626",
  skipped: "#d1d5db",
  cancelled: "#d1d5db",
};

function StatusDot({ status }: { status: string }) {
  const color = STATUS_DOT_COLOR[status] ?? "#9ca3af";
  return (
    <span
      style={{
        display: "inline-block",
        width: 6,
        height: 6,
        borderRadius: "50%",
        backgroundColor: color,
        flexShrink: 0,
      }}
      title={status}
    />
  );
}

// ─── Save as Template button ─────────────────────────────────────────────────

function SaveAsTemplateButton({ workflowId }: { workflowId: string }) {
  const [showInput, setShowInput] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedName, setSavedName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    const name = templateName.trim();
    if (!name) return;
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(name)) {
      setError("Name must be kebab-case (e.g. my-template)");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/api/workflows/${workflowId}/export-template`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      setSavedName(name);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setSaving(false);
    }
  };

  if (savedName) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "8px 16px",
          borderRadius: 6,
          border: "1px solid #16a34a",
          backgroundColor: "#f0fdf4",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 12,
          fontWeight: 600,
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        <span style={{ color: "#16a34a" }}>Exported as &ldquo;{savedName}&rdquo;</span>
        <Link
          href="/integrations"
          style={{
            color: "#0d9488",
            textDecoration: "underline",
            fontSize: 12,
          }}
        >
          View in Data Sources
        </Link>
      </div>
    );
  }

  if (!showInput) {
    return (
      <button
        onClick={() => setShowInput(true)}
        style={{
          padding: "8px 16px",
          borderRadius: 6,
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-base)",
          color: "#0d9488",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 12,
          fontWeight: 600,
          cursor: "pointer",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        Export as Template
      </button>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap",
      }}
    >
      <input
        type="text"
        placeholder="template-name"
        value={templateName}
        onChange={(e) => {
          setTemplateName(e.target.value);
          setError(null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleExport();
          if (e.key === "Escape") {
            setShowInput(false);
            setTemplateName("");
            setError(null);
          }
        }}
        autoFocus
        style={{
          padding: "6px 10px",
          borderRadius: 6,
          border: error ? "1px solid #dc2626" : "1px solid var(--color-border)",
          backgroundColor: "var(--color-base)",
          color: "var(--color-text-primary)",
          fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
          fontSize: 12,
          width: 200,
          outline: "none",
        }}
      />
      <button
        onClick={handleExport}
        disabled={saving || !templateName.trim()}
        style={{
          padding: "6px 14px",
          borderRadius: 6,
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-base)",
          color: saving ? "var(--color-text-muted)" : "#0d9488",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 12,
          fontWeight: 600,
          cursor: saving || !templateName.trim() ? "default" : "pointer",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        {saving ? "Exporting..." : "Export"}
      </button>
      <button
        onClick={() => {
          setShowInput(false);
          setTemplateName("");
          setError(null);
        }}
        style={{
          padding: "6px 10px",
          borderRadius: 6,
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-base)",
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 12,
          fontWeight: 500,
          cursor: "pointer",
        }}
      >
        Cancel
      </button>
      {error && (
        <span
          style={{
            color: "#dc2626",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 11,
            width: "100%",
          }}
        >
          {error}
        </span>
      )}
    </div>
  );
}
