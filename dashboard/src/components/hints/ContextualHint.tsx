"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

export interface HintData {
  id: string;
  message: string;
  ctaLabel?: string;
  ctaHref?: string;
  tier?: "pro" | "team" | "enterprise";
}

interface ContextualHintProps {
  hint: HintData;
}

const TIER_LABELS: Record<string, { label: string; color: string }> = {
  pro: { label: "Pro — $29/mo", color: "#0d9488" },
  team: { label: "Team — $99/mo", color: "#2563eb" },
  enterprise: { label: "Enterprise", color: "#7c3aed" },
};

export function ContextualHint({ hint }: ContextualHintProps) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(`hint_dismissed_${hint.id}`) === "true") {
      setDismissed(true);
    }
  }, [hint.id]);

  if (dismissed) return null;

  const handleDismiss = () => {
    localStorage.setItem(`hint_dismissed_${hint.id}`, "true");
    setDismissed(true);
  };

  const tierInfo = hint.tier ? TIER_LABELS[hint.tier] : null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 14px",
        borderRadius: 8,
        border: "1px solid var(--color-border)",
        backgroundColor: "var(--color-base)",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            color: "var(--color-text-secondary)",
            margin: 0,
            lineHeight: 1.4,
          }}
        >
          {hint.message}
        </p>
        {tierInfo && (
          <span
            style={{
              display: "inline-block",
              marginTop: 4,
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              fontWeight: 600,
              color: tierInfo.color,
              letterSpacing: "0.04em",
            }}
          >
            {tierInfo.label}
          </span>
        )}
      </div>
      {hint.ctaLabel && hint.ctaHref && (
        hint.ctaHref.startsWith("http") ? (
          <a
            href={hint.ctaHref}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              flexShrink: 0,
              padding: "5px 12px",
              borderRadius: 5,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface-1)",
              color: "var(--color-accent)",
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none",
              whiteSpace: "nowrap",
            }}
          >
            {hint.ctaLabel}
          </a>
        ) : (
          <Link
            href={hint.ctaHref}
            style={{
              flexShrink: 0,
              padding: "5px 12px",
              borderRadius: 5,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface-1)",
              color: "var(--color-accent)",
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none",
              whiteSpace: "nowrap",
            }}
          >
            {hint.ctaLabel}
          </Link>
        )
      )}
      <button
        onClick={handleDismiss}
        aria-label="Dismiss hint"
        style={{
          flexShrink: 0,
          background: "none",
          border: "none",
          fontFamily: "var(--font-mono)",
          fontSize: 14,
          color: "var(--color-text-muted)",
          cursor: "pointer",
          padding: "2px 4px",
          lineHeight: 1,
        }}
      >
        &times;
      </button>
    </div>
  );
}
