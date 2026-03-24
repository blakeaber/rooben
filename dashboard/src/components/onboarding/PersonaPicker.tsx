"use client";

interface PersonaPickerProps {
  onSelect: (persona: "operator" | "builder" | "optimizer") => void;
}

const PERSONAS = [
  {
    key: "operator" as const,
    title: "The Operator",
    description: "I run the business, not the busywork.",
    color: "#14b8a6",
    quote: "Board deck in 4 minutes.",
  },
  {
    key: "builder" as const,
    title: "The Builder",
    description: "I have taste but no time.",
    color: "#818cf8",
    quote: "API + Tests + Docker in 8 minutes.",
  },
  {
    key: "optimizer" as const,
    title: "The Optimizer",
    description: "I know what good looks like.",
    color: "#fbbf24",
    quote: "5 hours back every week.",
  },
];

export function PersonaPicker({ onSelect }: PersonaPickerProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        gap: 16,
        maxWidth: 780,
        margin: "0 auto",
      }}
    >
      {PERSONAS.map((persona) => (
        <button
          key={persona.key}
          type="button"
          onClick={() => onSelect(persona.key)}
          style={{
            padding: 24,
            borderRadius: 12,
            border: "1px solid var(--color-border)",
            background: "var(--color-surface-1)",
            textAlign: "left",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = persona.color;
            (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 16px ${persona.color}20`;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-border)";
            (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: persona.color,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            {persona.title}
          </span>
          <p
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 14,
              color: "var(--color-text-primary)",
              margin: "8px 0 12px",
              lineHeight: 1.5,
            }}
          >
            {persona.description}
          </p>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--color-text-muted)",
              fontStyle: "italic",
            }}
          >
            &ldquo;{persona.quote}&rdquo;
          </span>
        </button>
      ))}
    </div>
  );
}
