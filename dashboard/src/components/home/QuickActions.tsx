"use client";

import Link from "next/link";
import type { LifecycleStage } from "@/hooks/useUserLifecycle";

interface QuickActionsProps {
  stage: LifecycleStage;
}

interface ActionItem {
  label: string;
  href: string;
  primary?: boolean;
}

export function QuickActions({ stage }: QuickActionsProps) {
  const actions: ActionItem[] = [
    { label: "New Workflow", href: "/workflows/new", primary: true },
    { label: "Browse Templates", href: "/integrations?tab=templates" },
  ];

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {actions.map((action) => (
        <Link
          key={action.href}
          href={action.href}
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "7px 16px",
            borderRadius: 6,
            border: action.primary
              ? "none"
              : "1px solid var(--color-border)",
            backgroundColor: action.primary
              ? "var(--color-accent)"
              : "var(--color-base)",
            color: action.primary ? "#ffffff" : "var(--color-text-secondary)",
            fontFamily: "var(--font-ui)",
            fontSize: 12,
            fontWeight: 600,
            textDecoration: "none",
            transition: "opacity 0.15s ease",
          }}
        >
          {action.label}
        </Link>
      ))}
    </div>
  );
}
