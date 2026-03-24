"use client";

import Link from "next/link";

const SUGGESTIONS = [
  {
    icon: "\u{1F4CB}",
    title: "Start with a Template",
    description: "Pick from proven workflows and customize to your needs.",
    href: "/workflows/new?persona=operator",
    primary: true,
  },
  {
    icon: "\u{1F680}",
    title: "Describe Your Idea",
    description: "Tell Rooben what you want in plain English.",
    href: "/workflows/new",
    primary: false,
  },
  {
    icon: "\u{1F4E6}",
    title: "Browse Templates",
    description: "Explore workflow templates and agent configurations.",
    href: "/integrations?tab=templates",
    primary: false,
  },
];

export function EmptyWorkflows() {
  return (
    <div
      className="animate-fade-in-up"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "50vh",
        padding: "0 24px",
      }}
    >
      {/* Progress indicator */}
      <div
        className="animate-fade-in-up stagger-1"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 20,
          padding: "6px 14px",
          borderRadius: 16,
          backgroundColor: "var(--color-accent-dim)",
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: "var(--color-accent)",
          }}
        />
        <span
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 12,
            fontWeight: 500,
            color: "var(--color-accent-hover)",
          }}
        >
          Getting Started
        </span>
      </div>

      <h2
        className="animate-fade-in-up stagger-2"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 22,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          letterSpacing: "-0.01em",
          margin: "0 0 8px",
          textAlign: "center",
        }}
      >
        Ready to create your first workflow?
      </h2>
      <p
        className="animate-fade-in-up stagger-3"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 14,
          color: "var(--color-text-secondary)",
          margin: "0 0 32px",
          textAlign: "center",
          maxWidth: 420,
          lineHeight: 1.5,
        }}
      >
        Create more workflows to unlock analytics and workflow insights.
      </p>

      <div
        className="animate-fade-in-up stagger-4"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
          width: "100%",
          maxWidth: 640,
        }}
      >
        {SUGGESTIONS.map((s) => (
          <Link
            key={s.title}
            href={s.href}
            style={{
              display: "block",
              padding: "18px 16px",
              borderRadius: 10,
              border: s.primary
                ? "2px solid var(--color-accent)"
                : "1px solid var(--color-border)",
              backgroundColor: "var(--color-base)",
              textDecoration: "none",
              transition:
                "border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--color-accent)";
              e.currentTarget.style.boxShadow =
                "0 4px 12px rgba(13,148,136,0.12)";
              e.currentTarget.style.transform = "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = s.primary
                ? "var(--color-accent)"
                : "var(--color-border)";
              e.currentTarget.style.boxShadow = "none";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            <div style={{ fontSize: 20, marginBottom: 8 }}>{s.icon}</div>
            <div
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: 14,
                fontWeight: 600,
                color: s.primary
                  ? "var(--color-accent)"
                  : "var(--color-text-primary)",
                marginBottom: 4,
              }}
            >
              {s.title}
            </div>
            <div
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: 12,
                color: "var(--color-text-secondary)",
                lineHeight: 1.5,
              }}
            >
              {s.description}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
