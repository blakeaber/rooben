"use client";

import { useState } from "react";
import {
  IntegrationStatusBar,
  hasBlockingIntegrations,
  type IntegrationCheck,
} from "./IntegrationStatusBar";

interface SpecSection {
  label: string;
  key: string;
  items: string[];
  icon: string;
}

interface SpecReviewProps {
  specYaml: string;
  specSummary: {
    title: string;
    goal: string;
    deliverables: string[];
    agents: string[];
    acceptanceCriteria: string[];
    constraints: string[];
    inputSources?: string[];
  };
  integrationChecks?: IntegrationCheck[];
  onLaunch: () => void;
  onBack: () => void;
  isLaunching: boolean;
}

export function SpecReview({
  specYaml,
  specSummary,
  integrationChecks = [],
  onLaunch,
  onBack,
  isLaunching,
}: SpecReviewProps) {
  const [showYaml, setShowYaml] = useState(false);
  const hasBlockers = hasBlockingIntegrations(integrationChecks);
  const isLaunchDisabled = isLaunching || hasBlockers;

  const sections: SpecSection[] = [
    {
      label: "Deliverables",
      key: "deliverables",
      items: specSummary.deliverables,
      icon: "D",
    },
    {
      label: "Agents",
      key: "agents",
      items: specSummary.agents,
      icon: "A",
    },
    {
      label: "Acceptance Criteria",
      key: "criteria",
      items: specSummary.acceptanceCriteria,
      icon: "C",
    },
    {
      label: "Constraints",
      key: "constraints",
      items: specSummary.constraints,
      icon: "R",
    },
  ];

  return (
    <div
      style={{
        maxWidth: 680,
        margin: "0 auto",
        padding: "0 0 48px",
      }}
    >
      {/* Header */}
      <div className="animate-fade-in-up stagger-1" style={{ marginBottom: 32 }}>
        <h2
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 24,
            fontWeight: 700,
            color: "var(--color-text-primary)",
            letterSpacing: "-0.02em",
            margin: "0 0 8px",
          }}
        >
          {specSummary.title || "Your Specification"}
        </h2>
        <p
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            color: "var(--color-text-secondary)",
            margin: 0,
            lineHeight: 1.6,
          }}
        >
          {specSummary.goal}
        </p>
      </div>

      {/* Spec sections */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {sections
          .filter((s) => s.items.length > 0)
          .map((section, idx) => (
            <div
              key={section.key}
              className={`hud-card animate-fade-in-up stagger-${idx + 2}`}
              style={{ padding: 20 }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  marginBottom: 12,
                }}
              >
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 24,
                    height: 24,
                    borderRadius: 6,
                    backgroundColor: "var(--color-accent-dim)",
                    border: "1px solid rgba(13, 148, 136, 0.2)",
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--color-accent)",
                  }}
                >
                  {section.icon}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-ui)",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--color-text-primary)",
                    letterSpacing: "0.01em",
                  }}
                >
                  {section.label}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--color-text-muted)",
                    marginLeft: "auto",
                  }}
                >
                  {section.items.length}
                </span>
              </div>
              <ul
                style={{
                  margin: 0,
                  padding: "0 0 0 16px",
                  listStyleType: "none",
                }}
              >
                {section.items.map((item, i) => (
                  <li
                    key={i}
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: 13,
                      color: "var(--color-text-secondary)",
                      lineHeight: 1.6,
                      padding: "3px 0",
                      position: "relative",
                    }}
                  >
                    <span
                      style={{
                        position: "absolute",
                        left: -14,
                        top: 10,
                        width: 4,
                        height: 4,
                        borderRadius: "50%",
                        backgroundColor: "var(--color-accent)",
                        opacity: 0.5,
                      }}
                    />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </div>

      {/* Integration status (P17) */}
      {integrationChecks.length > 0 && (
        <div className="animate-fade-in-up stagger-5" style={{ marginTop: 16 }}>
          <IntegrationStatusBar checks={integrationChecks} />
        </div>
      )}

      {/* YAML toggle */}
      <div
        className="animate-fade-in-up stagger-5"
        style={{ marginTop: 20 }}
      >
        <button
          type="button"
          onClick={() => setShowYaml(!showYaml)}
          style={{
            background: "none",
            border: "none",
            color: "var(--color-accent)",
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
            padding: 0,
          }}
        >
          {showYaml ? "Hide" : "View"} raw YAML
        </button>

        {showYaml && (
          <pre
            className="animate-fade-in"
            style={{
              marginTop: 12,
              padding: 16,
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-base)",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--color-text-secondary)",
              lineHeight: 1.6,
              overflow: "auto",
              maxHeight: 400,
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
            }}
          >
            {specYaml}
          </pre>
        )}
      </div>

      {/* Actions */}
      <div
        className="animate-fade-in-up stagger-6"
        style={{
          marginTop: 32,
          display: "flex",
          gap: 12,
          justifyContent: "flex-end",
          alignItems: "center",
        }}
      >
        <button
          onClick={onBack}
          disabled={isLaunching}
          style={{
            padding: "10px 20px",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-base)",
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            fontWeight: 500,
            cursor: isLaunching ? "not-allowed" : "pointer",
            transition: "all 0.15s ease",
          }}
        >
          Back to Refinement
        </button>
        <button
          onClick={onLaunch}
          disabled={isLaunchDisabled}
          title={hasBlockers ? "Connect required integrations before launching" : undefined}
          style={{
            padding: "10px 28px",
            borderRadius: 8,
            border: "none",
            backgroundColor: isLaunchDisabled
              ? "var(--color-text-muted)"
              : "var(--color-accent)",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            fontWeight: 600,
            cursor: isLaunchDisabled ? "not-allowed" : "pointer",
            transition: "all 0.15s ease",
            boxShadow: isLaunchDisabled ? "none" : "var(--shadow-md)",
          }}
        >
          {isLaunching ? "Launching..." : hasBlockers ? "Connect Integrations to Launch" : "Launch Workflow"}
        </button>
      </div>
    </div>
  );
}
