"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSetup } from "@/lib/use-setup";
import { useConnection } from "@/lib/connection-context";
import { apiFetch } from "@/lib/api";

type Step = "welcome" | "llm-provider";

const PERSONA_KEY = "rooben_persona";

interface PersonaCard {
  id: string;
  title: string;
  description: string;
  route: string;
  icon?: string;
}

const PERSONAS: PersonaCard[] = [
  {
    id: "operator",
    title: "I have a deliverable to produce",
    description:
      "Reports, analyses, briefings — describe what you need, get a verified first draft.",
    route: "/workflows/new?persona=operator",
    icon: "\u{1F4CB}",
  },
  {
    id: "builder",
    title: "I want to build something",
    description:
      "APIs, pipelines, dashboards — multi-agent construction with tests that pass.",
    route: "/workflows/new?persona=builder",
    icon: "\u{1F6E0}",
  },
  {
    id: "optimizer",
    title: "I want to automate recurring work",
    description:
      "Set up a workflow once, schedule it to run automatically on your terms.",
    route: "/workflows/new?persona=optimizer",
    icon: "\u23F0",
  },
];

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

const LLM_PROVIDERS = [
  { name: "anthropic", label: "Anthropic (Claude)", envVar: "ANTHROPIC_API_KEY" },
  { name: "openai", label: "OpenAI (GPT)", envVar: "OPENAI_API_KEY" },
  { name: "ollama", label: "Ollama (Local)", envVar: "" },
];

function LLMProviderStep({ onComplete }: { onComplete: () => void }) {
  const [selectedProvider, setSelectedProvider] = useState("anthropic");
  const [keyValue, setKeyValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testPassed, setTestPassed] = useState<boolean | null>(null);
  const [testChecks, setTestChecks] = useState<TestCheck[]>([]);
  const [detectedKey, setDetectedKey] = useState<string | null>(null);

  // Check if a key is already available (from env or stored)
  useEffect(() => {
    apiFetch<{ keys: KeyStatus[] }>("/api/credentials/status")
      .then((res) => {
        for (const k of res.keys) {
          if (k.credential_type === "llm_provider" && k.available) {
            setDetectedKey(k.integration);
            setSelectedProvider(k.integration);
          }
        }
      })
      .catch(() => {});
  }, []);

  const provider = LLM_PROVIDERS.find((p) => p.name === selectedProvider)!;

  const handleSaveAndTest = async () => {
    if (provider.envVar && keyValue.trim()) {
      setSaving(true);
      try {
        await apiFetch("/api/credentials", {
          method: "POST",
          body: JSON.stringify({
            integration_name: selectedProvider,
            env_var_name: provider.envVar,
            value: keyValue.trim(),
            credential_type: "llm_provider",
          }),
        });
      } catch {
        setSaving(false);
        return;
      }
      setSaving(false);
    }

    // Test
    setTesting(true);
    setTestPassed(null);
    try {
      const res = await apiFetch<{ passed: boolean; checks: TestCheck[] }>(
        `/api/credentials/test-llm/${encodeURIComponent(selectedProvider)}`,
        { method: "POST", body: JSON.stringify({}) },
      );
      setTestPassed(res.passed);
      setTestChecks(res.checks);
    } catch {
      setTestPassed(false);
      setTestChecks([{ check: "request", passed: false, message: "Failed to reach test endpoint" }]);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="animate-fade-in-up">
      <h2
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 22,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          margin: "0 0 4px",
          textAlign: "center",
        }}
      >
        Connect your LLM Provider
      </h2>
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 14,
          color: "var(--color-text-secondary)",
          margin: "0 0 24px",
          textAlign: "center",
        }}
      >
        {detectedKey
          ? `Key detected for ${detectedKey} — you can continue or change provider.`
          : "Enter your API key, or use Ollama for local models."}
      </p>

      <div
        style={{
          backgroundColor: "var(--color-base)",
          border: "1px solid var(--color-border)",
          borderRadius: 10,
          padding: 24,
        }}
      >
        {/* Provider selector */}
        <label
          style={{
            display: "block",
            marginBottom: 6,
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-ui)",
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Provider
        </label>
        <select
          value={selectedProvider}
          onChange={(e) => {
            setSelectedProvider(e.target.value);
            setKeyValue("");
            setTestPassed(null);
            setTestChecks([]);
          }}
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-base)",
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            color: "var(--color-text-primary)",
            outline: "none",
            marginBottom: 16,
          }}
        >
          {LLM_PROVIDERS.map((p) => (
            <option key={p.name} value={p.name}>
              {p.label}
            </option>
          ))}
        </select>

        {/* Key input (not shown for Ollama) */}
        {provider.envVar && (
          <>
            <label
              style={{
                display: "block",
                marginBottom: 6,
                color: "var(--color-text-secondary)",
                fontFamily: "var(--font-ui)",
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              API Key
            </label>
            <input
              type="password"
              value={keyValue}
              onChange={(e) => setKeyValue(e.target.value)}
              placeholder={`Enter your ${provider.envVar}`}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: 6,
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-base)",
                fontFamily: "var(--font-mono)",
                fontSize: 13,
                color: "var(--color-text-primary)",
                outline: "none",
                marginBottom: 12,
              }}
            />
          </>
        )}

        <button
          onClick={handleSaveAndTest}
          disabled={saving || testing}
          style={{
            padding: "8px 20px",
            borderRadius: 6,
            border: "none",
            backgroundColor: saving || testing ? "var(--color-border-muted)" : "#0d9488",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            fontWeight: 600,
            cursor: saving || testing ? "not-allowed" : "pointer",
          }}
        >
          {saving ? "Saving..." : testing ? "Testing..." : "Test Connection"}
        </button>

        {/* Test result */}
        {testPassed !== null && (
          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              borderRadius: 6,
              backgroundColor: testPassed ? "#f0fdf4" : "#fef2f2",
              border: `1px solid ${testPassed ? "#bbf7d0" : "#fecaca"}`,
            }}
          >
            {testChecks.map((c, i) => (
              <div
                key={i}
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: 12,
                  color: c.passed ? "#16a34a" : "#dc2626",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: i < testChecks.length - 1 ? 4 : 0,
                }}
              >
                <span>{c.passed ? "\u2713" : "\u2717"}</span>
                <span>{c.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          marginTop: 16,
        }}
      >
        <button
          onClick={onComplete}
          style={{
            padding: "8px 20px",
            borderRadius: 6,
            border: "none",
            backgroundColor: "var(--color-accent)",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Continue
        </button>
      </div>
    </div>
  );
}

export function SetupWizard() {
  const [step, setStep] = useState<Step>("welcome");
  const { completeSetup } = useSetup();
  const { recheck } = useConnection();
  const router = useRouter();

  const handleChoosePath = (persona: PersonaCard) => {
    localStorage.setItem(PERSONA_KEY, persona.id);
    completeSetup();
    router.push(persona.route);
  };

  const handleSkipToApp = () => {
    completeSetup();
    router.push("/");
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        backgroundColor: "var(--color-surface-2)",
        padding: 24,
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 560,
        }}
      >
        {/* -- Step: Welcome -- */}
        {step === "welcome" && (
          <div
            className="animate-fade-in-up"
            style={{ textAlign: "center" }}
          >
            {/* Rooben brand mark */}
            <div
              className="animate-fade-in-up stagger-1"
              style={{
                width: 56,
                height: 56,
                borderRadius: 14,
                background: "var(--gradient-rooben)",
                backgroundSize: "200% 200%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 24px",
                boxShadow: "0 4px 16px rgba(20, 184, 166, 0.15)",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 24,
                  fontWeight: 700,
                  color: "#ffffff",
                }}
              >
                R
              </span>
            </div>

            <h1
              className="animate-fade-in-up stagger-2"
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: 32,
                fontWeight: 700,
                color: "var(--color-text-primary)",
                letterSpacing: "-0.02em",
                margin: "0 0 12px",
              }}
            >
              Welcome to Rooben
            </h1>
            <p
              className="animate-fade-in-up stagger-3"
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: 16,
                color: "var(--color-text-secondary)",
                lineHeight: 1.6,
                margin: "0 0 8px",
                maxWidth: 440,
                marginInline: "auto",
              }}
            >
              Describe the end result you want. AI agents plan, execute,
              verify, and deliver it.
            </p>
            <p
              className="animate-fade-in-up stagger-3"
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: 13,
                color: "var(--color-text-muted)",
                margin: "0 0 20px",
              }}
            >
              Every output is verified. You always know what it costs.
            </p>

            {/* Trust badges */}
            <div
              className="animate-fade-in-up stagger-4"
              style={{
                display: "flex",
                gap: 10,
                justifyContent: "center",
                flexWrap: "wrap",
                marginBottom: 32,
              }}
            >
              {[
                { label: "Budget-enforced", icon: "\u{1F6E1}" },
                { label: "Verified outputs", icon: "\u2713" },
                { label: "Multi-provider", icon: "\u{1F517}" },
              ].map((badge) => (
                <span
                  key={badge.label}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    padding: "4px 12px",
                    borderRadius: 16,
                    backgroundColor: "var(--color-accent-dim)",
                    color: "var(--color-accent-hover)",
                    fontFamily: "var(--font-ui)",
                    fontSize: 11,
                    fontWeight: 500,
                    letterSpacing: "0.02em",
                  }}
                >
                  <span style={{ fontSize: 12 }}>{badge.icon}</span>
                  {badge.label}
                </span>
              ))}
            </div>

            <button
              className="animate-fade-in-up stagger-5"
              onClick={() => setStep("llm-provider")}
              style={{
                padding: "12px 32px",
                borderRadius: 8,
                border: "none",
                backgroundColor: "var(--color-accent)",
                color: "#ffffff",
                fontFamily: "var(--font-ui)",
                fontSize: 15,
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s ease",
                boxShadow: "0 2px 8px rgba(20, 184, 166, 0.2)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = "var(--color-accent-hover)";
                (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-1px)";
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 12px rgba(20, 184, 166, 0.3)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = "var(--color-accent)";
                (e.currentTarget as HTMLButtonElement).style.transform = "translateY(0)";
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 2px 8px rgba(20, 184, 166, 0.2)";
              }}
            >
              Get Started
            </button>
          </div>
        )}

        {/* -- Step: Connect LLM Provider -- */}
        {step === "llm-provider" && (
          <LLMProviderStep
            onComplete={async () => {
              await recheck();
              completeSetup();
              router.push("/workflows/new");
            }}
          />
        )}

      </div>
    </div>
  );
}
