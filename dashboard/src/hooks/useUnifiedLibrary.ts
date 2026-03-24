"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

export interface LibraryItem {
  name: string;
  type: "integration" | "template" | "agent";
  display_type: string;
  source: string;
  description: string;
  tags: string[];
  domain_tags: string[];
  category: string;
  use_cases: string[];
  installed: boolean;
  author: string;
  version: string;
  // Integration-specific
  cost_tier?: number;
  server_count?: number;
  servers?: Array<{
    name: string;
    transport_type: string;
    command: string;
    args: string[];
    env: Record<string, string>;
  }>;
  install_count?: number;
  // Template-specific
  prefill?: string;
  requires?: string[];
  // Agent-specific
  capabilities?: string[];
  integration?: string;
  model_override?: string;
}

export interface LibraryFilters {
  types: Array<{ value: string; label: string }>;
  domain_tags: string[];
  categories: string[];
}

export interface LibraryResponse {
  items: LibraryItem[];
  total: number;
  filters: LibraryFilters;
}

export function useUnifiedLibrary(params?: {
  type?: string;
  q?: string;
  domain_tag?: string;
  category?: string;
}) {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<LibraryFilters>({
    types: [],
    domain_tags: [],
    categories: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLibrary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const searchParams = new URLSearchParams();
      if (params?.type) searchParams.set("type", params.type);
      if (params?.q) searchParams.set("q", params.q);
      if (params?.domain_tag) searchParams.set("domain_tag", params.domain_tag);
      if (params?.category) searchParams.set("category", params.category);

      const qs = searchParams.toString();
      const url = `/api/hub/library${qs ? `?${qs}` : ""}`;
      const data = await apiFetch<LibraryResponse>(url);
      setItems(data.items || []);
      setTotal(data.total || 0);
      setFilters(
        data.filters || { types: [], domain_tags: [], categories: [] }
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to fetch library";
      console.error("[useUnifiedLibrary] fetch failed:", msg);
      setError(msg);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [params?.type, params?.q, params?.domain_tag, params?.category]);

  useEffect(() => {
    fetchLibrary();
  }, [fetchLibrary]);

  return { items, total, filters, loading, error, refetch: fetchLibrary };
}
