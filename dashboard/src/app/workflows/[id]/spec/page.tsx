"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { apiFetch } from "@/lib/api";

const PRIORITY_COLORS: Record<string, string> = {
  critical: "#dc2626",
  high: "#d97706",
  medium: "#0d9488",
  low: "#6b7280",
};

const CATEGORY_COLORS: Record<string, string> = {
  budget: "#d97706",
  time: "#2563eb",
  technology: "#7c3aed",
  security: "#dc2626",
  compliance: "#b91c1c",
  performance: "#0d9488",
  compatibility: "#059669",
  other: "#6b7280",
};

export default function SpecOverviewPage() {
  const params = useParams();
  const workflowId = params.id as string;

  const [specYaml, setSpecYaml] = useState<string | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [meta, setMeta] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showYaml, setShowYaml] = useState(false);

  useEffect(() => {
    apiFetch<{ spec_yaml: string; spec_metadata: Record<string, unknown> }>(
      `/api/workflows/${workflowId}/spec`,
    )
      .then((res) => {
        setSpecYaml(res.spec_yaml);
        setMeta(res.spec_metadata);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load spec"),
      )
      .finally(() => setLoading(false));
  }, [workflowId]);

  const shortId = workflowId.slice(0, 12);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <span style={{ color: "var(--color-text-muted)", fontFamily: "var(--font-ui)", fontSize: 14 }}>
          Loading...
        </span>
      </div>
    );
  }

  if (error || !meta) {
    return (
      <div className="animate-fade-in-up" style={{ maxWidth: 960 }}>
        <Header
          title="Specification"
          breadcrumbs={[
            { label: "Workflows", href: "/" },
            { label: shortId, href: `/workflows/${workflowId}` },
            { label: "Specification" },
          ]}
        />
        <div
          className="rounded-md py-12 text-center"
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-muted)",
            fontFamily: "var(--font-ui)",
            fontSize: 14,
          }}
        >
          {error
            ? `Error: ${error}`
            : "No specification data available for this workflow."}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in-up" style={{ maxWidth: 960 }}>
      <Header
        title="Specification"
        breadcrumbs={[
          { label: "Workflows", href: "/" },
          { label: shortId, href: `/workflows/${workflowId}` },
          { label: "Specification" },
        ]}
      />

      {/* Title & Goal */}
      <div
        className="mb-4 rounded-md p-4"
        style={{
          backgroundColor: "var(--color-base)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
          }}
        >
          Title
        </span>
        <h2
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 18,
            fontWeight: 700,
            color: "var(--color-text-primary)",
            margin: "4px 0 12px",
          }}
        >
          {meta.title}
        </h2>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
          }}
        >
          Goal
        </span>
        <p
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            color: "var(--color-text-primary)",
            lineHeight: 1.6,
            margin: "4px 0 0",
          }}
        >
          {meta.goal}
        </p>
        {meta.context && (
          <p
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              color: "var(--color-text-muted)",
              lineHeight: 1.5,
              marginTop: 8,
            }}
          >
            {meta.context}
          </p>
        )}
      </div>

      {/* Deliverables */}
      {Array.isArray(meta.deliverables) && meta.deliverables.length > 0 && (
        <div className="mb-4">
          <SectionLabel>Deliverables ({meta.deliverables.length})</SectionLabel>
          <div className="grid gap-3 md:grid-cols-2">
            {meta.deliverables.map((d: Record<string, string>, i: number) => (
              <div
                key={d.id ?? d.name ?? i}
                className="rounded-md p-4"
                style={{
                  backgroundColor: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: 13,
                      fontWeight: 600,
                      color: "var(--color-text-primary)",
                    }}
                  >
                    {d.name}
                  </span>
                  {(d.deliverable_type || d.type) && (
                    <span
                      style={{
                        padding: "1px 6px",
                        borderRadius: 4,
                        backgroundColor: "#f0fdf4",
                        color: "#166534",
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        fontWeight: 500,
                        textTransform: "uppercase",
                      }}
                    >
                      {d.deliverable_type || d.type}
                    </span>
                  )}
                </div>
                {d.description && (
                  <p
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: 12,
                      color: "var(--color-text-secondary)",
                      lineHeight: 1.5,
                      margin: 0,
                    }}
                  >
                    {d.description}
                  </p>
                )}
                {d.output_path && (
                  <div
                    style={{
                      marginTop: 6,
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--color-text-muted)",
                    }}
                  >
                    {d.output_path}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agents */}
      {Array.isArray(meta.agents) && meta.agents.length > 0 && (
        <div className="mb-4">
          <SectionLabel>Agents ({meta.agents.length})</SectionLabel>
          <div className="grid gap-3 md:grid-cols-2">
            {meta.agents.map((a: Record<string, string>, i: number) => (
              <div
                key={a.id ?? i}
                className="rounded-md p-3"
                style={{
                  backgroundColor: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--font-ui)",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "#0d9488",
                  }}
                >
                  {a.name}
                </span>
                {a.description && (
                  <p
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: 12,
                      color: "var(--color-text-secondary)",
                      lineHeight: 1.4,
                      margin: "4px 0 0",
                    }}
                  >
                    {a.description.length > 100
                      ? a.description.slice(0, 100) + "\u2026"
                      : a.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Acceptance Criteria */}
      {Array.isArray(meta.acceptance_criteria) && meta.acceptance_criteria.length > 0 && (
        <div className="mb-4">
          <SectionLabel>
            Acceptance Criteria ({meta.acceptance_criteria.length})
          </SectionLabel>
          <div
            className="rounded-md overflow-hidden"
            style={{
              backgroundColor: "var(--color-base)",
              border: "1px solid var(--color-border)",
              boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
            }}
          >
            {meta.acceptance_criteria.map((ac: Record<string, string>, i: number) => (
              <div
                key={ac.id ?? i}
                className="flex items-start gap-3 px-4 py-3"
                style={{
                  borderTop: i > 0 ? "1px solid var(--color-surface-3)" : undefined,
                }}
              >
                {ac.id && (
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--color-text-muted)",
                      minWidth: 52,
                      flexShrink: 0,
                      paddingTop: 2,
                    }}
                  >
                    {ac.id}
                  </span>
                )}
                <p
                  style={{
                    fontFamily: "var(--font-ui)",
                    fontSize: 13,
                    color: "var(--color-text-primary)",
                    lineHeight: 1.5,
                    margin: 0,
                    flex: 1,
                  }}
                >
                  {ac.description}
                </p>
                {ac.priority && (
                  <span
                    style={{
                      padding: "2px 6px",
                      borderRadius: 4,
                      backgroundColor: `${PRIORITY_COLORS[ac.priority] ?? "#6b7280"}14`,
                      color: PRIORITY_COLORS[ac.priority] ?? "#6b7280",
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      fontWeight: 500,
                      textTransform: "uppercase",
                      flexShrink: 0,
                    }}
                  >
                    {ac.priority}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Constraints */}
      {Array.isArray(meta.constraints) && meta.constraints.length > 0 && (
        <div className="mb-4">
          <SectionLabel>Constraints ({meta.constraints.length})</SectionLabel>
          <div className="flex flex-wrap gap-2">
            {meta.constraints.map((c: Record<string, unknown>, i: number) => (
              <div
                key={(c.id as string) ?? i}
                className="rounded-md p-3"
                style={{
                  backgroundColor: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                  maxWidth: 320,
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  {c.category ? (
                    <span
                      style={{
                        padding: "1px 6px",
                        borderRadius: 4,
                        backgroundColor: `${CATEGORY_COLORS[c.category as string] ?? "#6b7280"}14`,
                        color: CATEGORY_COLORS[c.category as string] ?? "#6b7280",
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        fontWeight: 500,
                        textTransform: "uppercase",
                      }}
                    >
                      {String(c.category)}
                    </span>
                  ) : null}
                  {c.hard ? (
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 9,
                        color: "#dc2626",
                        fontWeight: 600,
                      }}
                    >
                      HARD
                    </span>
                  ) : null}
                </div>
                <p
                  style={{
                    fontFamily: "var(--font-ui)",
                    fontSize: 12,
                    color: "var(--color-text-secondary)",
                    lineHeight: 1.4,
                    margin: 0,
                  }}
                >
                  {c.description as string}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Budget */}
      {meta.global_budget && (
        <div className="mb-4">
          <SectionLabel>Budget</SectionLabel>
          <div
            className="grid grid-cols-2 gap-3 sm:grid-cols-4 rounded-md p-4"
            style={{
              backgroundColor: "var(--color-base)",
              border: "1px solid var(--color-border)",
              boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
            }}
          >
            {(meta.global_budget.max_total_tokens ?? meta.global_budget.max_tokens) != null && (
              <ConfigItem
                label="Max Tokens"
                value={Number(meta.global_budget.max_total_tokens ?? meta.global_budget.max_tokens).toLocaleString()}
              />
            )}
            {(meta.global_budget.max_cost_usd) != null && (
              <ConfigItem
                label="Max Cost"
                value={`$${meta.global_budget.max_cost_usd}`}
              />
            )}
            {(meta.global_budget.max_total_tasks) != null && (
              <ConfigItem
                label="Max Tasks"
                value={meta.global_budget.max_total_tasks.toString()}
              />
            )}
            {(meta.global_budget.max_wall_seconds ?? meta.global_budget.max_time_minutes) != null && (
              <ConfigItem
                label="Max Time"
                value={meta.global_budget.max_wall_seconds
                  ? `${meta.global_budget.max_wall_seconds}s`
                  : `${meta.global_budget.max_time_minutes}min`}
              />
            )}
            {meta.global_budget.max_concurrent_agents != null && (
              <ConfigItem
                label="Max Concurrent"
                value={meta.global_budget.max_concurrent_agents.toString()}
              />
            )}

          </div>
        </div>
      )}

      {/* Raw YAML */}
      {specYaml && (
        <div className="mb-4">
          <button
            onClick={() => setShowYaml(!showYaml)}
            style={{
              background: "none",
              border: "none",
              color: "#0d9488",
              cursor: "pointer",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              fontWeight: 500,
              padding: "4px 0",
              marginBottom: 8,
            }}
          >
            {showYaml ? "Hide raw spec" : "Show raw spec"}
          </button>
          {showYaml && (
            <pre
              style={{
                backgroundColor: "var(--color-surface-2)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                padding: 16,
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                lineHeight: 1.6,
                color: "var(--color-text-primary)",
                overflow: "auto",
                maxHeight: 500,
              }}
            >
              {specYaml}
            </pre>
          )}
        </div>
      )}

      {/* Refine CTA */}
      <div
        className="rounded-md p-4 flex items-center justify-between"
        style={{
          backgroundColor: "var(--color-base)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            color: "var(--color-text-secondary)",
          }}
        >
          Want to iterate on this specification?
        </span>
        <Link
          href={`/workflows/new?refine_from=${workflowId}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 16px",
            borderRadius: 6,
            backgroundColor: "#0d9488",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            fontWeight: 600,
            textDecoration: "none",
          }}
        >
          Refine this specification
        </Link>
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="mb-2 flex items-center gap-2"
      style={{
        color: "var(--color-text-secondary)",
        fontFamily: "var(--font-ui)",
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
      }}
    >
      <span
        style={{
          display: "inline-block",
          width: 3,
          height: 14,
          backgroundColor: "#0d9488",
          borderRadius: 2,
          flexShrink: 0,
        }}
      />
      {children}
    </h3>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 9,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 13,
          fontWeight: 600,
          color: "var(--color-text-primary)",
        }}
      >
        {value}
      </span>
    </div>
  );
}
