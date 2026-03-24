"use client";

import { Suspense, useState, useMemo, useEffect, useRef } from "react";
import Link from "next/link";
import { useUnifiedLibrary, type LibraryItem } from "@/hooks/useUnifiedLibrary";
import { apiFetch } from "@/lib/api";

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

// ── Type badge ────────────────────────────────────────────────────────────

function TypeBadge({ type, displayType }: { type: string; displayType: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    integration: { bg: "rgba(59, 130, 246, 0.1)", text: "#2563eb" },
    template: { bg: "rgba(22, 163, 74, 0.1)", text: "#16a34a" },
    agent: { bg: "rgba(217, 119, 6, 0.1)", text: "#d97706" },
  };
  const c = colors[type] || { bg: "var(--color-surface-3)", text: "var(--color-text-secondary)" };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "9999px",
        fontSize: "10px",
        fontFamily: "var(--font-mono)",
        fontWeight: 600,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        backgroundColor: c.bg,
        color: c.text,
      }}
    >
      {displayType}
    </span>
  );
}

// ── Source badge ───────────────────────────────────────────────────────────

function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    builtin: { bg: "rgba(22, 163, 74, 0.1)", text: "#16a34a" },
    user: { bg: "rgba(59, 130, 246, 0.1)", text: "#2563eb" },
    community: { bg: "rgba(217, 119, 6, 0.1)", text: "#d97706" },
  };
  const c = colors[source] || colors.builtin;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "9999px",
        fontSize: "10px",
        fontFamily: "var(--font-mono)",
        fontWeight: 600,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        backgroundColor: c.bg,
        color: c.text,
      }}
    >
      {source}
    </span>
  );
}

// ── Install modal ─────────────────────────────────────────────────────────

function InstallModal({
  item,
  onClose,
  onInstalled,
}: {
  item: LibraryItem;
  onClose: () => void;
  onInstalled: () => void;
}) {
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const envVars = new Set<string>();
  for (const server of item.servers || []) {
    if (server.env) {
      for (const val of Object.values(server.env)) {
        const match = val.match(/\$\{(\w+)\}/);
        if (match) envVars.add(match[1]);
      }
    }
    if (server.args) {
      for (const arg of server.args) {
        const match = arg.match(/\$\{(\w+)\}/);
        if (match) envVars.add(match[1]);
      }
    }
  }

  const handleInstall = async () => {
    setInstalling(true);
    setError(null);
    try {
      if (item.type === "integration" && item.source === "community") {
        await apiFetch("/api/integrations/install", {
          method: "POST",
          body: JSON.stringify({
            name: item.name,
            description: item.description,
            domain_tags: item.domain_tags,
            cost_tier: item.cost_tier,
            author: item.author,
            version: item.version,
            servers: item.servers || [],
          }),
        });
      } else {
        await apiFetch("/api/extensions/install", {
          method: "POST",
          body: JSON.stringify({ name: item.name }),
        });
      }
      onInstalled();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Install failed");
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.3)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: "var(--color-base)",
          borderRadius: "10px",
          padding: "28px",
          maxWidth: "460px",
          width: "90%",
          boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "16px",
            fontWeight: 700,
            color: "var(--color-text-primary)",
            margin: "0 0 8px 0",
          }}
        >
          Install {item.name}
        </h2>
        <p
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            color: "var(--color-text-secondary)",
            margin: "0 0 20px 0",
          }}
        >
          {item.description}
        </p>

        {envVars.size > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "10px",
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "var(--color-text-muted)",
                marginBottom: "8px",
              }}
            >
              Required Environment Variables
            </div>
            <div
              style={{
                backgroundColor: "var(--color-surface-2)",
                borderRadius: "4px",
                padding: "10px",
              }}
            >
              {Array.from(envVars).map((v) => (
                <div
                  key={v}
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "12px",
                    color: "var(--color-text-primary)",
                    padding: "2px 0",
                  }}
                >
                  {v}
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div
            style={{ fontFamily: "var(--font-ui)", fontSize: "12px", color: "#dc2626", marginBottom: "12px" }}
          >
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
          <button
            onClick={onClose}
            style={{
              padding: "8px 16px",
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
          <button
            onClick={handleInstall}
            disabled={installing}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#0d9488",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: installing ? "wait" : "pointer",
              opacity: installing ? 0.6 : 1,
            }}
          >
            {installing ? "Installing..." : "Install"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Stat chip ─────────────────────────────────────────────────────────────

function StatChip({ label, value, color = "#0d9488" }: { label: string; value: string; color?: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        padding: "12px 16px",
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: "6px",
        minWidth: "100px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "9px",
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
        }}
      >
        {label}
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "20px", fontWeight: 700, color, lineHeight: 1 }}>
        {value}
      </div>
    </div>
  );
}

// ── Unified card ──────────────────────────────────────────────────────────

function LibraryCard({
  item,
  onInstall,
}: {
  item: LibraryItem;
  onInstall: (item: LibraryItem) => void;
}) {
  return (
    <Link
      href={`/integrations/${encodeURIComponent(item.name)}`}
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: "8px",
        padding: "20px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        transition: "box-shadow 0.15s ease, border-color 0.15s ease",
        textDecoration: "none",
        color: "inherit",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "#0d9488";
        e.currentTarget.style.boxShadow = "0 2px 8px rgba(13,148,136,0.12)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--color-border)";
        e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.08)";
      }}
    >
      {/* Header: name + type badge */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h3
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "14px",
            fontWeight: 600,
            color: "var(--color-text-primary)",
            margin: 0,
          }}
        >
          {item.type === "template"
            ? item.name.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
            : item.name}
        </h3>
        <TypeBadge type={item.type} displayType={item.display_type} />
      </div>

      {/* Author + source */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {item.author && (
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--color-text-muted)" }}>
            by {item.author}
          </span>
        )}
        <SourceBadge source={item.source} />
      </div>

      {/* Description */}
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: "12px",
          color: "var(--color-text-secondary)",
          margin: 0,
          lineHeight: 1.5,
          flex: 1,
        }}
      >
        {item.description}
      </p>

      {/* Tags */}
      {item.domain_tags.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
          {item.domain_tags.map((tag) => (
            <span
              key={tag}
              style={{
                display: "inline-block",
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "10px",
                fontFamily: "var(--font-mono)",
                backgroundColor: "var(--color-surface-3)",
                color: "var(--color-text-secondary)",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Agent capabilities */}
      {item.type === "agent" && item.capabilities && item.capabilities.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
          {item.capabilities.map((cap) => (
            <span
              key={cap}
              style={{
                display: "inline-block",
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "10px",
                fontFamily: "var(--font-mono)",
                backgroundColor: "rgba(217, 119, 6, 0.1)",
                color: "#d97706",
              }}
            >
              {cap}
            </span>
          ))}
        </div>
      )}

      {/* Footer: type-specific meta + action */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderTop: "1px solid var(--color-surface-3)",
          paddingTop: "10px",
        }}
      >
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--color-text-muted)" }}>
          {item.type === "integration" && (item.cost_tier !== undefined
            ? ["Free", "$", "$$", "$$$"][item.cost_tier] || ""
            : "")}
          {item.type === "template" && item.category && (
            <span style={{ textTransform: "capitalize" }}>{item.category}</span>
          )}
          {item.type === "agent" && "Agent preset"}
        </span>

        {item.type === "template" ? (
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              window.location.href = `/workflows/new?template=${encodeURIComponent(item.name)}`;
            }}
            style={{
              padding: "4px 12px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#0d9488",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: "11px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Use Template
          </button>
        ) : item.installed ? (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "10px",
              fontWeight: 600,
              color: "#16a34a",
            }}
          >
            Installed
          </span>
        ) : (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onInstall(item); }}
            style={{
              padding: "4px 12px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#0d9488",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: "11px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Install
          </button>
        )}
      </div>
    </Link>
  );
}

// ── Page inner ────────────────────────────────────────────────────────────

const TYPE_OPTIONS = [
  { value: "", label: "All" },
  { value: "integration", label: "Data Sources" },
  { value: "template", label: "Templates" },
  { value: "agent", label: "Agents" },
];

function IntegrationsPageInner() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [installing, setInstalling] = useState<LibraryItem | null>(null);
  const debouncedSearch = useDebouncedValue(search, 250);

  const { items, total, filters, loading, refetch } = useUnifiedLibrary({
    type: typeFilter || undefined,
    q: debouncedSearch || undefined,
    domain_tag: tagFilter || undefined,
  });

  // Sticky stats: keep showing previous counts while loading
  const stats = useMemo(() => {
    const ds = items.filter((i) => i.type === "integration").length;
    const tmpl = items.filter((i) => i.type === "template").length;
    const ag = items.filter((i) => i.type === "agent").length;
    return { dataSources: ds, templates: tmpl, agents: ag, total: items.length };
  }, [items]);
  const lastStats = useRef(stats);
  if (!loading) lastStats.current = stats;
  const displayStats = loading ? lastStats.current : stats;
  const hasLoaded = useRef(false);
  if (!loading && items.length > 0) hasLoaded.current = true;

  return (
    <div className="animate-fade-in-up" style={{ maxWidth: "1280px" }}>
      {/* Page header */}
      <div style={{ marginBottom: "20px" }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "10px",
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
            marginBottom: "6px",
          }}
        >
          ROOBEN / INTEGRATIONS
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h1
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: "22px",
                fontWeight: 700,
                color: "var(--color-text-primary)",
                margin: 0,
                letterSpacing: "-0.01em",
              }}
            >
              Integrations Hub
            </h1>
            <p
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: "13px",
                color: "var(--color-text-secondary)",
                marginTop: "4px",
              }}
            >
              Browse and manage data sources, templates, and agents.
            </p>
          </div>
          <Link
            href="/integrations/create"
            data-testid="hub-create-custom"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 18px",
              borderRadius: "6px",
              backgroundColor: "#0d9488",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: "13px",
              fontWeight: 600,
              textDecoration: "none",
              transition: "opacity 0.15s ease",
              whiteSpace: "nowrap",
            }}
          >
            + Create Custom
          </Link>
        </div>
      </div>

      {/* Stat chips */}
      {hasLoaded.current && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "10px",
            marginBottom: "20px",
            opacity: loading ? 0.5 : 1,
            transition: "opacity 0.15s ease",
          }}
        >
          <StatChip label="Total" value={displayStats.total.toString()} color="#0d9488" />
          <StatChip label="Data Sources" value={displayStats.dataSources.toString()} color="#2563eb" />
          <StatChip label="Templates" value={displayStats.templates.toString()} color="#16a34a" />
          <StatChip label="Agents" value={displayStats.agents.toString()} color="#d97706" />
        </div>
      )}

      {/* Type filter toggles */}
      <div style={{ display: "flex", gap: "6px", marginBottom: "16px" }}>
        {TYPE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setTypeFilter(opt.value)}
            data-testid={`type-filter-${opt.value || "all"}`}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: typeFilter === opt.value ? "1px solid #0d9488" : "1px solid var(--color-border)",
              backgroundColor: typeFilter === opt.value ? "rgba(13, 148, 136, 0.08)" : "var(--color-base)",
              color: typeFilter === opt.value ? "#0d9488" : "var(--color-text-secondary)",
              fontFamily: "var(--font-ui)",
              fontSize: "12px",
              fontWeight: typeFilter === opt.value ? 600 : 400,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Search + Domain filter */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "24px", flexWrap: "wrap" }}>
        <input
          type="text"
          placeholder="Search extensions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: "1 1 200px",
            padding: "8px 12px",
            border: "1px solid var(--color-border)",
            borderRadius: "6px",
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            outline: "none",
          }}
        />
        <select
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          style={{
            padding: "8px 12px",
            border: "1px solid var(--color-border)",
            borderRadius: "6px",
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            backgroundColor: "var(--color-base)",
            color: "var(--color-text-primary)",
          }}
        >
          <option value="">All domains</option>
          {(filters.domain_tags || []).map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        </select>
      </div>

      {/* Loading */}
      {loading && (
        <div
          style={{
            padding: "60px",
            textAlign: "center",
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: "var(--color-text-muted)",
            animation: "live-pulse 2s ease-in-out infinite",
          }}
        >
          Loading extensions...
        </div>
      )}

      {/* Card grid */}
      {!loading && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: "16px",
          }}
        >
          {items.map((item) => (
            <LibraryCard
              key={`${item.type}-${item.name}`}
              item={item}
              onInstall={setInstalling}
            />
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && items.length === 0 && (
        <div
          style={{
            padding: "40px",
            textAlign: "center",
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            color: "var(--color-text-muted)",
          }}
        >
          No matching extensions found.
        </div>
      )}

      {/* Install modal */}
      {installing && (
        <InstallModal
          item={installing}
          onClose={() => setInstalling(null)}
          onInstalled={() => {
            setInstalling(null);
            refetch();
          }}
        />
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            padding: "60px",
            textAlign: "center",
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: "var(--color-text-muted)",
          }}
        >
          Loading...
        </div>
      }
    >
      <IntegrationsPageInner />
    </Suspense>
  );
}
