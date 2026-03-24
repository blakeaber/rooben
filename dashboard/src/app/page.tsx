"use client";

import { useState, useMemo, useEffect } from "react";
import { WorkflowTable } from "@/components/workflows/WorkflowTable";
import { useWorkflows } from "@/hooks/useWorkflows";
import { useUserLifecycle } from "@/hooks/useUserLifecycle";
import { WelcomeHero } from "@/components/home/WelcomeHero";
import { EmptyWorkflows } from "@/components/home/EmptyWorkflows";
import { ActiveWorkflowBanner } from "@/components/home/ActiveWorkflowBanner";
import { QuickActions } from "@/components/home/QuickActions";
import { ContextualHint } from "@/components/hints/ContextualHint";
import { useHints } from "@/hooks/useHints";
import type { WorkflowStatus } from "@/lib/types";

// ─── Types ──────────────────────────────────────────────────────────────────

type FilterTab = "all" | WorkflowStatus;

interface SummaryCard {
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STATUS_TABS: { key: FilterTab; label: string }[] = [
  { key: "all",         label: "All" },
  { key: "in_progress", label: "Active" },
  { key: "planning",    label: "Planning" },
  { key: "completed",   label: "Completed" },
  { key: "failed",      label: "Failed" },
  { key: "pending",     label: "Pending" },
  { key: "cancelled",   label: "Cancelled" },
];

const MONO = "var(--font-mono, 'JetBrains Mono', monospace)";
const SANS = "var(--font-ui, 'DM Sans', sans-serif)";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatUSD(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function formatCount(n: number): string {
  return n.toLocaleString();
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function SummaryReadout({ card }: { card: SummaryCard }) {
  return (
    <div
      style={{
        flex: "1 1 160px",
        minWidth: "140px",
        maxWidth: "240px",
        background: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: "8px",
        padding: "14px 16px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <div
        style={{
          fontFamily: SANS,
          fontSize: "11px",
          fontWeight: 500,
          letterSpacing: "0.04em",
          color: "var(--color-text-muted)",
          marginBottom: "6px",
          textTransform: "uppercase",
        }}
      >
        {card.label}
      </div>
      <div
        style={{
          fontFamily: MONO,
          fontSize: "26px",
          fontWeight: 700,
          lineHeight: 1,
          color: card.accent,
          letterSpacing: "-0.01em",
        }}
      >
        {card.value}
      </div>
      {card.sub && (
        <div
          style={{
            fontFamily: SANS,
            fontSize: "12px",
            color: "var(--color-text-muted)",
            marginTop: "4px",
          }}
        >
          {card.sub}
        </div>
      )}
    </div>
  );
}

function FilterTabButton({
  tab,
  active,
  count,
  onClick,
}: {
  tab: FilterTab;
  active: boolean;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "7px",
        paddingInline: "12px",
        paddingBlock: "6px",
        borderRadius: "6px",
        border: active ? "1px solid #0d9488" : "1px solid var(--color-border)",
        background: active ? "#f0fdfa" : "var(--color-base)",
        fontFamily: SANS,
        fontSize: "12px",
        fontWeight: active ? 600 : 400,
        color: active ? "#0d9488" : "var(--color-text-secondary)",
        cursor: "pointer",
        transition: "all 0.15s ease",
        whiteSpace: "nowrap",
      }}
      aria-pressed={active}
    >
      {STATUS_TABS.find((t) => t.key === tab)?.label ?? tab}
      <span
        style={{
          fontFamily: MONO,
          fontSize: "10px",
          paddingInline: "5px",
          paddingBlock: "1px",
          borderRadius: "4px",
          background: active ? "#ccfbf1" : "var(--color-surface-3)",
          color: active ? "#0d9488" : "var(--color-text-muted)",
          fontWeight: 600,
        }}
      >
        {count}
      </span>
    </button>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function WorkflowOverview() {
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [welcomeDismissed, setWelcomeDismissed] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("rooben_welcome_dismissed") === "true") {
      setWelcomeDismissed(true);
    }
  }, []);
  const statusFilter = activeTab === "all" ? undefined : activeTab;

  const { workflows, total, loading, error } = useWorkflows(statusFilter);
  const { stage, dashboard } = useUserLifecycle();
  const hints = useHints({ page: "home", stage, dashboard });

  const telemetry = useMemo(() => {
    const totalSpend    = workflows.reduce((s, w) => s + (w.total_cost_usd || 0), 0);
    const totalTokens   = workflows.reduce((s, w) => s + (w.total_tokens || 0), 0);
    const totalTasks    = workflows.reduce((s, w) => s + (w.total_tasks || 0), 0);
    const failedCount   = workflows.filter((w) => w.status === "failed").length;
    const activeCount   = workflows.filter((w) => w.status === "in_progress" || w.status === "planning").length;
    const successRate   = total > 0
      ? ((workflows.filter((w) => w.status === "completed").length / Math.max(total, 1)) * 100)
      : 0;

    return { totalSpend, totalTokens, totalTasks, failedCount, activeCount, successRate };
  }, [workflows, total]);

  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { all: total };
    for (const w of workflows) {
      counts[w.status] = (counts[w.status] ?? 0) + 1;
    }
    return {
      all:         total,
      in_progress: counts["in_progress"] ?? 0,
      planning:    counts["planning"]    ?? 0,
      completed:   counts["completed"]   ?? 0,
      failed:      counts["failed"]      ?? 0,
      pending:     counts["pending"]     ?? 0,
      cancelled:   counts["cancelled"]   ?? 0,
    } as Record<FilterTab, number>;
  }, [workflows, total]);

  const cards: SummaryCard[] = [
    {
      label:  "Total Workflows",
      value:  formatCount(total),
      sub:    `${telemetry.activeCount} active`,
      accent: "var(--color-text-primary)",
    },
    {
      label:  "Total Spend",
      value:  formatUSD(telemetry.totalSpend),
      sub:    `${formatTokens(telemetry.totalTokens)} tokens`,
      accent: telemetry.totalSpend < 1 ? "#16a34a" : telemetry.totalSpend < 10 ? "#d97706" : "#dc2626",
    },
    {
      label:  "Tasks",
      value:  formatCount(telemetry.totalTasks),
      accent: "var(--color-text-secondary)",
    },
    {
      label:  "Success Rate",
      value:  `${telemetry.successRate.toFixed(0)}%`,
      sub:    telemetry.failedCount > 0 ? `${telemetry.failedCount} failed` : "no failures",
      accent: telemetry.failedCount === 0 ? "#16a34a" : telemetry.successRate > 70 ? "#d97706" : "#dc2626",
    },
  ];

  // ── Lifecycle-aware rendering ──

  // New user: show WelcomeHero
  if (stage === "new" && !welcomeDismissed) {
    return <WelcomeHero onDismiss={() => setWelcomeDismissed(true)} />;
  }

  // Exploring: show EmptyWorkflows guidance
  if (stage === "exploring") {
    return <EmptyWorkflows />;
  }

  // Active / Power: full dashboard
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "24px",
        minHeight: "100%",
      }}
    >
      {/* ── Active workflow banner ── */}
      <ActiveWorkflowBanner workflows={workflows} />

      {/* ── Quick actions ── */}
      <QuickActions stage={stage} />

      {/* ── Contextual hints ── */}
      {hints.map((hint) => (
        <ContextualHint key={hint.id} hint={hint} />
      ))}

      {/* ── Page header ── */}
      <header>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "16px",
            flexWrap: "wrap",
          }}
        >
          <div>
            <h1
              style={{
                fontFamily: SANS,
                fontSize: "22px",
                fontWeight: 700,
                color: "var(--color-text-primary)",
                margin: 0,
                lineHeight: 1.2,
                letterSpacing: "-0.01em",
              }}
            >
              Workflows
            </h1>
            <p
              style={{
                fontFamily: SANS,
                fontSize: "14px",
                color: "var(--color-text-secondary)",
                margin: "4px 0 0",
              }}
            >
              Status, progress, and resource consumption
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            {error && (
              <span
                role="alert"
                style={{
                  fontFamily: SANS,
                  fontSize: "13px",
                  color: "#dc2626",
                  padding: "6px 12px",
                  border: "1px solid #fecaca",
                  borderRadius: "6px",
                  background: "#fef2f2",
                }}
              >
                Error — {error}
              </span>
            )}
          </div>
        </div>

        {/* Subtle separator */}
        <div
          aria-hidden="true"
          style={{
            marginTop: "16px",
            height: "1px",
            background: "var(--color-border)",
          }}
        />
      </header>

      {/* ── Summary readouts ── */}
      <section aria-label="Workflow summary">
        <div
          style={{
            display: "flex",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          {cards.map((card) => (
            <SummaryReadout key={card.label} card={card} />
          ))}
        </div>
      </section>

      {/* ── Status filter bar ── */}
      <section aria-label="Filter workflows by status">
        <div
          style={{
            display: "flex",
            gap: "6px",
            flexWrap: "wrap",
            alignItems: "center",
          }}
          role="group"
          aria-label="Workflow status filter"
        >
          {STATUS_TABS.map(({ key }) => (
            <FilterTabButton
              key={key}
              tab={key}
              active={activeTab === key}
              count={tabCounts[key] ?? 0}
              onClick={() => setActiveTab(key)}
            />
          ))}
        </div>
      </section>

      {/* ── Workflow table ── */}
      <section aria-label="Workflows table" style={{ flex: 1 }}>
        <WorkflowTable workflows={workflows} loading={loading} />
      </section>
    </div>
  );
}
