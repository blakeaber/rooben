"use client";

import type { VerificationFeedback } from "@/lib/types";
import { FeedbackCard } from "./FeedbackCard";

interface AttemptTimelineProps {
  feedback: VerificationFeedback[];
}

export function AttemptTimeline({ feedback }: AttemptTimelineProps) {
  if (feedback.length === 0) {
    return (
      <div
        className="py-8 text-center"
        style={{
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
          fontSize: 12,
          letterSpacing: "0.05em",
        }}
      >
        NO VERIFICATION ATTEMPTS
      </div>
    );
  }

  return (
    <ol
      className="relative"
      style={{ paddingLeft: 28 }}
      aria-label="Verification attempt timeline"
    >
      {/* Vertical connecting line */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          left: 7,
          top: 10,
          bottom: 10,
          width: 1,
          backgroundColor: "var(--color-border)",
        }}
      />

      {feedback.map((fb, i) => {
        const isPass    = fb.passed;
        const dotColor  = isPass ? "#16a34a" : "#dc2626";
        const isLast    = i === feedback.length - 1;

        return (
          <li
            key={i}
            className={isLast ? "" : "mb-5"}
            style={{ position: "relative" }}
          >
            {/* Timeline dot — solid, no glow */}
            <div
              aria-hidden="true"
              style={{
                position: "absolute",
                left: -21,
                top: 10,
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: dotColor,
                border: "2px solid var(--color-base)",
                flexShrink: 0,
              }}
            />

            {/* Attempt label above each card */}
            <div
              className="mb-1.5 flex items-center gap-2"
              style={{ paddingLeft: 2 }}
            >
              <span
                style={{
                  color: "var(--color-text-primary)",
                  fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                  fontSize: 10,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                Attempt #{fb.attempt}
              </span>
              <span
                style={{
                  color: "var(--color-border-muted)",
                  fontSize: 10,
                }}
                aria-hidden="true"
              >
                —
              </span>
              <span
                style={{
                  color: isPass ? "#16a34a" : "#dc2626",
                  fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                  fontSize: 10,
                  letterSpacing: "0.08em",
                }}
              >
                {isPass ? "PASSED" : "FAILED"}
              </span>
            </div>

            <FeedbackCard feedback={fb} />
          </li>
        );
      })}
    </ol>
  );
}
