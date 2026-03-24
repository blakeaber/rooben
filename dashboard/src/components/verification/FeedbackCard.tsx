import type { VerificationFeedback } from "@/lib/types";

interface FeedbackCardProps {
  feedback: VerificationFeedback;
}

export function FeedbackCard({ feedback }: FeedbackCardProps) {
  const pct       = Math.round(feedback.score * 100);
  const passed    = feedback.passed;
  const scoreColor = passed ? "#16a34a" : "#dc2626";

  return (
    <article
      className="rounded-md"
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      {/* Card header */}
      <header
        className="flex items-center gap-2 px-3 py-2"
        style={{ borderBottom: "1px solid #e5e7eb" }}
      >
        {/* Pass / fail indicator dot */}
        <span
          style={{
            display: "inline-block",
            width: 7,
            height: 7,
            borderRadius: "50%",
            backgroundColor: scoreColor,
            flexShrink: 0,
          }}
        />

        {/* Attempt number */}
        <span
          style={{
            color: "var(--color-text-primary)",
            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          Attempt #{feedback.attempt}
        </span>

        {/* Verifier type tag */}
        <span
          className="rounded px-1.5 py-0.5"
          style={{
            backgroundColor: "var(--color-surface-2)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-muted)",
            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
            fontSize: 9,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          {feedback.verifier_type}
        </span>

        {/* Score — right-aligned */}
        <span
          className="ml-auto"
          style={{
            color: scoreColor,
            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
            fontSize: 13,
            fontWeight: 700,
          }}
        >
          {pct}%
        </span>
      </header>

      {/* Score progress bar — thin, full-width */}
      <div style={{ height: 2, backgroundColor: "var(--color-border)" }}>
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            backgroundColor: scoreColor,
            transition: "width 0.4s ease",
          }}
        />
      </div>

      {/* Body */}
      <div className="px-3 py-2.5 space-y-3">
        {/* Feedback narrative */}
        {feedback.feedback && (
          <p
            style={{
              color: "var(--color-text-secondary)",
              fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
              fontSize: 12,
              lineHeight: 1.6,
            }}
          >
            {feedback.feedback}
          </p>
        )}

        {/* Suggested improvements */}
        {feedback.suggested_improvements.length > 0 && (
          <section>
            <h5
              className="mb-1"
              style={{
                color: "var(--color-text-muted)",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 10,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Suggested Improvements
            </h5>
            <ul
              className="space-y-1"
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
              }}
            >
              {feedback.suggested_improvements.map((imp, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2"
                  style={{
                    color: "var(--color-text-secondary)",
                    fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                    fontSize: 12,
                  }}
                >
                  {/* Bullet — dim diamond */}
                  <span
                    style={{
                      color: "var(--color-border-muted)",
                      marginTop: 3,
                      flexShrink: 0,
                      fontSize: 8,
                    }}
                    aria-hidden="true"
                  >
                    ◆
                  </span>
                  {imp}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Test results mini-table */}
        {feedback.test_results.length > 0 && (
          <section>
            <h5
              className="mb-1.5"
              style={{
                color: "var(--color-text-muted)",
                fontFamily: 'var(--font-dm-sans, "DM Sans", sans-serif)',
                fontSize: 10,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Test Results
            </h5>
            <table className="w-full" style={{ borderCollapse: "collapse" }}>
              <tbody>
                {feedback.test_results.map((tr, i) => (
                  <tr
                    key={i}
                    style={{ borderTop: "1px solid #e5e7eb" }}
                  >
                    <td
                      className="py-1 pr-2"
                      style={{
                        color: "var(--color-text-secondary)",
                        fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                        fontSize: 11,
                        wordBreak: "break-word",
                      }}
                    >
                      {tr.name}
                    </td>
                    <td className="py-1 text-right" style={{ whiteSpace: "nowrap" }}>
                      <span
                        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5"
                        style={{
                          backgroundColor: tr.passed ? "#f0fdf4" : "#fef2f2",
                          border: `1px solid ${tr.passed ? "#bbf7d0" : "#fecaca"}`,
                          color: tr.passed ? "#16a34a" : "#dc2626",
                          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                          fontSize: 9,
                          letterSpacing: "0.06em",
                          textTransform: "uppercase",
                        }}
                      >
                        {tr.passed ? "PASS" : "FAIL"}
                      </span>
                    </td>
                    {tr.error_message && !tr.passed && (
                      <tr
                        style={{ borderTop: "none" }}
                      >
                        <td
                          colSpan={2}
                          className="pb-1.5 pt-0"
                          style={{
                            color: "#dc262699",
                            fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
                            fontSize: 10,
                            lineHeight: 1.4,
                          }}
                        >
                          {tr.error_message}
                        </td>
                      </tr>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </article>
  );
}
