"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  testIntegration,
} from "@/hooks/useIntegrations";
import { apiFetch } from "@/lib/api";
import type { IntegrationTestResult, Credential } from "@/lib/types";

// ── Shared types ──────────────────────────────────────────────────────────

interface ExtensionDetail {
  name: string;
  type: string;
  description: string;
  version: string;
  author: string;
  tags: string[];
  domain_tags: string[];
  category: string;
  use_cases: string[];
  installed: boolean;
  ready: boolean;
  checks: { check: string; passed: boolean; message: string }[];
  // Integration-specific
  source?: string;
  cost_tier?: number;
  required_env?: string[] | { name: string; description: string }[];
  missing_env?: string[];
  server_count?: number;
  servers?: any[];
  available?: boolean;
  // Template-specific
  prefill?: string;
  requires?: string[];
  template_agents?: { name: string; description: string; capabilities?: string[]; integration?: string }[];
  template_workflow_hints?: { name: string; description: string; suggested_agent?: string; depends_on?: string[] }[];
  template_input_sources?: { name: string; type: string; integration?: string; description: string }[];
  template_deliverables?: { name: string; deliverable_type: string; description: string }[];
  template_acceptance_criteria?: { description: string; priority: string }[];
  // Agent-specific
  capabilities?: string[];
  integration?: string;
  model_override?: string;
  prompt_template?: string;
}

// ── Hook: fetch from extensions API first, fall back to integrations ──────

function useExtensionDetail(name: string) {
  const [detail, setDetail] = useState<ExtensionDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    try {
      // Try unified extensions API first
      const data = await apiFetch<ExtensionDetail>(
        `/api/extensions/${encodeURIComponent(name)}`
      );
      setDetail(data);
    } catch {
      try {
        // Fall back to integration-specific endpoint
        const data = await apiFetch<any>(
          `/api/integrations/${encodeURIComponent(name)}`
        );
        setDetail({
          ...data,
          type: "integration",
          tags: data.tags || [],
          domain_tags: data.domain_tags || [],
          category: data.category || "",
          use_cases: data.use_cases || [],
          installed: true,
          ready: data.available ?? false,
          checks: [],
        });
      } catch {
        setDetail(null);
      }
    } finally {
      setLoading(false);
    }
  }, [name]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { detail, loading, refetch };
}

// ── Test result display ───────────────────────────────────────────────────

function TestResultPanel({ result }: { result: IntegrationTestResult }) {
  return (
    <div
      style={{
        backgroundColor: result.passed ? "#f0fdf4" : "#fef2f2",
        border: `1px solid ${result.passed ? "#bbf7d0" : "#fecaca"}`,
        borderRadius: "6px",
        padding: "16px",
        marginTop: "12px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          fontWeight: 600,
          color: result.passed ? "#16a34a" : "#dc2626",
          marginBottom: "10px",
        }}
      >
        {result.passed ? "All checks passed" : "Some checks failed"}
      </div>
      {result.checks.map((check, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 0",
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: check.passed ? "#16a34a" : "#dc2626",
          }}
        >
          <span>{check.passed ? "\u2713" : "\u2717"}</span>
          <span>{check.message}</span>
        </div>
      ))}
    </div>
  );
}

// ── Readiness checks display ──────────────────────────────────────────────

function ReadinessChecks({ checks }: { checks: { check: string; passed: boolean; message: string }[] }) {
  if (!checks || checks.length === 0) return null;
  const allPassed = checks.every((c) => c.passed);
  return (
    <div
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: "8px",
        padding: "20px",
        marginBottom: "24px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--color-text-secondary)",
          marginBottom: "14px",
        }}
      >
        Readiness Status
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          fontWeight: 600,
          color: allPassed ? "#16a34a" : "#dc2626",
          marginBottom: "10px",
        }}
      >
        {allPassed ? "Ready" : "Not Ready"}
      </div>
      {checks.map((check, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 0",
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: check.passed ? "#16a34a" : "#dc2626",
          }}
        >
          <span>{check.passed ? "\u2713" : "\u2717"}</span>
          <span>{check.message}</span>
        </div>
      ))}
    </div>
  );
}

// ── Editable config form ──────────────────────────────────────────────────

function EditForm({
  name,
  initialDescription,
  initialDomainTags,
  onSaved,
}: {
  name: string;
  initialDescription: string;
  initialDomainTags: string[];
  onSaved: () => void;
}) {
  const [description, setDescription] = useState(initialDescription);
  const [tags, setTags] = useState(initialDomainTags.join(", "));
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        style={{
          padding: "6px 14px",
          borderRadius: "6px",
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-base)",
          color: "var(--color-text-secondary)",
          fontFamily: "var(--font-ui)",
          fontSize: "12px",
          cursor: "pointer",
        }}
      >
        Edit Configuration
      </button>
    );
  }

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiFetch(`/api/integrations/${encodeURIComponent(name)}`, {
        method: "PUT",
        body: JSON.stringify({
          description,
          domain_tags: tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean),
        }),
      });
      setEditing(false);
      onSaved();
    } catch {
      // silently handle
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: "8px",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--color-text-secondary)",
        }}
      >
        Edit Configuration
      </div>
      <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <span style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-secondary)" }}>
          Description
        </span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            padding: "8px",
            border: "1px solid var(--color-border)",
            borderRadius: "4px",
            resize: "vertical",
          }}
        />
      </label>
      <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <span style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-secondary)" }}>
          Domain Tags (comma-separated)
        </span>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            padding: "8px",
            border: "1px solid var(--color-border)",
            borderRadius: "4px",
          }}
        />
      </label>
      <div style={{ display: "flex", gap: "8px" }}>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            padding: "6px 16px",
            borderRadius: "6px",
            border: "none",
            backgroundColor: "#0d9488",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: "12px",
            fontWeight: 600,
            cursor: saving ? "wait" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <button
          onClick={() => setEditing(false)}
          style={{
            padding: "6px 16px",
            borderRadius: "6px",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-base)",
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-ui)",
            fontSize: "12px",
            cursor: "pointer",
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Credentials section ───────────────────────────────────────────────────

function CredentialsSection({ integrationName }: { integrationName: string }) {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [envVarName, setEnvVarName] = useState("");
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [testingCreds, setTestingCreds] = useState(false);
  const [credTestResult, setCredTestResult] = useState<IntegrationTestResult | null>(null);

  const fetchCreds = async () => {
    try {
      const res = await apiFetch<{ credentials: Credential[] }>(
        `/api/credentials?integration=${encodeURIComponent(integrationName)}`
      );
      setCredentials(res.credentials);
    } catch {
      // silently handle
    }
  };

  useState(() => {
    fetchCreds();
  });

  const handleAdd = async () => {
    if (!envVarName.trim() || !value.trim()) return;
    setSaving(true);
    try {
      await apiFetch("/api/credentials", {
        method: "POST",
        body: JSON.stringify({
          integration_name: integrationName,
          env_var_name: envVarName.trim(),
          value: value.trim(),
        }),
      });
      setEnvVarName("");
      setValue("");
      fetchCreds();
    } catch {
      // silently handle
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiFetch(`/api/credentials/${id}`, { method: "DELETE" });
      fetchCreds();
    } catch {
      // silently handle
    }
  };

  const handleTestCreds = async () => {
    setTestingCreds(true);
    setCredTestResult(null);
    try {
      const res = await apiFetch<IntegrationTestResult>(
        `/api/credentials/test/${encodeURIComponent(integrationName)}`,
        { method: "POST" }
      );
      setCredTestResult(res);
    } catch {
      // silently handle
    } finally {
      setTestingCreds(false);
    }
  };

  return (
    <div
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: "8px",
        padding: "20px",
        marginBottom: "24px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--color-text-secondary)",
          marginBottom: "14px",
        }}
      >
        Stored Credentials
      </div>

      {credentials.length > 0 ? (
        <div style={{ marginBottom: "16px" }}>
          {credentials.map((cred) => (
            <div
              key={cred.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 0",
                borderBottom: "1px solid var(--color-surface-3)",
              }}
            >
              <div>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--color-text-primary)" }}>
                  {cred.env_var_name}
                </span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--color-text-muted)", marginLeft: "8px" }}>
                  {cred.value}
                </span>
              </div>
              <button
                onClick={() => handleDelete(cred.id)}
                style={{
                  padding: "2px 8px",
                  borderRadius: "4px",
                  border: "1px solid #fecaca",
                  backgroundColor: "#fef2f2",
                  color: "#dc2626",
                  fontFamily: "var(--font-ui)",
                  fontSize: "10px",
                  cursor: "pointer",
                }}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "16px" }}>
          No credentials stored for this integration.
        </p>
      )}

      <div style={{ display: "flex", gap: "8px", alignItems: "flex-end" }}>
        <div style={{ flex: 1 }}>
          <span style={{ fontFamily: "var(--font-ui)", fontSize: "11px", color: "var(--color-text-muted)", display: "block", marginBottom: "2px" }}>
            Env Variable
          </span>
          <input
            value={envVarName}
            onChange={(e) => setEnvVarName(e.target.value)}
            placeholder="e.g. API_KEY"
            style={{ fontFamily: "var(--font-mono)", fontSize: "12px", padding: "6px 8px", border: "1px solid var(--color-border)", borderRadius: "4px", width: "100%" }}
          />
        </div>
        <div style={{ flex: 1 }}>
          <span style={{ fontFamily: "var(--font-ui)", fontSize: "11px", color: "var(--color-text-muted)", display: "block", marginBottom: "2px" }}>
            Value
          </span>
          <input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Secret value"
            style={{ fontFamily: "var(--font-mono)", fontSize: "12px", padding: "6px 8px", border: "1px solid var(--color-border)", borderRadius: "4px", width: "100%" }}
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={saving || !envVarName.trim() || !value.trim()}
          style={{
            padding: "6px 14px",
            borderRadius: "6px",
            border: "none",
            backgroundColor: envVarName.trim() && value.trim() ? "#0d9488" : "var(--color-border-muted)",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: "12px",
            fontWeight: 600,
            cursor: envVarName.trim() && value.trim() ? "pointer" : "not-allowed",
            whiteSpace: "nowrap",
          }}
        >
          {saving ? "..." : "Add"}
        </button>
      </div>

      {credentials.length > 0 && (
        <div style={{ marginTop: "16px" }}>
          <button
            onClick={handleTestCreds}
            disabled={testingCreds}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-base)",
              color: "var(--color-text-secondary)",
              fontFamily: "var(--font-ui)",
              fontSize: "12px",
              cursor: testingCreds ? "wait" : "pointer",
            }}
          >
            {testingCreds ? "Testing..." : "Test with Stored Credentials"}
          </button>
          {credTestResult && <TestResultPanel result={credTestResult} />}
        </div>
      )}
    </div>
  );
}

// ── Template detail panel ─────────────────────────────────────────────────

function TemplateDetail({ ext }: { ext: ExtensionDetail }) {
  const router = useRouter();

  return (
    <>
      {/* Workstream preview */}
      {ext.template_workflow_hints && ext.template_workflow_hints.length > 0 && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Workstream
          </div>
          {ext.template_workflow_hints.map((hint, i) => (
            <div key={i} style={{ padding: "8px 0", borderBottom: i < ext.template_workflow_hints!.length - 1 ? "1px solid var(--color-surface-3)" : "none" }}>
              <div style={{ fontFamily: "var(--font-ui)", fontSize: "13px", fontWeight: 600, color: "var(--color-text-primary)" }}>
                {i + 1}. {hint.name}
              </div>
              <div style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                {hint.description}
              </div>
              {hint.suggested_agent && (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "#0d9488", marginTop: "4px", display: "inline-block" }}>
                  Agent: {hint.suggested_agent}
                </span>
              )}
              {hint.depends_on && hint.depends_on.length > 0 && (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--color-text-muted)", marginLeft: "12px" }}>
                  After: {hint.depends_on.join(", ")}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Agents */}
      {ext.template_agents && ext.template_agents.length > 0 && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Agent Roster
          </div>
          {ext.template_agents.map((agent, i) => (
            <div key={i} style={{ padding: "8px 0", borderBottom: i < ext.template_agents!.length - 1 ? "1px solid var(--color-surface-3)" : "none" }}>
              <div style={{ fontFamily: "var(--font-ui)", fontSize: "13px", fontWeight: 600, color: "var(--color-text-primary)" }}>
                {agent.name}
              </div>
              <div style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                {agent.description}
              </div>
              {agent.capabilities && agent.capabilities.length > 0 && (
                <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "6px" }}>
                  {agent.capabilities.map((cap) => (
                    <span key={cap} style={{ padding: "2px 8px", borderRadius: "4px", fontSize: "10px", fontFamily: "var(--font-mono)", backgroundColor: "var(--color-surface-3)", color: "var(--color-text-primary)" }}>
                      {cap}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Deliverables */}
      {ext.template_deliverables && ext.template_deliverables.length > 0 && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Deliverables
          </div>
          {ext.template_deliverables.map((d, i) => (
            <div key={i} style={{ padding: "8px 0", borderBottom: i < ext.template_deliverables!.length - 1 ? "1px solid var(--color-surface-3)" : "none" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontFamily: "var(--font-ui)", fontSize: "13px", fontWeight: 600, color: "var(--color-text-primary)" }}>
                  {d.name}
                </span>
                <span style={{ padding: "2px 6px", borderRadius: "4px", fontSize: "10px", fontFamily: "var(--font-mono)", backgroundColor: "#eff6ff", color: "#2563eb" }}>
                  {d.deliverable_type}
                </span>
              </div>
              <div style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-secondary)", marginTop: "2px" }}>
                {d.description}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Acceptance criteria */}
      {ext.template_acceptance_criteria && ext.template_acceptance_criteria.length > 0 && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Acceptance Criteria
          </div>
          {ext.template_acceptance_criteria.map((ac, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 0" }}>
              <span style={{
                padding: "2px 6px", borderRadius: "4px", fontSize: "10px", fontFamily: "var(--font-mono)", fontWeight: 600,
                backgroundColor: ac.priority === "critical" ? "#fef2f2" : ac.priority === "high" ? "#fffbeb" : "var(--color-surface-3)",
                color: ac.priority === "critical" ? "#dc2626" : ac.priority === "high" ? "#d97706" : "var(--color-text-secondary)",
              }}>
                {ac.priority}
              </span>
              <span style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-primary)" }}>
                {ac.description}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Use Template button */}
      <button
        onClick={() => router.push(`/workflows/new?template=${encodeURIComponent(ext.name)}`)}
        style={{
          padding: "10px 24px",
          borderRadius: "6px",
          border: "none",
          backgroundColor: "#0d9488",
          color: "#ffffff",
          fontFamily: "var(--font-ui)",
          fontSize: "13px",
          fontWeight: 600,
          cursor: "pointer",
          marginBottom: "24px",
        }}
      >
        Use Template
      </button>
    </>
  );
}

// ── Agent detail panel ────────────────────────────────────────────────────

function AgentDetail({ ext }: { ext: ExtensionDetail }) {
  return (
    <>
      {/* Capabilities */}
      {ext.capabilities && ext.capabilities.length > 0 && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Capabilities
          </div>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {ext.capabilities.map((cap) => (
              <span key={cap} style={{ padding: "4px 10px", borderRadius: "4px", fontSize: "11px", fontFamily: "var(--font-mono)", backgroundColor: "var(--color-surface-3)", color: "var(--color-text-primary)" }}>
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Integration dependency */}
      {ext.integration && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Integration Dependency
          </div>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--color-text-primary)" }}>
            {ext.integration}
          </span>
        </div>
      )}

      {/* Prompt preview */}
      {ext.prompt_template && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Prompt Preview
          </div>
          <pre style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--color-text-secondary)", backgroundColor: "var(--color-surface-2)", padding: "12px", borderRadius: "4px", overflow: "auto", whiteSpace: "pre-wrap" }}>
            {ext.prompt_template}
          </pre>
        </div>
      )}
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  integration: "Data Source",
  template: "Template",
  agent: "Agent",
};

export default function ExtensionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const name = decodeURIComponent(params.id as string);
  const { detail, loading, refetch } = useExtensionDetail(name);
  const [testResult, setTestResult] = useState<IntegrationTestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testIntegration(name);
      setTestResult(res);
    } catch {
      // silently handle
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "60px", textAlign: "center", fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--color-text-muted)", animation: "live-pulse 2s ease-in-out infinite" }}>
        Loading...
      </div>
    );
  }

  if (!detail) {
    return (
      <div style={{ padding: "60px", textAlign: "center" }}>
        <p style={{ fontFamily: "var(--font-ui)", fontSize: "14px", color: "#dc2626" }}>
          Extension not found.
        </p>
        <button
          onClick={() => router.push("/integrations")}
          style={{ marginTop: "12px", padding: "6px 14px", borderRadius: "6px", border: "1px solid var(--color-border)", backgroundColor: "var(--color-base)", fontFamily: "var(--font-ui)", fontSize: "12px", cursor: "pointer", color: "var(--color-text-secondary)" }}
        >
          Back to Integrations
        </button>
      </div>
    );
  }

  const typeLabel = TYPE_LABELS[detail.type] || detail.type;

  return (
    <div className="animate-fade-in-up" style={{ maxWidth: "900px" }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: "20px" }}>
        <button
          onClick={() => router.push("/integrations")}
          style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "#0d9488", background: "none", border: "none", cursor: "pointer", padding: 0 }}
        >
          &larr; Integrations Hub
        </button>
      </div>

      {/* Header */}
      <div style={{ marginBottom: "28px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
          <span
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              backgroundColor: detail.ready ? "#16a34a" : "#dc2626",
            }}
          />
          <h1 style={{ fontFamily: "var(--font-ui)", fontSize: "22px", fontWeight: 700, color: "var(--color-text-primary)", margin: 0 }}>
            {detail.name}
          </h1>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: "9999px",
              fontSize: "10px",
              fontFamily: "var(--font-mono)",
              fontWeight: 600,
              textTransform: "uppercase",
              backgroundColor: detail.type === "integration" ? "#f0fdf4" : detail.type === "template" ? "#eff6ff" : "#fefce8",
              color: detail.type === "integration" ? "#16a34a" : detail.type === "template" ? "#2563eb" : "#d97706",
            }}
          >
            {typeLabel}
          </span>
          {detail.source && (
            <span
              style={{
                padding: "2px 8px",
                borderRadius: "9999px",
                fontSize: "10px",
                fontFamily: "var(--font-mono)",
                fontWeight: 600,
                textTransform: "uppercase",
                backgroundColor: "var(--color-surface-3)",
                color: "var(--color-text-secondary)",
              }}
            >
              {detail.source}
            </span>
          )}
        </div>
        <p style={{ fontFamily: "var(--font-ui)", fontSize: "13px", color: "var(--color-text-secondary)", margin: 0 }}>
          {detail.description}
        </p>
        <div style={{ borderBottom: "1px solid var(--color-border)", marginTop: "16px" }} />
      </div>

      {/* Info grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
        <div style={{ backgroundColor: "var(--color-base)", border: "1px solid var(--color-border)", borderRadius: "8px", padding: "20px" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Information
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {[
              { label: "Author", value: detail.author || "\u2014" },
              { label: "Version", value: detail.version },
              { label: "Type", value: typeLabel },
              ...(detail.type === "integration" && detail.cost_tier !== undefined
                ? [{ label: "Cost Tier", value: `${"$".repeat(detail.cost_tier) || "Free"} (${["Free", "Low", "Medium", "High"][detail.cost_tier]})` }]
                : []),
              ...(detail.type === "integration" && detail.server_count !== undefined
                ? [{ label: "Servers", value: detail.server_count.toString() }]
                : []),
              ...(detail.requires && detail.requires.length > 0
                ? [{ label: "Requires", value: detail.requires.join(", ") }]
                : []),
            ].map((row) => (
              <div key={row.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-muted)" }}>{row.label}</span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--color-text-primary)" }}>{row.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ backgroundColor: "var(--color-base)", border: "1px solid var(--color-border)", borderRadius: "8px", padding: "20px" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
            Domain Tags
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {detail.domain_tags.length > 0 ? (
              detail.domain_tags.map((tag) => (
                <span key={tag} style={{ display: "inline-block", padding: "4px 10px", borderRadius: "4px", fontSize: "11px", fontFamily: "var(--font-mono)", backgroundColor: "var(--color-surface-3)", color: "var(--color-text-primary)" }}>
                  {tag}
                </span>
              ))
            ) : (
              <span style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-muted)" }}>
                No domain tags
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Readiness checks */}
      <ReadinessChecks checks={detail.checks} />

      {/* Type-specific rendering */}
      {detail.type === "template" && <TemplateDetail ext={detail} />}
      {detail.type === "agent" && <AgentDetail ext={detail} />}

      {/* Integration-specific: env vars, credentials, test */}
      {detail.type === "integration" && (
        <>
          {/* Environment variables */}
          <div style={{ backgroundColor: "var(--color-base)", border: "1px solid var(--color-border)", borderRadius: "8px", padding: "20px", marginBottom: "24px" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)", marginBottom: "14px" }}>
              Required Environment Variables
            </div>
            {(!detail.required_env || detail.required_env.length === 0) ? (
              <span style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "var(--color-text-muted)" }}>
                No environment variables required.
              </span>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border)", textAlign: "left" }}>
                    <th style={{ padding: "6px 0", color: "var(--color-text-muted)", fontSize: "10px", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600 }}>Variable</th>
                    <th style={{ padding: "6px 0", color: "var(--color-text-muted)", fontSize: "10px", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, textAlign: "right" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.required_env.map((env) => {
                    const envName = typeof env === "string" ? env : env.name;
                    const isMissing = detail.missing_env?.includes(envName);
                    return (
                      <tr key={envName} style={{ borderBottom: "1px solid var(--color-surface-3)" }}>
                        <td style={{ padding: "8px 0", color: "var(--color-text-primary)" }}>{envName}</td>
                        <td style={{ padding: "8px 0", textAlign: "right", color: isMissing ? "#dc2626" : "#16a34a", fontWeight: 600 }}>
                          {isMissing ? "Missing" : "Set"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Credentials */}
          <CredentialsSection integrationName={detail.name} />

          {/* Test Connection */}
          <div style={{ backgroundColor: "var(--color-base)", border: "1px solid var(--color-border)", borderRadius: "8px", padding: "20px", marginBottom: "24px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: testResult ? "0" : undefined }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-secondary)" }}>
                Test Connection
              </div>
              <button
                onClick={handleTest}
                disabled={testing}
                style={{ padding: "6px 16px", borderRadius: "6px", border: "none", backgroundColor: "#0d9488", color: "#ffffff", fontFamily: "var(--font-ui)", fontSize: "12px", fontWeight: 600, cursor: testing ? "wait" : "pointer", opacity: testing ? 0.6 : 1 }}
              >
                {testing ? "Testing..." : "Run Test"}
              </button>
            </div>
            {testResult && <TestResultPanel result={testResult} />}
          </div>

          {/* Edit (user only) */}
          {detail.source === "user" && (
            <div style={{ marginBottom: "24px" }}>
              <EditForm
                name={detail.name}
                initialDescription={detail.description}
                initialDomainTags={detail.domain_tags}
                onSaved={refetch}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
