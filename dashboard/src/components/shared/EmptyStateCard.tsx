"use client";

import Link from "next/link";

interface EmptyStateCardProps {
  icon?: string;
  title: string;
  description: string;
  ctaLabel?: string;
  ctaHref?: string;
}

export function EmptyStateCard({
  icon,
  title,
  description,
  ctaLabel,
  ctaHref,
}: EmptyStateCardProps) {
  return (
    <div
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px dashed var(--color-border-muted)",
        borderRadius: 10,
        padding: "40px 32px",
        textAlign: "center",
        maxWidth: 480,
        marginInline: "auto",
      }}
    >
      {icon && (
        <div
          style={{
            fontSize: 28,
            marginBottom: 12,
            color: "var(--color-text-muted)",
          }}
        >
          {icon}
        </div>
      )}
      <h3
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 16,
          fontWeight: 600,
          color: "var(--color-text-primary)",
          margin: "0 0 6px",
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 13,
          color: "var(--color-text-secondary)",
          lineHeight: 1.5,
          margin: "0 0 16px",
        }}
      >
        {description}
      </p>
      {ctaLabel && ctaHref && (
        <Link
          href={ctaHref}
          style={{
            display: "inline-block",
            padding: "8px 20px",
            borderRadius: 6,
            backgroundColor: "var(--color-accent)",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            fontWeight: 600,
            textDecoration: "none",
            transition: "opacity 0.15s ease",
          }}
        >
          {ctaLabel}
        </Link>
      )}
    </div>
  );
}
