"use client";

import Link from "next/link";

const WELCOME_DISMISSED_KEY = "rooben_welcome_dismissed";

interface PersonaPath {
  title: string;
  description: string;
  icon: string;
  href: string;
  accent: string;
}

const PATHS: PersonaPath[] = [
  {
    title: "Produce a Deliverable",
    icon: "\u{1F4CB}",
    description:
      "Reports, analyses, briefings — describe what you need, get a verified first draft.",
    href: "/workflows/new?persona=operator",
    accent: "var(--color-accent)",
  },
  {
    title: "Build Something",
    icon: "\u{1F6E0}",
    description:
      "APIs, pipelines, dashboards — multi-agent construction with tests that pass.",
    href: "/workflows/new?persona=builder",
    accent: "var(--color-indigo)",
  },
  {
    title: "Browse Templates",
    icon: "\u{1F4E6}",
    description: "Start from a proven workflow template.",
    href: "/integrations?tab=templates",
    accent: "var(--color-amber)",
  },
];

const TRUST_BADGES = [
  { label: "Budget-enforced", icon: "\u{1F6E1}" },
  { label: "Verified outputs", icon: "\u2713" },
  { label: "Multi-provider", icon: "\u{1F517}" },
];

interface WelcomeHeroProps {
  onDismiss?: () => void;
}

export function WelcomeHero({ onDismiss }: WelcomeHeroProps) {
  const handleDismiss = () => {
    localStorage.setItem(WELCOME_DISMISSED_KEY, "true");
    onDismiss?.();
  };

  return (
    <div
      className="animate-fade-in-up"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "70vh",
        padding: "0 24px",
      }}
    >
      {/* Rooben brand mark */}
      <div
        className="animate-fade-in-up stagger-1"
        style={{
          width: 56,
          height: 56,
          borderRadius: 14,
          background: "var(--gradient-rooben)",
          backgroundSize: "200% 200%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 24,
          boxShadow: "0 4px 16px rgba(20, 184, 166, 0.15)",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 24,
            fontWeight: 700,
            color: "#ffffff",
          }}
        >
          R
        </span>
      </div>

      <h1
        className="animate-fade-in-up stagger-2"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 32,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          letterSpacing: "-0.02em",
          margin: "0 0 12px",
          textAlign: "center",
        }}
      >
        Welcome to Rooben
      </h1>
      <p
        className="animate-fade-in-up stagger-3"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 16,
          color: "var(--color-text-secondary)",
          margin: "0 0 6px",
          textAlign: "center",
          maxWidth: 460,
          lineHeight: 1.6,
        }}
      >
        Describe the end result you want. AI agents plan, execute, verify, and
        deliver it.
      </p>
      <p
        className="animate-fade-in-up stagger-4"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 13,
          color: "var(--color-text-muted)",
          margin: "0 0 20px",
          textAlign: "center",
        }}
      >
        Every output is verified. You always know what it costs.
      </p>

      {/* Trust badges */}
      <div
        className="animate-fade-in-up stagger-4"
        style={{
          display: "flex",
          gap: 10,
          marginBottom: 36,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {TRUST_BADGES.map((badge) => (
          <span
            key={badge.label}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "4px 12px",
              borderRadius: 16,
              backgroundColor: "var(--color-accent-dim)",
              color: "var(--color-accent-hover)",
              fontFamily: "var(--font-ui)",
              fontSize: 11,
              fontWeight: 500,
              letterSpacing: "0.02em",
            }}
          >
            <span style={{ fontSize: 12 }}>{badge.icon}</span>
            {badge.label}
          </span>
        ))}
      </div>

      {/* Persona cards */}
      <div
        className="animate-fade-in-up stagger-5"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 14,
          width: "100%",
          maxWidth: 680,
        }}
      >
        {PATHS.map((path) => (
          <Link
            key={path.title}
            href={path.href}
            style={{
              display: "block",
              padding: "22px 20px",
              borderRadius: 12,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-base)",
              textDecoration: "none",
              transition:
                "border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--color-accent)";
              e.currentTarget.style.boxShadow =
                "0 4px 12px rgba(13,148,136,0.12)";
              e.currentTarget.style.transform = "translateY(-2px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--color-border)";
              e.currentTarget.style.boxShadow = "none";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            <div
              style={{
                fontSize: 22,
                marginBottom: 10,
              }}
            >
              {path.icon}
            </div>
            <div
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: 15,
                fontWeight: 600,
                color: "var(--color-text-primary)",
                marginBottom: 6,
              }}
            >
              {path.title}
            </div>
            <div
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: 12,
                color: "var(--color-text-secondary)",
                lineHeight: 1.5,
              }}
            >
              {path.description}
            </div>
          </Link>
        ))}
      </div>

      {/* Tier callout */}
      <p
        className="animate-fade-in-up stagger-6"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 12,
          color: "var(--color-text-muted)",
          marginTop: 28,
          textAlign: "center",
        }}
      >
        Free forever with your own API key. No workflow cap.
      </p>

      {/* Dismiss link */}
      <button
        onClick={handleDismiss}
        className="animate-fade-in-up stagger-6"
        style={{
          background: "none",
          border: "none",
          fontFamily: "var(--font-ui)",
          fontSize: 12,
          color: "var(--color-text-muted)",
          cursor: "pointer",
          marginTop: 8,
          textDecoration: "underline",
          textUnderlineOffset: 2,
        }}
      >
        explore on my own
      </button>
    </div>
  );
}
