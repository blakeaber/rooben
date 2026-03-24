"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Task, AgentSpec } from "@/lib/types";
import { StatusBadge } from "@/components/workflows/StatusBadge";
import { MarkdownRenderer } from "@/components/output/MarkdownRenderer";
import { ArtifactViewer } from "@/components/output/ArtifactViewer";

interface TaskDetailPanelProps {
  task: Task | null;
  onClose: () => void;
  agents?: AgentSpec[];
  onUpdate?: () => void;
}

// Reusable data row for the telemetry grid
function DataRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
}) {
  return (
    <>
      <dt
        style={{
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </dt>
      <dd
        style={{
          color: accent ?? "var(--color-text-primary)",
          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
          fontSize: 12,
        }}
      >
        {value}
      </dd>
    </>
  );
}

const EDITABLE_STATUSES = new Set(["pending", "blocked", "ready"]);

export function TaskDetailPanel({ task, onClose, agents, onUpdate }: TaskDetailPanelProps) {
  const [outputExpanded, setOutputExpanded] = useState(false);
  const [panelWide, setPanelWide] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editAgent, setEditAgent] = useState("");
  const [saving, setSaving] = useState(false);

  if (!task) return null;

  const isEditable = EDITABLE_STATUSES.has(task.status);

  const startEditing = () => {
    setEditTitle(task.title);
    setEditDescription(task.description || "");
    setEditAgent(task.assigned_agent_id || "");
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const body: Record<string, unknown> = {};
      if (editTitle !== task.title) body.title = editTitle;
      if (editDescription !== (task.description || "")) body.description = editDescription;
      if (editAgent !== (task.assigned_agent_id || "")) body.assigned_agent_id = editAgent || null;
      if (Object.keys(body).length > 0) {
        await apiFetch(`/api/tasks/${task.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        onUpdate?.();
      }
      setEditing(false);
    } catch {
      // silently handle
    } finally {
      setSaving(false);
    }
  };

  const hasResult = !!task.result;
  const output = task.result?.output ?? "";
  const outputPreview = output.slice(0, 1000);
  const outputTruncated = output.length > 1000;

  // Token usage detail (attached by backend query)
  const tokenDetail = (task as unknown as Record<string, unknown>).token_usage_detailed as
    | { input_tokens: number; output_tokens: number; cost_usd: number }
    | null
    | undefined;

  return (
    // Slide-out positioned inside the parent DAG container
    <div
      className="absolute right-0 top-0 h-full overflow-y-auto z-20"
      style={{
        width: panelWide ? 600 : 360,
        backgroundColor: "var(--color-base)",
        borderLeft: "1px solid var(--color-border)",
        boxShadow: "-2px 0 8px rgba(0,0,0,0.06)",
        transition: "width 0.2s ease",
      }}
    >
      {/* Panel header */}
      <div
        className="sticky top-0 z-10 flex items-center justify-between px-4 py-3"
        style={{
          backgroundColor: "var(--color-base)",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <div className="flex items-center gap-2">
          {/* Teal accent bar */}
          <div
            style={{
              width: 2,
              height: 16,
              backgroundColor: "#0d9488",
              borderRadius: 1,
              flexShrink: 0,
            }}
          />
          <span
            style={{
              color: "var(--color-text-secondary)",
              fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
              fontSize: 11,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            Task Detail
          </span>
        </div>

        <div className="flex items-center gap-1">
          {/* Width toggle button */}
          <button
            onClick={() => setPanelWide(!panelWide)}
            aria-label={panelWide ? "Narrow panel" : "Widen panel"}
            className="flex h-7 w-7 items-center justify-center rounded transition-colors
                       hover:bg-gray-100 focus-visible:outline focus-visible:outline-2
                       focus-visible:outline-[#0d9488]"
            style={{ color: "var(--color-text-muted)" }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              {panelWide ? (
                <>
                  <line x1="4" y1="2" x2="4" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <line x1="8" y1="2" x2="8" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <line x1="1" y1="6" x2="4" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <line x1="8" y1="6" x2="11" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </>
              ) : (
                <>
                  <line x1="4" y1="2" x2="4" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <line x1="8" y1="2" x2="8" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <line x1="4" y1="6" x2="1" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <line x1="8" y1="6" x2="11" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </>
              )}
            </svg>
          </button>

          <button
            onClick={onClose}
            aria-label="Close task detail panel"
            className="flex h-7 w-7 items-center justify-center rounded transition-colors
                       hover:bg-gray-100 focus-visible:outline focus-visible:outline-2
                       focus-visible:outline-[#0d9488]"
            style={{ color: "var(--color-text-muted)" }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Panel body */}
      <div className="px-4 py-4 space-y-5">

        {/* Title + description */}
        <div>
          <h3
            className="leading-snug"
            style={{
              color: "var(--color-text-primary)",
              fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            {task.title}
          </h3>
          {task.description && (
            <p
              className="mt-1 leading-relaxed"
              style={{
                color: "var(--color-text-secondary)",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 12,
              }}
            >
              {task.description}
            </p>
          )}
        </div>

        {/* Status + agent tags + edit button */}
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={task.status} />
          {task.assigned_agent_id && (
            <span
              className="inline-flex items-center rounded px-2 py-0.5 text-xs"
              style={{
                backgroundColor: "var(--color-surface-2)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-secondary)",
                fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
              }}
            >
              {task.assigned_agent_id}
            </span>
          )}
          {isEditable && !editing && (
            <button
              onClick={startEditing}
              style={{
                marginLeft: "auto",
                padding: "3px 10px",
                borderRadius: 4,
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-base)",
                color: "#0d9488",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 11,
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Edit
            </button>
          )}
        </div>

        {/* Inline edit form */}
        {editing && (
          <div
            style={{
              backgroundColor: "var(--color-surface-2)",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              padding: 12,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <input
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              placeholder="Title"
              style={{
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 13,
                padding: "6px 8px",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
              }}
            />
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="Description"
              rows={2}
              style={{
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 12,
                padding: "6px 8px",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
                resize: "vertical",
              }}
            />
            {agents && agents.length > 0 && (
              <select
                value={editAgent}
                onChange={(e) => setEditAgent(e.target.value)}
                style={{
                  fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                  fontSize: 12,
                  padding: "6px 8px",
                  border: "1px solid var(--color-border)",
                  borderRadius: 4,
                }}
              >
                <option value="">Unassigned</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  padding: "4px 12px",
                  borderRadius: 4,
                  border: "none",
                  backgroundColor: "#0d9488",
                  color: "#ffffff",
                  fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: saving ? "wait" : "pointer",
                  opacity: saving ? 0.6 : 1,
                }}
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setEditing(false)}
                style={{
                  padding: "4px 12px",
                  borderRadius: 4,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-base)",
                  color: "var(--color-text-secondary)",
                  fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Telemetry grid */}
        <div>
          <div
            className="mb-2"
            style={{
              color: "var(--color-text-muted)",
              fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
              fontSize: 10,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            Telemetry
          </div>
          <dl
            className="grid gap-x-4 gap-y-2"
            style={{ gridTemplateColumns: "max-content 1fr" }}
          >
            <DataRow label="Attempts" value={`${task.attempt} / ${task.max_retries}`} />
            <DataRow label="Strategy" value={task.verification_strategy} />
            {hasResult && (
              <>
                <DataRow
                  label="Tokens"
                  value={task.result!.token_usage.toLocaleString()}
                  accent="#0d9488"
                />
                <DataRow
                  label="Wall time"
                  value={`${task.result!.wall_seconds.toFixed(2)}s`}
                />
              </>
            )}
            {task.started_at && (
              <DataRow
                label="Started"
                value={new Date(task.started_at).toLocaleTimeString()}
              />
            )}
            {task.completed_at && (
              <DataRow
                label="Completed"
                value={new Date(task.completed_at).toLocaleTimeString()}
              />
            )}
          </dl>
        </div>

        {/* Token usage breakdown */}
        {tokenDetail && (
          <div>
            <div
              className="mb-2"
              style={{
                color: "var(--color-text-muted)",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 10,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Token Breakdown
            </div>
            <dl
              className="grid gap-x-4 gap-y-2"
              style={{ gridTemplateColumns: "max-content 1fr" }}
            >
              <DataRow
                label="Input"
                value={tokenDetail.input_tokens.toLocaleString()}
              />
              <DataRow
                label="Output"
                value={tokenDetail.output_tokens.toLocaleString()}
              />
              <DataRow
                label="Cost"
                value={`$${tokenDetail.cost_usd.toFixed(6)}`}
                accent="#16a34a"
              />
            </dl>
          </div>
        )}

        {/* Output preview — expandable */}
        {output && (
          <div>
            <div
              className="mb-1.5"
              style={{
                color: "var(--color-text-muted)",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 10,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Output
            </div>
            <div style={{ maxHeight: outputExpanded ? 600 : undefined, overflowY: outputExpanded ? "auto" : undefined }}>
              <MarkdownRenderer
                content={outputExpanded ? output : outputPreview}
                maxHeight={outputExpanded ? 580 : 240}
              />
            </div>
            {outputTruncated && (
              <button
                onClick={() => setOutputExpanded(!outputExpanded)}
                style={{
                  marginTop: 6,
                  padding: "3px 10px",
                  borderRadius: 4,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-base)",
                  color: "#0d9488",
                  fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                  fontSize: 11,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                {outputExpanded ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {/* Artifacts — tabbed viewer with file-type detection */}
        {task.result?.artifacts &&
          Object.keys(task.result.artifacts).length > 0 && (
            <div>
              <div
                className="mb-1.5"
                style={{
                  color: "var(--color-text-muted)",
                  fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                  fontSize: 10,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                Artifacts ({Object.keys(task.result.artifacts).length})
              </div>
              <ArtifactViewer artifacts={task.result.artifacts} />
            </div>
          )}

        {/* Verification feedback — compact cards */}
        {task.attempt_feedback.length > 0 && (
          <div>
            <div
              className="mb-2"
              style={{
                color: "var(--color-text-muted)",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 10,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Verification Attempts
            </div>
            <div className="space-y-2">
              {task.attempt_feedback.map((fb, i) => {
                const pct = Math.round(fb.score * 100);
                const barColor = fb.passed ? "#16a34a" : "#dc2626";
                return (
                  <div
                    key={i}
                    className="rounded p-2.5"
                    style={{
                      backgroundColor: "var(--color-surface-2)",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    {/* Header row */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          style={{
                            display: "inline-block",
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            backgroundColor: barColor,
                            flexShrink: 0,
                          }}
                        />
                        <span
                          style={{
                            color: "var(--color-text-secondary)",
                            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                            fontSize: 10,
                          }}
                        >
                          #{fb.attempt}
                        </span>
                        <span
                          className="rounded px-1.5 py-0.5"
                          style={{
                            backgroundColor: "var(--color-base)",
                            border: "1px solid var(--color-border)",
                            color: "var(--color-text-muted)",
                            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                            fontSize: 9,
                            letterSpacing: "0.06em",
                          }}
                        >
                          {fb.verifier_type}
                        </span>
                      </div>
                      <span
                        style={{
                          color: barColor,
                          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                          fontSize: 12,
                          fontWeight: 600,
                        }}
                      >
                        {pct}%
                      </span>
                    </div>

                    {/* Score bar */}
                    <div
                      className="rounded-full overflow-hidden mb-2"
                      style={{
                        height: 2,
                        backgroundColor: "var(--color-border)",
                      }}
                    >
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: barColor,
                        }}
                      />
                    </div>

                    {/* Feedback text */}
                    {fb.feedback && (
                      <p
                        style={{
                          color: "var(--color-text-secondary)",
                          fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                          fontSize: 11,
                          lineHeight: 1.5,
                        }}
                      >
                        {fb.feedback}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
