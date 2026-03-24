"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface ExecutionStatusProps {
  workflowId: string | null;
  status: "launching" | "running" | "completed" | "failed";
  error?: string | null;
}

const STEPS = [
  { key: "generating", label: "Generating specification..." },
  { key: "planning", label: "Planning workflow..." },
  { key: "launching", label: "Launching agents..." },
];

export function ExecutionStatus({
  workflowId,
  status,
  error,
}: ExecutionStatusProps) {
  const router = useRouter();
  const [elapsed, setElapsed] = useState(0);
  const [activeStep, setActiveStep] = useState(0);

  // Tick elapsed time
  useEffect(() => {
    if (status !== "launching" && status !== "running") return;
    const interval = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(interval);
  }, [status]);

  // Animate through steps while launching
  useEffect(() => {
    if (status !== "launching") return;
    const timers = [
      setTimeout(() => setActiveStep(1), 3000),
      setTimeout(() => setActiveStep(2), 7000),
    ];
    return () => timers.forEach(clearTimeout);
  }, [status]);

  // Auto-redirect to workflow page once we have an ID and it's running
  useEffect(() => {
    if (workflowId && status === "running") {
      const timer = setTimeout(() => {
        router.push(`/workflows/${workflowId}`);
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [workflowId, status, router]);

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
      {/* Status icon */}
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 24,
          backgroundColor:
            status === "failed"
              ? "var(--color-rose-dim)"
              : status === "completed"
                ? "var(--color-emerald-dim)"
                : "var(--color-accent-dim)",
          border: `2px solid ${
            status === "failed"
              ? "rgba(220, 38, 38, 0.2)"
              : status === "completed"
                ? "rgba(22, 163, 74, 0.2)"
                : "rgba(13, 148, 136, 0.2)"
          }`,
        }}
      >
        {status === "launching" || status === "running" ? (
          <div
            style={{
              width: 20,
              height: 20,
              border: "2px solid var(--color-accent)",
              borderTopColor: "transparent",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }}
          />
        ) : status === "completed" ? (
          <span
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 24,
              color: "var(--color-emerald)",
            }}
          >
            &#10003;
          </span>
        ) : (
          <span
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 24,
              color: "var(--color-rose)",
            }}
          >
            !
          </span>
        )}
      </div>

      {/* Title */}
      <h2
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 22,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          margin: "0 0 8px",
          textAlign: "center",
        }}
      >
        {status === "launching" && "Building Workflow..."}
        {status === "running" && "Workflow Running"}
        {status === "completed" && "Workflow Complete"}
        {status === "failed" && "Launch Failed"}
      </h2>

      {/* Progress steps — shown during launching */}
      {status === "launching" && (
        <div
          style={{
            margin: "16px 0 24px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            width: "100%",
            maxWidth: 320,
          }}
        >
          {STEPS.map((step, i) => (
            <div
              key={step.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                opacity: i <= activeStep ? 1 : 0.35,
                transition: "opacity 0.4s ease",
              }}
            >
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  backgroundColor:
                    i < activeStep
                      ? "var(--color-accent)"
                      : i === activeStep
                        ? "transparent"
                        : "var(--color-border)",
                  border:
                    i === activeStep
                      ? "2px solid var(--color-accent)"
                      : "2px solid transparent",
                }}
              >
                {i < activeStep ? (
                  <span style={{ color: "#fff", fontSize: 11, fontWeight: 700 }}>
                    &#10003;
                  </span>
                ) : i === activeStep ? (
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      backgroundColor: "var(--color-accent)",
                      animation: "pulse-dot 1.2s ease-in-out infinite",
                    }}
                  />
                ) : null}
              </div>
              <span
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: 13,
                  color:
                    i <= activeStep
                      ? "var(--color-text-primary)"
                      : "var(--color-text-secondary)",
                  fontWeight: i === activeStep ? 600 : 400,
                }}
              >
                {step.label}
              </span>
            </div>
          ))}
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--color-text-secondary)",
              textAlign: "center",
              marginTop: 8,
            }}
          >
            {elapsed}s elapsed
          </div>
        </div>
      )}

      {/* Running / completed subtitle */}
      {status !== "launching" && (
        <p
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            color: "var(--color-text-secondary)",
            margin: "0 0 24px",
            textAlign: "center",
            maxWidth: 400,
            lineHeight: 1.6,
          }}
        >
          {status === "running" &&
            "Redirecting to workflow dashboard..."}
          {status === "completed" &&
            "All tasks have been processed successfully."}
          {status === "failed" && (error || "Something went wrong. Please try again.")}
        </p>
      )}

      {/* Actions */}
      {workflowId && (status === "running" || status === "completed") && (
        <a
          href={`/workflows/${workflowId}`}
          style={{
            padding: "10px 24px",
            borderRadius: 8,
            backgroundColor: "var(--color-accent)",
            color: "#ffffff",
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            fontWeight: 600,
            textDecoration: "none",
            transition: "all 0.15s ease",
            boxShadow: "var(--shadow-md)",
          }}
        >
          View in Dashboard
        </a>
      )}

      {status === "failed" && (
        <button
          onClick={() => window.location.reload()}
          style={{
            padding: "10px 24px",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-base)",
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-ui)",
            fontSize: 14,
            fontWeight: 500,
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          Start Over
        </button>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.7); }
        }
      `}</style>
    </div>
  );
}
