"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { TaskStatus } from "@/lib/types";

// Left-border accent color per status — muted palette for light theme
const STATUS_BORDER: Record<string, string> = {
  pending:    "var(--color-text-muted)",
  blocked:    "#d97706",
  ready:      "#0d9488",
  in_progress:"#0d9488",
  verifying:  "#7c3aed",
  passed:     "#16a34a",
  failed:     "#dc2626",
  skipped:    "var(--color-border-muted)",
  cancelled:  "var(--color-border-muted)",
};

const STATUS_DOT: Record<string, string> = {
  pending:    "var(--color-text-muted)",
  blocked:    "#d97706",
  ready:      "#0d9488",
  in_progress:"#0d9488",
  verifying:  "#7c3aed",
  passed:     "#16a34a",
  failed:     "#dc2626",
  skipped:    "var(--color-border-muted)",
  cancelled:  "var(--color-border-muted)",
};

// Workstream color palette — deterministic hash to color
const WS_COLORS = [
  "#6366f1", // indigo
  "#0d9488", // teal
  "#d97706", // amber
  "#7c3aed", // violet
  "#0284c7", // sky
  "#c026d3", // fuchsia
  "#059669", // emerald
  "#dc2626", // red
];

function wsColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  return WS_COLORS[Math.abs(hash) % WS_COLORS.length];
}

// Label shown in the status row
const STATUS_LABEL: Record<string, string> = {
  pending:    "PENDING",
  blocked:    "BLOCKED",
  ready:      "READY",
  in_progress:"IN PROGRESS",
  verifying:  "VERIFYING",
  passed:     "PASSED",
  failed:     "FAILED",
  skipped:    "SKIPPED",
  cancelled:  "CANCELLED",
};

interface TaskNodeData {
  title: string;
  status: TaskStatus;
  agent: string | null;
  workstream: string;
  attempt: number;
  maxRetries: number;
  [key: string]: unknown;
}

export function TaskNode({ data }: NodeProps) {
  const d = data as TaskNodeData;
  const borderColor = STATUS_BORDER[d.status] ?? STATUS_BORDER.pending;
  const dotColor    = STATUS_DOT[d.status]    ?? STATUS_DOT.pending;
  const isActive    = d.status === "in_progress" || d.status === "verifying";
  const label       = STATUS_LABEL[d.status]   ?? d.status.toUpperCase();

  const wsAccent = d.workstream ? wsColor(d.workstream) : "var(--color-border-muted)";

  return (
    <div
      style={{
        minWidth: 192,
        maxWidth: 240,
        backgroundColor: "var(--color-base)",
        border: `1px solid var(--color-border)`,
        borderLeftColor: borderColor,
        borderLeftWidth: 2,
        boxShadow: d.status === "passed"
          ? "0 0 12px rgba(22, 163, 74, 0.15), 0 1px 3px rgba(0,0,0,0.08)"
          : isActive
          ? "0 0 12px rgba(20, 184, 166, 0.12), 0 1px 3px rgba(0,0,0,0.08)"
          : "0 1px 3px rgba(0,0,0,0.08)",
        overflow: "hidden",
        transition: "box-shadow 0.4s ease, transform 0.2s ease",
        transform: isActive ? "scale(1.02)" : "scale(1)",
      }}
      className="rounded-md cursor-pointer select-none
                 transition-shadow duration-150 hover:shadow-md"
    >
      {/* Workstream color bar */}
      <div
        style={{
          height: 3,
          backgroundColor: wsAccent,
        }}
        title={d.workstream || undefined}
      />

      <div className="px-3 py-2">
      {/* Target handle — left side */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: "var(--color-base)",
          border: `1px solid ${borderColor}`,
          width: 8,
          height: 8,
        }}
      />

      {/* Title row */}
      <div
        className="truncate text-xs font-medium leading-snug"
        style={{ color: "var(--color-text-primary)", fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)' }}
        title={d.title}
      >
        {d.title}
      </div>

      {/* Status row */}
      <div className="mt-1.5 flex items-center gap-1.5">
        {/* Pulsing dot for active states */}
        <span
          className={isActive ? "animate-pulse" : ""}
          style={{
            display: "inline-block",
            width: 6,
            height: 6,
            borderRadius: "50%",
            backgroundColor: dotColor,
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
            fontSize: 9,
            letterSpacing: "0.08em",
            color: dotColor,
          }}
        >
          {label}
        </span>
        {d.status === "passed" && (
          <span
            className="animate-check-pop"
            style={{ color: "#16a34a", fontSize: 11, fontWeight: 700, marginLeft: 2 }}
          >
            &#10003;
          </span>
        )}
      </div>

      {/* Agent + attempt row */}
      <div
        className="mt-1 flex items-center justify-between gap-1"
        style={{
          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
          fontSize: 9,
          color: "var(--color-text-muted)",
        }}
      >
        <span className="truncate max-w-[120px]">
          {d.agent ?? "unassigned"}
        </span>
        {d.maxRetries > 0 && (
          <span style={{ flexShrink: 0 }}>
            {d.attempt}/{d.maxRetries}
          </span>
        )}
      </div>

      {/* Workstream label */}
      {d.workstream && (
        <div
          className="mt-1 truncate"
          style={{
            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
            fontSize: 8,
            letterSpacing: "0.06em",
            color: wsAccent,
            opacity: 0.7,
          }}
          title={d.workstream}
        >
          {d.workstream}
        </div>
      )}

      {/* Source handle — right side */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: "var(--color-base)",
          border: `1px solid ${borderColor}`,
          width: 8,
          height: 8,
        }}
      />
      </div>
    </div>
  );
}
