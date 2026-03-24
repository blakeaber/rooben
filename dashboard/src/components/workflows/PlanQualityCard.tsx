"use client";

import { useState } from "react";
import type { Workflow } from "@/lib/types";

interface PlanQualityCardProps {
  workflow: Workflow;
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return "var(--color-text-muted)";
  if (score >= 0.7) return "#16a34a";
  if (score >= 0.4) return "#d97706";
  return "#dc2626";
}

const SEVERITY_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: "rgba(220, 38, 38, 0.1)", text: "#dc2626" },
  medium: { bg: "rgba(217, 119, 6, 0.1)", text: "#d97706" },
  low: { bg: "rgba(22, 163, 74, 0.1)", text: "#16a34a" },
};

export function PlanQualityCard({ workflow }: PlanQualityCardProps) {
  const [showAll, setShowAll] = useState(false);
  const pq = workflow.plan_quality;

  const checkerScore = pq?.checker?.score ?? null;
  const judgeScore = pq?.judge?.score ?? null;
  const checkerValid = pq?.checker?.valid;
  const judgeApproved = pq?.judge?.approved;
  const judgeIssues = pq?.judge?.issues ?? [];
  const checkerIssues = pq?.checker?.issues ?? [];
  const totalIssueCount = judgeIssues.length + checkerIssues.length;

  const displayedJudgeIssues = showAll ? judgeIssues : judgeIssues.slice(0, 3);

  return (
    <div
      className="rounded-md p-4"
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <h3
        style={{
          color: "var(--color-text-secondary)",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 12,
          fontWeight: 600,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          marginBottom: 12,
        }}
      >
        Plan Quality
      </h3>

      {/* Scores row */}
      <div className="flex gap-6 mb-3">
        <div>
          <span
            style={{
              color: "var(--color-text-muted)",
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              display: "block",
              marginBottom: 2,
            }}
          >
            Checker Score
          </span>
          <span
            style={{
              color: scoreColor(checkerScore),
              fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
              fontSize: 20,
              fontWeight: 700,
            }}
          >
            {checkerScore != null ? checkerScore.toFixed(2) : "Pending"}
          </span>
          {checkerValid != null && (
            <span
              style={{
                display: "block",
                color: checkerValid ? "#16a34a" : "#dc2626",
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 11,
                fontWeight: 500,
                marginTop: 2,
              }}
            >
              {checkerValid ? "\u2713 Valid" : "\u2717 Invalid"}
            </span>
          )}
        </div>

        <div>
          <span
            style={{
              color: "var(--color-text-muted)",
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              display: "block",
              marginBottom: 2,
            }}
          >
            Judge Score
          </span>
          <span
            style={{
              color: scoreColor(judgeScore),
              fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
              fontSize: 20,
              fontWeight: 700,
            }}
          >
            {judgeScore != null ? judgeScore.toFixed(2) : "Pending"}
          </span>
          {judgeApproved != null && (
            <span
              style={{
                display: "block",
                color: judgeApproved ? "#16a34a" : "#dc2626",
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 11,
                fontWeight: 500,
                marginTop: 2,
              }}
            >
              {judgeApproved ? "\u2713 Approved" : "\u2717 Rejected"}
            </span>
          )}
        </div>
      </div>

      {/* Issues */}
      {totalIssueCount > 0 && (
        <div>
          <span
            style={{
              color: "var(--color-text-secondary)",
              fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
              fontSize: 12,
              fontWeight: 500,
              marginBottom: 6,
              display: "block",
            }}
          >
            {totalIssueCount} issue{totalIssueCount !== 1 ? "s" : ""}
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {displayedJudgeIssues.map((issue, i) => {
              const colors = SEVERITY_COLORS[issue.severity] ?? SEVERITY_COLORS.medium;
              return (
                <div
                  key={i}
                  className="rounded"
                  style={{
                    backgroundColor: colors.bg,
                    border: `1px solid ${colors.text}20`,
                    padding: "6px 8px",
                  }}
                >
                  <div className="flex items-center gap-1.5" style={{ marginBottom: 2 }}>
                    <span
                      style={{
                        color: colors.text,
                        fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                        fontSize: 10,
                        fontWeight: 700,
                        textTransform: "uppercase",
                      }}
                    >
                      [{issue.severity}]
                    </span>
                    <span
                      style={{
                        color: "var(--color-text-secondary)",
                        fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                        fontSize: 10,
                      }}
                    >
                      {issue.task_id}
                    </span>
                  </div>
                  <div
                    style={{
                      color: "var(--color-text-primary)",
                      fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                      fontSize: 11,
                      lineHeight: 1.4,
                    }}
                  >
                    {issue.reason}
                    {issue.suggestion && (
                      <span style={{ color: "var(--color-text-secondary)" }}> &rarr; {issue.suggestion}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {judgeIssues.length > 3 && (
            <button
              onClick={() => setShowAll((v) => !v)}
              style={{
                color: "#0d9488",
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 11,
                fontWeight: 500,
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "4px 0",
                marginTop: 4,
              }}
            >
              {showAll ? "Show less" : `Show all ${judgeIssues.length} issues`}
            </button>
          )}
        </div>
      )}

      {/* Pending state */}
      {!pq && (
        <span
          style={{
            color: "var(--color-text-muted)",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 13,
            fontStyle: "italic",
          }}
        >
          Plan quality data not yet available
        </span>
      )}
    </div>
  );
}
