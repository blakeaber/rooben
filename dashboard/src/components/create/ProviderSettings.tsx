"use client";

import { useState } from "react";

export const PROVIDER_MODELS: Record<
  string,
  { label: string; value: string }[]
> = {
  anthropic: [
    { label: "Claude Sonnet 4", value: "claude-sonnet-4-20250514" },
    { label: "Claude Haiku 3.5", value: "claude-3-5-haiku-20241022" },
  ],
  openai: [
    { label: "GPT-4o", value: "gpt-4o" },
    { label: "GPT-4o Mini", value: "gpt-4o-mini" },
  ],
  ollama: [{ label: "Llama 3.1", value: "llama3.1" }],
  bedrock: [
    {
      label: "Claude Sonnet 4",
      value: "anthropic.claude-sonnet-4-20250514-v1:0",
    },
  ],
};

interface ProviderSettingsProps {
  provider: string;
  model: string;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
  alwaysExpanded?: boolean;
}

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 6,
  color: "var(--color-text-secondary)",
  fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
};

const selectStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  borderRadius: 6,
  border: "1px solid var(--color-border)",
  backgroundColor: "var(--color-base)",
  fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
  fontSize: 14,
  color: "var(--color-text-primary)",
  outline: "none",
};

export function ProviderSettings({
  provider,
  model,
  onProviderChange,
  onModelChange,
  alwaysExpanded,
}: ProviderSettingsProps) {
  const [expanded, setExpanded] = useState(alwaysExpanded ?? false);
  const showToggle = !alwaysExpanded;

  return (
    <div
      className="animate-fade-in-up stagger-5"
      style={{
        maxWidth: 560,
        margin: "16px auto 0",
        textAlign: "center",
      }}
    >
      {showToggle && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          aria-label="Toggle provider settings"
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--color-text-muted)",
            letterSpacing: "0.04em",
            padding: "4px 8px",
            transition: "color 0.15s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color =
              "var(--color-text-secondary)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color =
              "var(--color-text-muted)";
          }}
        >
          {expanded ? "Hide" : "Model & provider settings"}
        </button>
      )}

      {expanded && (
        <div
          className="animate-slide-down"
          style={{
            marginTop: 12,
            display: "flex",
            gap: 12,
          }}
        >
          <div style={{ flex: 1 }}>
            <label htmlFor="wiz-provider" style={labelStyle}>
              Provider
            </label>
            <select
              id="wiz-provider"
              value={provider}
              onChange={(e) => onProviderChange(e.target.value)}
              style={selectStyle}
            >
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama</option>
              <option value="bedrock">Bedrock</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label htmlFor="wiz-model" style={labelStyle}>
              Model
            </label>
            <select
              id="wiz-model"
              value={model}
              onChange={(e) => onModelChange(e.target.value)}
              style={selectStyle}
            >
              {(PROVIDER_MODELS[provider] || []).map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {!expanded && showToggle && (
        <p
          style={{
            margin: "4px 0 0",
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--color-text-muted)",
            letterSpacing: "0.02em",
          }}
        >
          Defaults to Claude Sonnet 4 on Anthropic
        </p>
      )}
    </div>
  );
}
