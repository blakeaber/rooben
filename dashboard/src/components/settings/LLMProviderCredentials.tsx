"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

interface KeyStatus {
  env_var: string;
  integration: string;
  credential_type: string;
  available: boolean;
  source: string;
}

interface TestCheck {
  check: string;
  passed: boolean;
  message: string;
}

interface TestResult {
  name: string;
  passed: boolean;
  checks: TestCheck[];
}

const PROVIDERS = [
  { name: "anthropic", label: "Anthropic", envVar: "ANTHROPIC_API_KEY", description: "Claude models for planning and agents" },
  { name: "openai", label: "OpenAI", envVar: "OPENAI_API_KEY", description: "GPT models for planning and generation" },
  { name: "ollama", label: "Ollama", envVar: "", description: "Local open-source models (no key required)" },
  { name: "bedrock", label: "AWS Bedrock", envVar: "", description: "Managed models via AWS credentials" },
];

export function LLMProviderCredentials() {
  const [keyStatuses, setKeyStatuses] = useState<Record<string, KeyStatus>>({});
  const [loading, setLoading] = useState(true);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [keyValue, setKeyValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});

  const fetchStatus = useCallback(async () => {
    try {
      const res = await apiFetch<{ keys: KeyStatus[] }>("/api/credentials/status");
      const map: Record<string, KeyStatus> = {};
      for (const k of res.keys) {
        map[k.integration] = k;
      }
      setKeyStatuses(map);
    } catch {
      // API may not be running
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleSave = async (providerName: string, envVar: string) => {
    if (!keyValue.trim()) return;
    setSaving(true);
    try {
      await apiFetch("/api/credentials", {
        method: "POST",
        body: JSON.stringify({
          integration_name: providerName,
          env_var_name: envVar,
          value: keyValue.trim(),
          credential_type: "llm_provider",
        }),
      });
      setKeyValue("");
      setEditingProvider(null);
      fetchStatus();
    } catch {
      // Error handling
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (providerName: string) => {
    setTesting(providerName);
    setTestResults((prev) => {
      const next = { ...prev };
      delete next[providerName];
      return next;
    });
    try {
      const res = await apiFetch<TestResult>(
        `/api/credentials/test-llm/${encodeURIComponent(providerName)}`,
        { method: "POST", body: JSON.stringify({}) },
      );
      setTestResults((prev) => ({ ...prev, [providerName]: res }));
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [providerName]: {
          name: providerName,
          passed: false,
          checks: [{ check: "request", passed: false, message: "Failed to reach test endpoint" }],
        },
      }));
    } finally {
      setTesting(null);
    }
  };

  const statusBadge = (providerName: string) => {
    const status = keyStatuses[providerName];
    if (!status) return null;

    const colors: Record<string, { bg: string; fg: string; border: string }> = {
      env: { bg: "#eff6ff", fg: "#2563eb", border: "#bfdbfe" },
      stored: { bg: "#f0fdf4", fg: "#16a34a", border: "#bbf7d0" },
      missing: { bg: "#fef2f2", fg: "#dc2626", border: "#fecaca" },
    };
    const c = colors[status.source] || colors.missing;
    const label = status.source === "env" ? "From env" : status.source === "stored" ? "Stored" : "Not configured";

    return (
      <span
        style={{
          display: "inline-block",
          padding: "2px 8px",
          borderRadius: 12,
          backgroundColor: c.bg,
          color: c.fg,
          border: `1px solid ${c.border}`,
          fontFamily: "var(--font-ui)",
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.02em",
        }}
      >
        {label}
      </span>
    );
  };

  if (loading) {
    return (
      <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--color-text-muted)", padding: 16 }}>
        Loading provider status...
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: 20,
      }}
    >
      <h3
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 15,
          fontWeight: 600,
          color: "var(--color-text-primary)",
          margin: "0 0 4px",
        }}
      >
        LLM Providers
      </h3>
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 12,
          color: "var(--color-text-secondary)",
          margin: "0 0 16px",
        }}
      >
        Configure API keys for your LLM providers. Keys are encrypted and stored in the database.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {PROVIDERS.map((prov) => {
          const test = testResults[prov.name];
          const isEditing = editingProvider === prov.name;

          return (
            <div
              key={prov.name}
              style={{
                padding: "12px 14px",
                borderRadius: 8,
                border: "1px solid var(--color-surface-3)",
                backgroundColor: "var(--color-surface-1)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontFamily: "var(--font-ui)",
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--color-text-primary)",
                      }}
                    >
                      {prov.label}
                    </span>
                    {statusBadge(prov.name)}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: 11,
                      color: "var(--color-text-muted)",
                      marginTop: 2,
                    }}
                  >
                    {prov.description}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    onClick={() => handleTest(prov.name)}
                    disabled={testing === prov.name}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 4,
                      border: "1px solid var(--color-border)",
                      backgroundColor:
                        test?.passed === true
                          ? "#f0fdf4"
                          : test?.passed === false
                            ? "#fef2f2"
                            : "var(--color-base)",
                      color:
                        test?.passed === true
                          ? "#16a34a"
                          : test?.passed === false
                            ? "#dc2626"
                            : "var(--color-text-secondary)",
                      fontFamily: "var(--font-ui)",
                      fontSize: 11,
                      cursor: testing === prov.name ? "not-allowed" : "pointer",
                    }}
                  >
                    {testing === prov.name
                      ? "Testing..."
                      : test?.passed === true
                        ? "Passed"
                        : test?.passed === false
                          ? "Failed"
                          : "Test"}
                  </button>
                  {prov.envVar && (
                    <button
                      onClick={() => {
                        if (isEditing) {
                          setEditingProvider(null);
                          setKeyValue("");
                        } else {
                          setEditingProvider(prov.name);
                        }
                      }}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 4,
                        border: "none",
                        backgroundColor: "#0d9488",
                        color: "#ffffff",
                        fontFamily: "var(--font-ui)",
                        fontSize: 11,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      {isEditing ? "Cancel" : keyStatuses[prov.name]?.available ? "Update Key" : "Add Key"}
                    </button>
                  )}
                </div>
              </div>

              {/* Inline key editor */}
              {isEditing && prov.envVar && (
                <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                  <input
                    type="password"
                    value={keyValue}
                    onChange={(e) => setKeyValue(e.target.value)}
                    placeholder={`Enter ${prov.envVar}`}
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      borderRadius: 6,
                      border: "1px solid var(--color-border)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 12,
                      color: "var(--color-text-primary)",
                      outline: "none",
                    }}
                  />
                  <button
                    onClick={() => handleSave(prov.name, prov.envVar)}
                    disabled={saving || !keyValue.trim()}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 6,
                      border: "none",
                      backgroundColor: saving ? "var(--color-border-muted)" : "#0d9488",
                      color: "#ffffff",
                      fontFamily: "var(--font-ui)",
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: saving ? "not-allowed" : "pointer",
                    }}
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                </div>
              )}

              {/* Test result details */}
              {test && (
                <div
                  style={{
                    marginTop: 8,
                    padding: "8px 10px",
                    borderRadius: 6,
                    backgroundColor: test.passed ? "#f0fdf4" : "#fef2f2",
                    border: `1px solid ${test.passed ? "#bbf7d0" : "#fecaca"}`,
                  }}
                >
                  {test.checks.map((c, i) => (
                    <div
                      key={i}
                      style={{
                        fontFamily: "var(--font-ui)",
                        fontSize: 11,
                        color: c.passed ? "#16a34a" : "#dc2626",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        marginBottom: i < test.checks.length - 1 ? 4 : 0,
                      }}
                    >
                      <span>{c.passed ? "\u2713" : "\u2717"}</span>
                      <span>{c.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
