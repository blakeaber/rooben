"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type {
  Integration,
  IntegrationTestResult,
  LibraryIntegration,
} from "@/lib/types";

export function useIntegrations() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await apiFetch<{ integrations: Integration[] }>(
        "/api/integrations"
      );
      setIntegrations(data.integrations);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { integrations, loading, error, refetch };
}

export function useIntegrationDetail(name: string) {
  const [integration, setIntegration] = useState<Integration | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await apiFetch<Integration>(
        `/api/integrations/${encodeURIComponent(name)}`
      );
      setIntegration(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, [name]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { integration, loading, error, refetch };
}

export function useLibrary() {
  const [library, setLibrary] = useState<LibraryIntegration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ library: LibraryIntegration[] }>("/api/integrations/library")
      .then((data) => {
        setLibrary(data.library);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to fetch");
      })
      .finally(() => setLoading(false));
  }, []);

  return { library, loading, error };
}

export async function testIntegration(
  name: string
): Promise<IntegrationTestResult> {
  return apiFetch<IntegrationTestResult>(
    `/api/integrations/${encodeURIComponent(name)}/test`,
    { method: "POST" }
  );
}
