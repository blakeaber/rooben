import Link from "next/link";
import type { Workflow } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`;
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`;
  return String(tokens);
}

function costStyle(cost: number): React.CSSProperties {
  if (cost < 0.1) return { color: "#16a34a" };
  if (cost < 1.0) return { color: "#d97706" };
  return { color: "#dc2626" };
}

function elapsedLabel(created: string, completed: string | null | undefined): string {
  if (!completed) return "\u2014";
  const ms = new Date(completed).getTime() - new Date(created).getTime();
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  return `${mins}m ${rem}s`;
}

const MONO: React.CSSProperties = {
  fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
};

const DIM: React.CSSProperties = {
  color: "var(--color-text-secondary)",
  fontSize: "12px",
};

const DIMMER: React.CSSProperties = {
  color: "var(--color-text-muted)",
  fontSize: "11px",
  fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
};

export function WorkflowRow({ workflow }: { workflow: Workflow }) {
  const progress =
    workflow.total_tasks > 0
      ? (workflow.completed_tasks / workflow.total_tasks) * 100
      : 0;

  const hasFailures = workflow.failed_tasks > 0;
  const progressBarColor = hasFailures ? "#dc2626" : "#0d9488";

  return (
    <tr
      style={{
        borderBottom: "1px solid var(--color-border)",
        transition: "background 0.15s ease",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--color-surface-2)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      {/* Status */}
      <td style={{ padding: "10px 16px", whiteSpace: "nowrap" }}>
        <StatusBadge status={workflow.status} />
      </td>

      {/* Workflow ID + Spec */}
      <td style={{ padding: "10px 16px" }}>
        <Link
          href={`/workflows/${workflow.id}`}
          style={{
            ...MONO,
            fontSize: "12px",
            color: "#0d9488",
            textDecoration: "none",
            letterSpacing: "0.02em",
            fontWeight: 600,
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLAnchorElement).style.textDecoration = "underline";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLAnchorElement).style.textDecoration = "none";
          }}
        >
          {workflow.id.slice(0, 8).toUpperCase()}
        </Link>
        <div
          style={{
            ...DIMMER,
            marginTop: "2px",
            maxWidth: "160px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={workflow.spec_id}
        >
          {workflow.spec_id}
        </div>
      </td>

      {/* Created At */}
      <td style={{ padding: "10px 16px", ...DIM, whiteSpace: "nowrap" }}>
        {formatDate(workflow.created_at)}
      </td>

      {/* Progress bar + task counts */}
      <td style={{ padding: "10px 16px", minWidth: "140px" }}>
        <div
          style={{
            width: "100%",
            height: "4px",
            background: "var(--color-border)",
            borderRadius: "2px",
            overflow: "hidden",
            marginBottom: "5px",
          }}
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${Math.round(progress)}% complete`}
        >
          <div
            style={{
              height: "100%",
              width: `${progress}%`,
              background: progressBarColor,
              borderRadius: "2px",
              transition: "width 0.4s ease",
            }}
          />
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            ...MONO,
            fontSize: "11px",
          }}
        >
          <span style={{ color: "#16a34a" }}>{workflow.completed_tasks}</span>
          <span style={{ color: "var(--color-border-muted)" }}>/</span>
          <span style={{ color: "var(--color-text-secondary)" }}>{workflow.total_tasks}</span>
          {hasFailures && (
            <span style={{ color: "#dc2626" }}>
              {workflow.failed_tasks} err
            </span>
          )}
        </div>
      </td>

      {/* Cost */}
      <td style={{ padding: "10px 16px", whiteSpace: "nowrap" }}>
        <span
          style={{
            ...MONO,
            fontSize: "13px",
            fontWeight: 600,
            ...costStyle(workflow.total_cost_usd),
          }}
        >
          {formatCost(workflow.total_cost_usd)}
        </span>
        <div style={{ ...DIMMER, marginTop: "2px" }}>
          {formatTokens(workflow.total_tokens)} tok
        </div>
      </td>

      {/* Elapsed */}
      <td
        style={{
          padding: "10px 16px",
          ...MONO,
          fontSize: "12px",
          color: "var(--color-text-secondary)",
          whiteSpace: "nowrap",
        }}
      >
        {elapsedLabel(workflow.created_at, workflow.completed_at)}
      </td>

      {/* Replans */}
      <td style={{ padding: "10px 16px", textAlign: "center" }}>
        <span
          style={{
            ...MONO,
            fontSize: "12px",
            color: workflow.replan_count > 0 ? "#d97706" : "var(--color-text-muted)",
            fontWeight: workflow.replan_count > 0 ? 600 : 400,
          }}
        >
          {workflow.replan_count}
        </span>
      </td>
    </tr>
  );
}
