"use client";

import { Header } from "@/components/layout/Header";
import { LLMProviderCredentials } from "@/components/settings/LLMProviderCredentials";
import { ProviderSettings, PROVIDER_MODELS } from "@/components/create/ProviderSettings";
import { IntegrationCredentials } from "@/components/settings/IntegrationCredentials";
import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

export default function SettingsPage() {
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("claude-sonnet-4-20250514");

  // Load user preferences
  useEffect(() => {
    apiFetch<{ preferences: Record<string, string> }>("/api/me/preferences")
      .then((res) => {
        if (res.preferences?.default_provider) setProvider(res.preferences.default_provider);
        if (res.preferences?.default_model) setModel(res.preferences.default_model);
      })
      .catch(() => {});
  }, []);

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    const models = PROVIDER_MODELS[newProvider];
    if (models?.length) setModel(models[0].value);
    apiFetch("/api/me/preferences", {
      method: "POST",
      body: JSON.stringify({ default_provider: newProvider, default_model: models?.[0]?.value || "" }),
    }).catch(() => {});
  };

  const handleModelChange = (newModel: string) => {
    setModel(newModel);
    apiFetch("/api/me/preferences", {
      method: "POST",
      body: JSON.stringify({ default_provider: provider, default_model: newModel }),
    }).catch(() => {});
  };

  return (
    <div style={{ backgroundColor: "var(--color-surface-1)", minHeight: "100vh", padding: "0 0 48px" }}>
      <Header title="Settings" breadcrumbs={[{ label: "Settings" }]} />

      <div style={{ maxWidth: 480 }}>
        {/* LLM Provider credentials + model selection */}
        <LLMProviderCredentials />
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            padding: 20,
            marginTop: 16,
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
            Default Provider & Model
          </h3>
          <p
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              color: "var(--color-text-secondary)",
              margin: "0 0 12px",
            }}
          >
            Default provider and model used when creating new workflows.
          </p>
          <ProviderSettings
            provider={provider}
            model={model}
            onProviderChange={handleProviderChange}
            onModelChange={handleModelChange}
            alwaysExpanded
          />
        </div>

        {/* Data Source credentials */}
        <IntegrationCredentials />
      </div>
    </div>
  );
}
