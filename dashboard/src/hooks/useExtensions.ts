"use client";

import { useState, useEffect, useCallback } from "react";

export interface Extension {
  name: string;
  type: "integration" | "template" | "agent";
  version: string;
  author: string;
  description: string;
  tags: string[];
  domain_tags: string[];
  category: string;
  use_cases: string[];
  installed: boolean;
  // Integration-specific
  cost_tier?: number;
  required_env?: { name: string; description: string; link: string }[];
  // Template-specific
  prefill?: string;
  requires?: string[];
  // Agent-specific
  capabilities?: string[];
  integration?: string;
  model_override?: string;
  prompt_template?: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420";

export function useExtensions(type?: string) {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchExtensions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = type
        ? `${API}/api/extensions?type=${type}`
        : `${API}/api/extensions`;
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error(`Failed to fetch extensions: ${res.status}`);
      const data = await res.json();
      setExtensions(data.extensions || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setExtensions([]);
    } finally {
      setLoading(false);
    }
  }, [type]);

  useEffect(() => {
    fetchExtensions();
  }, [fetchExtensions]);

  const install = useCallback(
    async (name: string) => {
      try {
        const res = await fetch(`${API}/api/extensions/install`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ name }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `Install failed: ${res.status}`);
        }
        await fetchExtensions(); // Refresh
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Install failed");
        return false;
      }
    },
    [fetchExtensions]
  );

  const uninstall = useCallback(
    async (name: string) => {
      try {
        const res = await fetch(`${API}/api/extensions/uninstall`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ name }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `Uninstall failed: ${res.status}`);
        }
        await fetchExtensions(); // Refresh
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Uninstall failed");
        return false;
      }
    },
    [fetchExtensions]
  );

  return { extensions, loading, error, refetch: fetchExtensions, install, uninstall };
}

export function useExtensionTemplates() {
  return useExtensions("template");
}

export function useExtensionAgents() {
  return useExtensions("agent");
}
