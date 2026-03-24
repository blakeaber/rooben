"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { StatusBadge } from "@/components/workflows/StatusBadge";
import { ScoreTrendChart } from "@/components/verification/ScoreTrendChart";
import { AttemptTimeline } from "@/components/verification/AttemptTimeline";
import { useTasks } from "@/hooks/useTasks";
import type { Task, VerificationFeedback } from "@/lib/types";

// ─── Run derivation helpers ──────────────────────────────────────────────────

interface RunSummary {
  run: number;
  passed: number;
  failed: number;
  total: number;
}

/** Derive distinct run numbers from all tasks' attempt_feedback. */
function deriveRuns(tasks: Task[]): RunSummary[] {
  const runMap = new Map<number, { passed: number; failed: number; total: number }>();

  for (const task of tasks) {
    for (const fb of task.attempt_feedback) {
      const existing = runMap.get(fb.attempt);
      if (existing) {
        existing.total += 1;
        if (fb.passed) existing.passed += 1;
        else existing.failed += 1;
      } else {
        runMap.set(fb.attempt, {
          total: 1,
          passed: fb.passed ? 1 : 0,
          failed: fb.passed ? 0 : 1,
        });
      }
    }
  }

  return Array.from(runMap.entries())
    .sort(([a], [b]) => a - b)
    .map(([run, counts]) => ({ run, ...counts }));
}

/** Filter a task's feedback to only entries matching the selected run. */
function feedbackForRun(task: Task, run: number): VerificationFeedback[] {
  return task.attempt_feedback.filter((fb) => fb.attempt === run);
}

/** Check whether a task participated in a given run. */
function taskInRun(task: Task, run: number): boolean {
  return task.attempt_feedback.some((fb) => fb.attempt === run);
}

// ─── Empty / loading states ───────────────────────────────────────────────────

function MonoPlaceholder({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex items-center justify-center py-16"
      style={{
        color: "var(--color-text-muted)",
        fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
        fontSize: 12,
        letterSpacing: "0.08em",
      }}
    >
      {children}
    </div>
  );
}

// ─── Task list item ───────────────────────────────────────────────────────────

function TaskListItem({
  task,
  selected,
  onClick,
  runFeedback,
}: {
  task: Task;
  selected: boolean;
  onClick: () => void;
  runFeedback: VerificationFeedback[];
}) {
  const lastFb    = runFeedback[runFeedback.length - 1];
  const lastScore = lastFb ? Math.round(lastFb.score * 100) : null;
  const lastPassed = lastFb?.passed;

  const scoreColor =
    lastScore === null
      ? "#9ca3af"
      : lastPassed
      ? "#16a34a"
      : "#dc2626";

  // Progress bar width for the last score
  const barWidth = lastScore !== null ? `${lastScore}%` : "0%";

  return (
    <button
      onClick={onClick}
      className="w-full text-left transition-colors duration-100"
      style={{
        padding: "10px 14px",
        borderBottom: "1px solid var(--color-border)",
        backgroundColor: selected ? "#f0fdfa" : "transparent",
        borderLeft: selected ? "2px solid #0d9488" : "2px solid transparent",
        cursor: "pointer",
      }}
      aria-pressed={selected}
    >
      {/* Title + status badge */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <span
          className="truncate"
          style={{
            color: selected ? "var(--color-text-primary)" : "var(--color-text-secondary)",
            fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
            fontSize: 12,
            fontWeight: selected ? 600 : 400,
            maxWidth: 160,
          }}
          title={task.title}
        >
          {task.title}
        </span>
        <StatusBadge status={task.status} />
      </div>

      {/* Attempt count + last score */}
      <div
        className="flex items-center justify-between gap-2 mb-1.5"
        style={{
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
          fontSize: 10,
        }}
      >
        <span>{runFeedback.length} attempt{runFeedback.length !== 1 ? "s" : ""}</span>
        {lastScore !== null && (
          <span style={{ color: scoreColor }}>{lastScore}%</span>
        )}
      </div>

      {/* Mini score bar */}
      {lastScore !== null && (
        <div
          className="rounded-full overflow-hidden"
          style={{ height: 2, backgroundColor: "var(--color-border)" }}
        >
          <div
            style={{
              height: "100%",
              width: barWidth,
              backgroundColor: scoreColor,
              transition: "width 0.3s ease",
            }}
          />
        </div>
      )}
    </button>
  );
}

// ─── Right panel — selected task detail ──────────────────────────────────────

function TaskDetail({ task, runFeedback }: { task: Task; runFeedback: VerificationFeedback[] }) {
  const hasFeedback = runFeedback.length > 0;

  return (
    <div className="space-y-6">
      {/* Task header */}
      <div
        className="rounded-md p-4"
        style={{
          backgroundColor: "var(--color-base)",
          border: "1px solid var(--color-border)",
          borderLeft: "2px solid #0d9488",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3
            style={{
              color: "var(--color-text-primary)",
              fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
              fontSize: 15,
              fontWeight: 600,
              lineHeight: 1.4,
            }}
          >
            {task.title}
          </h3>
          <StatusBadge status={task.status} />
        </div>

        {task.description && (
          <p
            style={{
              color: "var(--color-text-secondary)",
              fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
              fontSize: 13,
              lineHeight: 1.6,
            }}
          >
            {task.description}
          </p>
        )}

        {/* Inline telemetry row */}
        <div
          className="mt-3 flex flex-wrap gap-x-6 gap-y-1"
          style={{
            color: "var(--color-text-secondary)",
            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
            fontSize: 11,
          }}
        >
          <span>
            <span style={{ color: "var(--color-text-muted)" }}>ATTEMPT </span>
            {task.attempt}/{task.max_retries}
          </span>
          <span>
            <span style={{ color: "var(--color-text-muted)" }}>STRATEGY </span>
            {task.verification_strategy}
          </span>
          {task.result?.token_usage != null && (
            <span>
              <span style={{ color: "var(--color-text-muted)" }}>TOKENS </span>
              {task.result.token_usage.toLocaleString()}
            </span>
          )}
          {task.result?.wall_seconds != null && (
            <span>
              <span style={{ color: "var(--color-text-muted)" }}>WALL </span>
              {task.result.wall_seconds.toFixed(2)}s
            </span>
          )}
        </div>
      </div>

      {/* Score trend chart — shows ALL attempts for full context */}
      {task.attempt_feedback.length > 0 && (
        <section>
          <PanelSectionLabel>Score Trend (All Runs)</PanelSectionLabel>
          <div
            className="rounded-md p-4"
            style={{
              backgroundColor: "var(--color-base)",
              border: "1px solid var(--color-border)",
              boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
            }}
          >
            <ScoreTrendChart feedback={task.attempt_feedback} />
          </div>
        </section>
      )}

      {/* Attempt timeline — filtered to selected run */}
      <section>
        <PanelSectionLabel>
          Attempt Timeline ({runFeedback.length})
        </PanelSectionLabel>
        <AttemptTimeline feedback={runFeedback} />
      </section>
    </div>
  );
}

function PanelSectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h4
      className="mb-3 flex items-center gap-2"
      style={{
        color: "var(--color-text-secondary)",
        fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.1em",
        textTransform: "uppercase",
      }}
    >
      <span
        style={{
          display: "inline-block",
          width: 2,
          height: 10,
          backgroundColor: "#0d9488",
          borderRadius: 1,
          flexShrink: 0,
        }}
        aria-hidden="true"
      />
      {children}
    </h4>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function VerificationInspector() {
  const params     = useParams();
  const workflowId = params.id as string;

  const { tasks, loading, error } = useTasks(workflowId);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<number | null>(null);

  // Derive runs from task data
  const runs = useMemo(() => deriveRuns(tasks), [tasks]);

  // Default to latest run when runs change and no selection yet
  const activeRun = useMemo(() => {
    if (runs.length === 0) return null;
    if (selectedRun !== null && runs.some((r) => r.run === selectedRun)) return selectedRun;
    return runs[runs.length - 1].run;
  }, [runs, selectedRun]);

  // Filter tasks to those that participated in the active run
  const filteredTasks = useMemo(() => {
    if (activeRun === null) return tasks;
    return tasks.filter((t) => taskInRun(t, activeRun));
  }, [tasks, activeRun]);

  const selectedTask = filteredTasks.find((t) => t.id === selectedTaskId) ?? null;

  // Sort: most verification attempts first, then by title
  const sortedTasks = [...filteredTasks].sort((a, b) => {
    const aFb = activeRun !== null ? feedbackForRun(a, activeRun).length : a.attempt_feedback.length;
    const bFb = activeRun !== null ? feedbackForRun(b, activeRun).length : b.attempt_feedback.length;
    const diff = bFb - aFb;
    if (diff !== 0) return diff;
    return a.title.localeCompare(b.title);
  });

  // Run-level stats
  const runStats = useMemo(() => {
    if (activeRun === null) return { total: tasks.length, withFeedback: 0, passed: 0, failed: 0 };
    const tasksInRun = tasks.filter((t) => taskInRun(t, activeRun));
    let passed = 0;
    let failed = 0;
    for (const t of tasksInRun) {
      const fb = feedbackForRun(t, activeRun);
      const last = fb[fb.length - 1];
      if (last?.passed) passed++;
      else if (last && !last.passed) failed++;
    }
    return { total: tasksInRun.length, withFeedback: tasksInRun.length, passed, failed };
  }, [tasks, activeRun]);

  // ── Loading / error ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ backgroundColor: "var(--color-surface-1)", minHeight: "100vh" }}>
        <Header
          title="Verification Inspector"
          breadcrumbs={[
            { label: "Workflows", href: "/" },
            { label: workflowId.slice(0, 12), href: `/workflows/${workflowId}` },
            { label: "Verification" },
          ]}
        />
        <MonoPlaceholder>LOADING TASKS…</MonoPlaceholder>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ backgroundColor: "var(--color-surface-1)", minHeight: "100vh" }}>
        <Header
          title="Verification Inspector"
          breadcrumbs={[
            { label: "Workflows", href: "/" },
            { label: workflowId.slice(0, 12), href: `/workflows/${workflowId}` },
            { label: "Verification" },
          ]}
        />
        <MonoPlaceholder>ERROR: {error}</MonoPlaceholder>
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: "var(--color-surface-1)",
        minHeight: "100vh",
        padding: "0 0 48px",
      }}
    >
      <Header
        title="Verification Inspector"
        breadcrumbs={[
          { label: "Workflows", href: "/" },
          { label: workflowId.slice(0, 12), href: `/workflows/${workflowId}` },
          { label: "Verification" },
        ]}
      />

      {/* ── Run selector ─────────────────────────────────────────── */}
      {runs.length > 1 && (
        <div
          className="mb-4 flex items-center gap-2 rounded-md px-4 py-2.5"
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
          }}
        >
          <span
            style={{
              color: "var(--color-text-muted)",
              fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
              fontSize: 10,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              marginRight: 4,
              flexShrink: 0,
            }}
          >
            Run
          </span>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {runs.map((r) => {
              const isActive = r.run === activeRun;
              return (
                <button
                  key={r.run}
                  onClick={() => setSelectedRun(r.run)}
                  className="shrink-0 transition-colors duration-100"
                  style={{
                    padding: "4px 10px",
                    borderRadius: 9999,
                    border: isActive ? "1px solid #0d9488" : "1px solid var(--color-border)",
                    backgroundColor: isActive ? "#f0fdfa" : "transparent",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span
                    style={{
                      color: isActive ? "#0d9488" : "var(--color-text-secondary)",
                      fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                      fontSize: 11,
                      fontWeight: isActive ? 600 : 400,
                    }}
                  >
                    {r.run}
                  </span>
                  <span
                    style={{
                      color: "var(--color-text-muted)",
                      fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                      fontSize: 9,
                      letterSpacing: "0.04em",
                    }}
                  >
                    <span style={{ color: "#16a34a" }}>{r.passed}</span>
                    {"/"}
                    <span style={{ color: "#dc2626" }}>{r.failed}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Summary strip ────────────────────────────────────────── */}
      <div
        className="mb-6 flex flex-wrap items-center gap-6 rounded-md px-4 py-3"
        style={{
          backgroundColor: "var(--color-base)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        <Stat label="Tasks" value={runStats.total} />
        <Stat
          label="Passed"
          value={runStats.passed}
          accent="#16a34a"
        />
        <Stat
          label="Failed"
          value={runStats.failed}
          accent="#dc2626"
        />
        {runs.length > 1 && activeRun !== null && (
          <Stat
            label="Run"
            value={`${activeRun} / ${runs.length}`}
            accent="#0d9488"
            mono
          />
        )}

        {/* Back link */}
        <Link
          href={`/workflows/${workflowId}`}
          className="ml-auto"
          style={{
            color: "#0d9488",
            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
            fontSize: 11,
            letterSpacing: "0.06em",
            textDecoration: "none",
            padding: "4px 10px",
            borderRadius: 4,
            border: "1px solid #0d948833",
            backgroundColor: "#f0fdfa",
          }}
        >
          ← DAG VIEW
        </Link>
      </div>

      {/* ── Split layout ─────────────────────────────────────────── */}
      <div
        className="flex gap-4"
        style={{ alignItems: "flex-start" }}
      >
        {/* Left: task list panel */}
        <aside
          className="shrink-0 rounded-md overflow-hidden"
          style={{
            width: 288,
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
            position: "sticky",
            top: 16,
            maxHeight: "calc(100vh - 200px)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Panel header */}
          <div
            className="flex items-center justify-between px-3.5 py-2.5"
            style={{
              borderBottom: "1px solid var(--color-border)",
              flexShrink: 0,
            }}
          >
            <span
              style={{
                color: "var(--color-text-muted)",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 10,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Tasks
            </span>
            <span
              style={{
                color: "var(--color-text-secondary)",
                fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                fontSize: 11,
              }}
            >
              {filteredTasks.length}
            </span>
          </div>

          {/* Scrollable task list */}
          <div className="overflow-y-auto flex-1">
            {sortedTasks.length === 0 ? (
              <MonoPlaceholder>NO TASKS</MonoPlaceholder>
            ) : (
              sortedTasks.map((task) => (
                <TaskListItem
                  key={task.id}
                  task={task}
                  selected={selectedTaskId === task.id}
                  runFeedback={activeRun !== null ? feedbackForRun(task, activeRun) : task.attempt_feedback}
                  onClick={() =>
                    setSelectedTaskId(
                      selectedTaskId === task.id ? null : task.id
                    )
                  }
                />
              ))
            )}
          </div>
        </aside>

        {/* Right: detail panel */}
        <main className="flex-1 min-w-0">
          {selectedTask ? (
            <TaskDetail
              task={selectedTask}
              runFeedback={activeRun !== null ? feedbackForRun(selectedTask, activeRun) : selectedTask.attempt_feedback}
            />
          ) : (
            <div
              className="flex flex-col items-center justify-center rounded-md"
              style={{
                height: 320,
                backgroundColor: "var(--color-base)",
                border: "1px solid var(--color-border)",
                boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
              }}
            >
              <span
                style={{
                  display: "block",
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  border: "1px solid var(--color-border)",
                  marginBottom: 12,
                }}
                aria-hidden="true"
              />
              <span
                style={{
                  color: "var(--color-text-muted)",
                  fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                  fontSize: 11,
                  letterSpacing: "0.08em",
                }}
              >
                SELECT A TASK TO INSPECT
              </span>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// ─── Stat chip ────────────────────────────────────────────────────────────────

function Stat({
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
    <div className="flex flex-col gap-0.5">
      <span
        style={{
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
          fontSize: 10,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span
        style={{
          color: accent ?? "var(--color-text-primary)",
          fontFamily: mono ? 'var(--font-jetbrains, "JetBrains Mono", monospace)' : 'var(--font-dm-sans, "DM Sans", sans-serif)',
          fontSize: 15,
          fontWeight: 700,
        }}
      >
        {value}
      </span>
    </div>
  );
}
