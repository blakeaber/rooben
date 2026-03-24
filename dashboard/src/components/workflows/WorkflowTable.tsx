"use client";

import { useState, useMemo } from "react";
import type { Workflow, WorkflowStatus } from "@/lib/types";
import { WorkflowRow } from "./WorkflowRow";

interface WorkflowTableProps {
  workflows: Workflow[];
  loading: boolean;
}

type SortKey = "created_at" | "total_cost_usd" | "completed_tasks" | "replan_count" | "status";
type SortDir = "asc" | "desc";

interface SortState {
  key: SortKey;
  dir: SortDir;
}

const COLUMNS: { key: SortKey | null; label: string; align?: "center" }[] = [
  { key: "status",          label: "Status" },
  { key: null,              label: "Workflow / Spec" },
  { key: "created_at",      label: "Created" },
  { key: "completed_tasks", label: "Progress" },
  { key: "total_cost_usd",  label: "Cost / Tokens" },
  { key: null,              label: "Elapsed" },
  { key: "replan_count",    label: "Replans", align: "center" },
];

const STATUS_ORDER: Partial<Record<WorkflowStatus, number>> = {
  in_progress: 0,
  planning:    1,
  pending:     2,
  completed:   3,
  failed:      4,
  cancelled:   5,
};

function sortWorkflows(workflows: Workflow[], sort: SortState): Workflow[] {
  return [...workflows].sort((a, b) => {
    let cmp = 0;

    switch (sort.key) {
      case "status": {
        const ao = STATUS_ORDER[a.status as WorkflowStatus] ?? 99;
        const bo = STATUS_ORDER[b.status as WorkflowStatus] ?? 99;
        cmp = ao - bo;
        break;
      }
      case "created_at":
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        break;
      case "total_cost_usd":
        cmp = a.total_cost_usd - b.total_cost_usd;
        break;
      case "completed_tasks": {
        const ap = a.total_tasks > 0 ? a.completed_tasks / a.total_tasks : 0;
        const bp = b.total_tasks > 0 ? b.completed_tasks / b.total_tasks : 0;
        cmp = ap - bp;
        break;
      }
      case "replan_count":
        cmp = a.replan_count - b.replan_count;
        break;
    }

    return sort.dir === "asc" ? cmp : -cmp;
  });
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  const up = dir === "asc" && active;
  const down = dir === "desc" && active;
  return (
    <span
      aria-hidden="true"
      style={{
        display: "inline-flex",
        flexDirection: "column",
        gap: "1px",
        marginLeft: "5px",
        verticalAlign: "middle",
        opacity: active ? 1 : 0.35,
      }}
    >
      <span
        style={{
          display: "block",
          width: 0,
          height: 0,
          borderLeft: "3px solid transparent",
          borderRight: "3px solid transparent",
          borderBottom: `4px solid ${up ? "#0d9488" : "var(--color-text-muted)"}`,
        }}
      />
      <span
        style={{
          display: "block",
          width: 0,
          height: 0,
          borderLeft: "3px solid transparent",
          borderRight: "3px solid transparent",
          borderTop: `4px solid ${down ? "#0d9488" : "var(--color-text-muted)"}`,
        }}
      />
    </span>
  );
}

export function WorkflowTable({ workflows, loading }: WorkflowTableProps) {
  const [sort, setSort] = useState<SortState>({ key: "created_at", dir: "desc" });

  const sorted = useMemo(() => sortWorkflows(workflows, sort), [workflows, sort]);

  function handleSort(key: SortKey | null) {
    if (!key) return;
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "desc" }
    );
  }

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "64px 24px",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-ui, 'DM Sans', sans-serif)",
            fontSize: "14px",
            color: "var(--color-text-muted)",
          }}
        >
          Loading...
        </span>
      </div>
    );
  }

  if (workflows.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "64px 24px",
          gap: "8px",
          border: "1px solid var(--color-border)",
          borderRadius: "8px",
          background: "var(--color-base)",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-ui, 'DM Sans', sans-serif)",
            fontSize: "14px",
            fontWeight: 500,
            color: "var(--color-text-secondary)",
          }}
        >
          No workflows yet
        </span>
        <span
          style={{
            fontFamily: "var(--font-ui, 'DM Sans', sans-serif)",
            fontSize: "13px",
            color: "var(--color-text-muted)",
          }}
        >
          Run <code style={{ color: "var(--color-accent)", fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)", fontSize: "12px" }}>rooben run</code> to launch a workflow
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        overflowX: "auto",
        borderRadius: "8px",
        border: "1px solid var(--color-border)",
        background: "var(--color-base)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <table
        style={{ width: "100%", borderCollapse: "collapse" }}
        aria-label="Workflows"
      >
        <thead>
          <tr
            style={{
              borderBottom: "1px solid var(--color-border)",
              background: "var(--color-surface-2)",
            }}
          >
            {COLUMNS.map((col) => (
              <th
                key={col.label}
                style={{
                  padding: "10px 16px",
                  textAlign: col.align === "center" ? "center" : "left",
                  fontFamily: "var(--font-ui, 'DM Sans', sans-serif)",
                  fontSize: "11px",
                  fontWeight: 600,
                  letterSpacing: "0.04em",
                  color: sort.key === col.key ? "#0d9488" : "var(--color-text-secondary)",
                  whiteSpace: "nowrap",
                  userSelect: "none",
                  cursor: col.key ? "pointer" : "default",
                  transition: "color 0.15s ease",
                  textTransform: "uppercase",
                }}
                onClick={() => handleSort(col.key)}
                aria-sort={
                  sort.key === col.key
                    ? sort.dir === "asc"
                      ? "ascending"
                      : "descending"
                    : col.key
                    ? "none"
                    : undefined
                }
              >
                {col.label}
                {col.key && (
                  <SortIcon active={sort.key === col.key} dir={sort.dir} />
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((wf) => (
            <WorkflowRow key={wf.id} workflow={wf} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
