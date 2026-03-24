import type { TaskStatus, WorkflowStatus } from "@/lib/types";

type StatusConfig = {
  dot: string;
  text: string;
  bg: string;
  border: string;
  label: string;
};

const STATUS_CONFIG: Record<string, StatusConfig> = {
  pending: {
    dot: "var(--color-text-muted)",
    text: "var(--color-text-secondary)",
    bg: "var(--color-surface-3)",
    border: "var(--color-border)",
    label: "Pending",
  },
  planning: {
    dot: "#0d9488",
    text: "#0d9488",
    bg: "rgba(20, 184, 166, 0.1)",
    border: "rgba(20, 184, 166, 0.25)",
    label: "Planning",
  },
  ready: {
    dot: "#0d9488",
    text: "#0d9488",
    bg: "rgba(20, 184, 166, 0.1)",
    border: "rgba(20, 184, 166, 0.25)",
    label: "Ready",
  },
  in_progress: {
    dot: "#0d9488",
    text: "#0d9488",
    bg: "rgba(20, 184, 166, 0.1)",
    border: "rgba(20, 184, 166, 0.3)",
    label: "In Progress",
  },
  verifying: {
    dot: "#d97706",
    text: "#d97706",
    bg: "rgba(217, 119, 6, 0.1)",
    border: "rgba(217, 119, 6, 0.25)",
    label: "Verifying",
  },
  blocked: {
    dot: "#d97706",
    text: "#d97706",
    bg: "rgba(217, 119, 6, 0.1)",
    border: "rgba(217, 119, 6, 0.25)",
    label: "Blocked",
  },
  passed: {
    dot: "#16a34a",
    text: "#16a34a",
    bg: "rgba(22, 163, 74, 0.1)",
    border: "rgba(22, 163, 74, 0.25)",
    label: "Passed",
  },
  completed: {
    dot: "#16a34a",
    text: "#16a34a",
    bg: "rgba(22, 163, 74, 0.1)",
    border: "rgba(22, 163, 74, 0.25)",
    label: "Completed",
  },
  failed: {
    dot: "#dc2626",
    text: "#dc2626",
    bg: "rgba(220, 38, 38, 0.1)",
    border: "rgba(220, 38, 38, 0.25)",
    label: "Failed",
  },
  skipped: {
    dot: "var(--color-text-muted)",
    text: "var(--color-text-secondary)",
    bg: "var(--color-surface-3)",
    border: "var(--color-border)",
    label: "Skipped",
  },
  cancelled: {
    dot: "var(--color-text-muted)",
    text: "var(--color-text-secondary)",
    bg: "var(--color-surface-3)",
    border: "var(--color-border)",
    label: "Cancelled",
  },
};

const FALLBACK: StatusConfig = {
  dot: "var(--color-text-muted)",
  text: "var(--color-text-secondary)",
  bg: "var(--color-surface-3)",
  border: "var(--color-border)",
  label: "Unknown",
};

export function StatusBadge({
  status,
}: {
  status: TaskStatus | WorkflowStatus | string;
}) {
  const cfg = STATUS_CONFIG[status] ?? {
    ...FALLBACK,
    label: status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, " "),
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        paddingInline: "8px",
        paddingBlock: "3px",
        borderRadius: "4px",
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
        fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
        fontSize: "11px",
        fontWeight: 500,
        letterSpacing: "0.02em",
        color: cfg.text,
        whiteSpace: "nowrap",
      }}
    >
      {/* Status dot */}
      <span
        style={{
          display: "block",
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          backgroundColor: cfg.dot,
          flexShrink: 0,
        }}
        aria-hidden="true"
      />
      {cfg.label}
    </span>
  );
}
