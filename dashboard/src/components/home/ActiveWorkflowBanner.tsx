"use client";

import Link from "next/link";
import type { Workflow } from "@/lib/types";

interface ActiveWorkflowBannerProps {
  workflows: Workflow[];
}

export function ActiveWorkflowBanner({ workflows }: ActiveWorkflowBannerProps) {
  const active = workflows.filter(
    (w) => w.status === "in_progress" || w.status === "planning"
  );
  const recentComplete = workflows
    .filter((w) => w.status === "completed")
    .sort(
      (a, b) =>
        new Date(b.completed_at ?? b.created_at).getTime() -
        new Date(a.completed_at ?? a.created_at).getTime()
    )
    .slice(0, 1);

  const items = [...active, ...recentComplete].slice(0, 3);
  if (items.length === 0) return null;

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        flexWrap: "wrap",
      }}
    >
      {items.map((w) => {
        const isRunning =
          w.status === "in_progress" || w.status === "planning";
        return (
          <Link
            key={w.id}
            href={`/workflows/${w.id}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              borderRadius: 8,
              border: `1px solid ${isRunning ? "rgba(13,148,136,0.3)" : "var(--color-border)"}`,
              backgroundColor: isRunning ? "#f0fdfa" : "var(--color-base)",
              textDecoration: "none",
              transition: "box-shadow 0.15s ease",
              flex: "1 1 auto",
              minWidth: 200,
              maxWidth: 360,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: isRunning ? "#0d9488" : "#16a34a",
                flexShrink: 0,
                animation: isRunning ? "live-pulse 2s ease-in-out infinite" : undefined,
              }}
            />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--color-text-muted)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {w.id.slice(0, 8)}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: 12,
                  color: isRunning
                    ? "var(--color-accent)"
                    : "var(--color-text-secondary)",
                  fontWeight: 500,
                }}
              >
                {isRunning
                  ? `Running — ${w.completed_tasks}/${w.total_tasks} tasks`
                  : `Completed — ${w.total_tasks} tasks`}
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
