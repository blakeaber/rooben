"use client";

import { useState, useEffect, useRef } from "react";
import { apiFetch } from "@/lib/api";

interface SpecPreviewData {
  yaml: string;
  summary: {
    title: string;
    goal: string;
    deliverables: string[];
    agents: string[];
    acceptance_criteria: string[];
    constraints: string[];
  };
}

interface RefinementSpecPreviewProps {
  sessionId: string | null;
  completeness: number;
  /** If set, show this spec immediately instead of fetching */
  initialSpec?: string;
}

export function RefinementSpecPreview({
  sessionId,
  completeness,
  initialSpec,
}: RefinementSpecPreviewProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [preview, setPreview] = useState<SpecPreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const lastFetch = useRef(0);

  // Fetch preview when completeness changes above threshold
  useEffect(() => {
    if (!sessionId || completeness < 0.3) return;

    // Debounce: don't fetch more than once every 3 seconds
    const now = Date.now();
    if (now - lastFetch.current < 3000) return;
    lastFetch.current = now;

    setLoading(true);
    apiFetch<SpecPreviewData>(
      `/api/refine/draft?session_id=${sessionId}&preview=true`,
    )
      .then(setPreview)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [sessionId, completeness]);

  // Don't show until we have enough completeness
  if (completeness < 0.3 && !initialSpec && !preview) return null;

  const summary = preview?.summary;

  return (
    <div
      className="animate-fade-in"
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        backgroundColor: "var(--color-base)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          border: "none",
          backgroundColor: "var(--color-surface-2)",
          cursor: "pointer",
          fontFamily: "var(--font-ui)",
          fontSize: 12,
          fontWeight: 600,
          color: "var(--color-text-secondary)",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        <span>Spec Preview {loading ? "(updating...)" : ""}</span>
        <span style={{ fontSize: 14, transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)", transition: "transform 0.2s" }}>
          v
        </span>
      </button>

      {!collapsed && (
        <div style={{ padding: 14 }}>
          {summary ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {summary.title && (
                <div>
                  <div className="label-xs" style={{ marginBottom: 4 }}>Title</div>
                  <div style={{ fontFamily: "var(--font-ui)", fontSize: 13, color: "var(--color-text-primary)", fontWeight: 500 }}>
                    {summary.title}
                  </div>
                </div>
              )}
              {summary.goal && (
                <div>
                  <div className="label-xs" style={{ marginBottom: 4 }}>Goal</div>
                  <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                    {summary.goal}
                  </div>
                </div>
              )}
              {summary.deliverables.length > 0 && (
                <div>
                  <div className="label-xs" style={{ marginBottom: 4 }}>Deliverables ({summary.deliverables.length})</div>
                  <ul style={{ margin: 0, paddingLeft: 16, fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
                    {summary.deliverables.map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </div>
              )}
              {summary.constraints.length > 0 && (
                <div>
                  <div className="label-xs" style={{ marginBottom: 4 }}>Constraints ({summary.constraints.length})</div>
                  <ul style={{ margin: 0, paddingLeft: 16, fontFamily: "var(--font-ui)", fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.5 }}>
                    {summary.constraints.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
            </div>
          ) : initialSpec ? (
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-text-secondary)", whiteSpace: "pre-wrap", margin: 0, maxHeight: 200, overflow: "auto" }}>
              {initialSpec}
            </pre>
          ) : (
            <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--color-text-muted)", textAlign: "center", padding: 12 }}>
              Spec preview will appear as your project takes shape...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
