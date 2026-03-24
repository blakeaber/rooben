"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

interface Credential {
  id: string;
  integration_name: string;
  env_var_name: string;
  created_at: string;
}

export function IntegrationCredentials() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [integrationName, setIntegrationName] = useState("");
  const [envVarName, setEnvVarName] = useState("");
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, "success" | "error" | null>>({});
  const [error, setError] = useState<string | null>(null);

  const fetchCredentials = useCallback(async () => {
    try {
      const res = await apiFetch<{ credentials: Credential[] }>("/api/credentials");
      setCredentials(res.credentials ?? []);
    } catch {
      // API may not be running
      setCredentials([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCredentials();
  }, [fetchCredentials]);

  const handleAdd = async () => {
    if (!integrationName.trim() || !envVarName.trim() || !value.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/api/credentials", {
        method: "POST",
        body: JSON.stringify({
          integration_name: integrationName.trim(),
          env_var_name: envVarName.trim(),
          value: value.trim(),
        }),
      });
      setIntegrationName("");
      setEnvVarName("");
      setValue("");
      setShowForm(false);
      fetchCredentials();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save credential");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiFetch(`/api/credentials/${id}`, { method: "DELETE" });
      fetchCredentials();
    } catch {
      // silent
    }
  };

  const handleTest = async (name: string) => {
    setTesting(name);
    setTestResult((prev) => ({ ...prev, [name]: null }));
    try {
      await apiFetch(`/api/credentials/test/${encodeURIComponent(name)}`, { method: "POST" });
      setTestResult((prev) => ({ ...prev, [name]: "success" }));
    } catch {
      setTestResult((prev) => ({ ...prev, [name]: "error" }));
    } finally {
      setTesting(null);
    }
  };

  const inputStyle = {
    width: "100%",
    padding: "8px 10px",
    border: "1px solid var(--color-border)",
    borderRadius: 6,
    fontFamily: "var(--font-ui)",
    fontSize: 13,
    color: "var(--color-text-primary)",
    outline: "none",
    boxSizing: "border-box" as const,
  };

  return (
    <div
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: 20,
        marginTop: 24,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <h3
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 15,
              fontWeight: 600,
              color: "var(--color-text-primary)",
              margin: 0,
            }}
          >
            Integration Credentials
          </h3>
          <p
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              color: "var(--color-text-secondary)",
              margin: "4px 0 0",
            }}
          >
            Stored encrypted with Fernet. Used by agents during workflow execution.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          style={{
            padding: "6px 14px",
            borderRadius: 6,
            border: "none",
            backgroundColor: "#0d9488",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {showForm ? "Cancel" : "Add Credential"}
        </button>
      </div>

      {/* Env var hint */}
      <div
        style={{
          padding: "8px 12px",
          borderRadius: 6,
          backgroundColor: "var(--color-surface-2)",
          border: "1px solid var(--color-surface-3)",
          fontFamily: "var(--font-ui)",
          fontSize: 11,
          color: "var(--color-text-secondary)",
          marginBottom: 16,
          lineHeight: 1.5,
        }}
      >
        Common env vars: <code style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>ANTHROPIC_API_KEY</code>,{" "}
        <code style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>OPENAI_API_KEY</code>,{" "}
        <code style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>SLACK_BOT_TOKEN</code>
      </div>

      {/* Add form */}
      {showForm && (
        <div
          style={{
            padding: 16,
            borderRadius: 6,
            border: "1px solid var(--color-border)",
            marginBottom: 16,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <input
            value={integrationName}
            onChange={(e) => setIntegrationName(e.target.value)}
            placeholder="Integration name (e.g. Slack)"
            style={inputStyle}
          />
          <input
            value={envVarName}
            onChange={(e) => setEnvVarName(e.target.value)}
            placeholder="Env variable name (e.g. SLACK_BOT_TOKEN)"
            style={{ ...inputStyle, fontFamily: "var(--font-mono)", fontSize: 12 }}
          />
          <input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Value"
            style={inputStyle}
          />
          {error && (
            <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, color: "#dc2626" }}>{error}</div>
          )}
          <button
            onClick={handleAdd}
            disabled={saving || !integrationName.trim() || !envVarName.trim() || !value.trim()}
            style={{
              padding: "8px 16px",
              borderRadius: 6,
              border: "none",
              backgroundColor: saving ? "var(--color-border-muted)" : "#0d9488",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              fontWeight: 600,
              cursor: saving ? "not-allowed" : "pointer",
              alignSelf: "flex-start",
            }}
          >
            {saving ? "Saving..." : "Save Credential"}
          </button>
        </div>
      )}

      {/* Credential list */}
      {loading ? (
        <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--color-text-muted)", padding: 16, textAlign: "center" }}>
          Loading...
        </div>
      ) : credentials.length === 0 ? (
        <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--color-text-muted)", padding: 16, textAlign: "center" }}>
          No credentials stored yet.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {credentials.map((cred) => (
            <div
              key={cred.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 12px",
                borderRadius: 6,
                border: "1px solid var(--color-surface-3)",
                backgroundColor: "var(--color-surface-1)",
              }}
            >
              <div>
                <div style={{ fontFamily: "var(--font-ui)", fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)" }}>
                  {cred.integration_name}
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-text-secondary)", marginTop: 2 }}>
                  {cred.env_var_name} = ••••••••
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => handleTest(cred.integration_name)}
                  disabled={testing === cred.integration_name}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 4,
                    border: "1px solid var(--color-border)",
                    backgroundColor:
                      testResult[cred.integration_name] === "success"
                        ? "#f0fdf4"
                        : testResult[cred.integration_name] === "error"
                          ? "#fef2f2"
                          : "var(--color-base)",
                    color:
                      testResult[cred.integration_name] === "success"
                        ? "#16a34a"
                        : testResult[cred.integration_name] === "error"
                          ? "#dc2626"
                          : "var(--color-text-secondary)",
                    fontFamily: "var(--font-ui)",
                    fontSize: 11,
                    cursor: testing === cred.integration_name ? "not-allowed" : "pointer",
                  }}
                >
                  {testing === cred.integration_name
                    ? "Testing..."
                    : testResult[cred.integration_name] === "success"
                      ? "Passed"
                      : testResult[cred.integration_name] === "error"
                        ? "Failed"
                        : "Test"}
                </button>
                <button
                  onClick={() => handleDelete(cred.id)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 4,
                    border: "1px solid #fecaca",
                    backgroundColor: "var(--color-base)",
                    color: "#dc2626",
                    fontFamily: "var(--font-ui)",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
