"use client";

import { useState, useEffect } from "react";
import { PersonaPicker } from "./PersonaPicker";

interface WelcomeFlowProps {
  onComplete: (persona: "operator" | "builder" | "optimizer") => void;
}

const STORAGE_KEY = "rooben_onboarding_complete";

export function WelcomeFlow({ onComplete }: WelcomeFlowProps) {
  const [step, setStep] = useState<"welcome" | "persona">("welcome");
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    const done = localStorage.getItem(STORAGE_KEY);
    setDismissed(done === "true");
  }, []);

  if (dismissed) return null;

  const handlePersonaSelect = (persona: "operator" | "builder" | "optimizer") => {
    localStorage.setItem(STORAGE_KEY, "true");
    localStorage.setItem("rooben_persona", persona);
    setDismissed(true);
    onComplete(persona);
  };

  return (
    <div
      className="animate-fade-in"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "70vh",
        padding: "40px 24px",
        textAlign: "center",
      }}
    >
      {step === "welcome" && (
        <>
          {/* Rooben mark */}
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
              boxShadow: "var(--glow-accent)",
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
              fontSize: 28,
              fontWeight: 700,
              color: "var(--color-text-primary)",
              letterSpacing: "-0.02em",
              margin: "0 0 12px",
            }}
          >
            Welcome to Rooben
          </h1>
          <p
            className="animate-fade-in-up stagger-3"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 15,
              color: "var(--color-text-secondary)",
              maxWidth: 420,
              lineHeight: 1.6,
              margin: "0 0 32px",
            }}
          >
            Rooben turns your ideas into verified, multi-agent work product.
            Describe what you need, watch AI teams execute, and trust every
            result.
          </p>
          <button
            type="button"
            className="animate-fade-in-up stagger-4"
            onClick={() => setStep("persona")}
            style={{
              padding: "12px 28px",
              borderRadius: 8,
              border: "none",
              background: "var(--color-accent)",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: 15,
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "var(--color-accent-hover)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "var(--color-accent)";
            }}
          >
            Get started
          </button>
        </>
      )}

      {step === "persona" && (
        <>
          <h2
            className="animate-fade-in-up stagger-1"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 22,
              fontWeight: 700,
              color: "var(--color-text-primary)",
              letterSpacing: "-0.01em",
              margin: "0 0 8px",
            }}
          >
            What brings you here?
          </h2>
          <p
            className="animate-fade-in-up stagger-2"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 14,
              color: "var(--color-text-secondary)",
              margin: "0 0 32px",
            }}
          >
            This helps us show you the most relevant templates and features.
          </p>
          <div className="animate-fade-in-up stagger-3">
            <PersonaPicker onSelect={handlePersonaSelect} />
          </div>
        </>
      )}
    </div>
  );
}
