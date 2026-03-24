"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────

interface BuilderQuestion {
  text: string;
  choices: string[];
  allow_freeform: boolean;
}

interface BuildStartResponse {
  session_id: string;
  detected_type: string;
  display_type: string;
  questions: BuilderQuestion[];
  phase: string;
  completeness: number;
}

interface BuildAnswerResponse {
  session_id: string;
  phase: string;
  completeness: number;
  questions: BuilderQuestion[];
}

interface BuildDraftResponse {
  session_id: string;
  manifest: Record<string, unknown>;
  yaml_preview: string;
}

// ── Type selection cards ──────────────────────────────────────────────────

const TYPE_OPTIONS = [
  {
    value: "integration",
    label: "Data Source",
    description: "Connect an external service via MCP",
    icon: "D",
  },
  {
    value: "template",
    label: "Template",
    description: "A reusable workflow starting point",
    icon: "T",
  },
  {
    value: "agent",
    label: "Agent",
    description: "A specialized AI agent preset",
    icon: "A",
  },
];

// ── Question item component ───────────────────────────────────────────────

function QuestionItem({
  question,
  onAnswer,
  disabled,
}: {
  question: BuilderQuestion;
  onAnswer: (answer: string) => void;
  disabled: boolean;
}) {
  const [freeform, setFreeform] = useState("");

  return (
    <div
      style={{
        padding: "12px 16px",
        backgroundColor: "var(--color-surface-2)",
        borderRadius: "8px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
      }}
    >
      {/* Choice buttons */}
      {question.choices.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {question.choices.map((choice) => (
            <button
              key={choice}
              onClick={() => !disabled && onAnswer(choice)}
              disabled={disabled}
              style={{
                padding: "6px 14px",
                borderRadius: "6px",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-base)",
                color: "var(--color-text-primary)",
                fontFamily: "var(--font-ui)",
                fontSize: "12px",
                cursor: disabled ? "not-allowed" : "pointer",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                if (!disabled) {
                  e.currentTarget.style.borderColor = "#0d9488";
                  e.currentTarget.style.color = "#0d9488";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--color-border)";
                e.currentTarget.style.color = "var(--color-text-primary)";
              }}
            >
              {choice}
            </button>
          ))}
        </div>
      )}

      {/* Freeform input */}
      {question.allow_freeform && (
        <div style={{ display: "flex", gap: "6px" }}>
          <input
            type="text"
            value={freeform}
            onChange={(e) => setFreeform(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && freeform.trim() && !disabled) {
                onAnswer(freeform.trim());
                setFreeform("");
              }
            }}
            disabled={disabled}
            placeholder="Type your answer..."
            style={{
              flex: 1,
              padding: "8px 12px",
              border: "1px solid var(--color-border)",
              borderRadius: "6px",
              fontFamily: "var(--font-ui)",
              fontSize: "13px",
              outline: "none",
            }}
          />
          <button
            onClick={() => {
              if (freeform.trim() && !disabled) {
                onAnswer(freeform.trim());
                setFreeform("");
              }
            }}
            disabled={!freeform.trim() || disabled}
            style={{
              padding: "8px 14px",
              borderRadius: "6px",
              border: "none",
              backgroundColor:
                freeform.trim() && !disabled ? "#0d9488" : "var(--color-border-muted)",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: "12px",
              fontWeight: 600,
              cursor:
                freeform.trim() && !disabled ? "pointer" : "not-allowed",
            }}
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}

// ── Completeness bar ──────────────────────────────────────────────────────

function CompletenessBar({ value, phase }: { value: number; phase: string }) {
  return (
    <div style={{ marginBottom: "20px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "6px",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "10px",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
          }}
        >
          {phase === "review" ? "Ready for review" : `${phase} phase`}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "10px",
            color: "var(--color-text-secondary)",
          }}
        >
          {Math.round(value * 100)}%
        </span>
      </div>
      <div
        style={{
          height: "4px",
          backgroundColor: "var(--color-border)",
          borderRadius: "2px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${value * 100}%`,
            backgroundColor: value >= 0.7 ? "#16a34a" : "#0d9488",
            borderRadius: "2px",
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function CreateExtensionPage() {
  const router = useRouter();

  // Step 0: Type selection + description
  const [description, setDescription] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);

  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<BuilderQuestion[]>([]);
  const [phase, setPhase] = useState("discovery");
  const [completeness, setCompleteness] = useState(0);
  const [detectedType, setDetectedType] = useState("");
  const [answers, setAnswers] = useState<{ q: string; a: string }[]>([]);

  // Sequential Q&A state
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Review state
  const [yamlPreview, setYamlPreview] = useState("");
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [installed, setInstalled] = useState(false);
  const [installedName, setInstalledName] = useState("");
  const [installedType, setInstalledType] = useState("");

  // Auto-scroll to bottom when answers change or loading state changes
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [answers, loading, currentQuestionIndex]);

  // Reset question index when a new batch of questions arrives
  useEffect(() => {
    setCurrentQuestionIndex(0);
  }, [questions]);

  const isQA = sessionId && phase !== "review" && !installed;
  const isReview = phase === "review" && !installed;

  /** Handle answering one question in the sequential flow */
  const handleSequentialAnswer = (answer: string) => {
    const currentQ = questions[currentQuestionIndex];
    if (!currentQ) return;

    // Record this Q&A in the history
    setAnswers((prev) => [...prev, { q: currentQ.text, a: answer }]);

    if (currentQuestionIndex < questions.length - 1) {
      // More questions in this batch -- advance to the next one
      setCurrentQuestionIndex((prev) => prev + 1);
    } else {
      // Last question in the batch -- call the API for the next batch
      handleAnswer(answer);
    }
  };

  const handleStart = async () => {
    if (!description.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<BuildStartResponse>("/api/hub/build/start", {
        method: "POST",
        body: JSON.stringify({
          description: description.trim(),
          type: selectedType || undefined,
        }),
      });
      setSessionId(res.session_id);
      setDetectedType(res.detected_type);
      setQuestions(res.questions);
      setPhase(res.phase);
      setCompleteness(res.completeness);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start builder");
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = async (answer: string) => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<BuildAnswerResponse>("/api/hub/build/answer", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, answer }),
      });
      setPhase(res.phase);
      setCompleteness(res.completeness);
      setQuestions(res.questions);

      if (res.phase === "review") {
        // Auto-fetch draft
        const draft = await apiFetch<BuildDraftResponse>(
          "/api/hub/build/draft",
          {
            method: "POST",
            body: JSON.stringify({ session_id: sessionId }),
          }
        );
        setYamlPreview(draft.yaml_preview);
        setManifest(draft.manifest);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to process answer");
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{
        installed: boolean;
        name: string;
        type: string;
        display_type: string;
      }>("/api/hub/build/install", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
      setInstalled(true);
      setInstalledName(res.name);
      setInstalledType(res.display_type);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Install failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-in-up" style={{ maxWidth: "700px" }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: "20px" }}>
        <button
          onClick={() => router.push("/integrations")}
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: "#0d9488",
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: 0,
          }}
        >
          &larr; Integrations Hub
        </button>
      </div>

      {/* Header */}
      <div style={{ marginBottom: "24px" }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "10px",
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
            marginBottom: "6px",
          }}
        >
          ROOBEN / INTEGRATIONS / CREATE
        </div>
        <h1
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "22px",
            fontWeight: 700,
            color: "var(--color-text-primary)",
            margin: 0,
          }}
        >
          AI-Assisted Builder
        </h1>
        <p
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            color: "var(--color-text-secondary)",
            marginTop: "4px",
          }}
        >
          Describe what you want to create and we&apos;ll guide you through building it.
        </p>
        <div style={{ borderBottom: "1px solid var(--color-border)", marginTop: "16px" }} />
      </div>

      {/* Step 0: Type selection + description */}
      {!sessionId && !installed && (
        <div
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {/* Type cards */}
          <div>
            <label
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--color-text-primary)",
                display: "block",
                marginBottom: "10px",
              }}
            >
              What type of extension? (optional &mdash; we can auto-detect)
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
              {TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() =>
                    setSelectedType(selectedType === opt.value ? null : opt.value)
                  }
                  style={{
                    padding: "14px",
                    borderRadius: "8px",
                    border:
                      selectedType === opt.value
                        ? "2px solid #0d9488"
                        : "1px solid var(--color-border)",
                    backgroundColor:
                      selectedType === opt.value ? "#f0fdfa" : "var(--color-base)",
                    cursor: "pointer",
                    textAlign: "center",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "8px",
                      border: "1px solid var(--color-border)",
                      backgroundColor: "var(--color-surface-2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: "var(--font-mono)",
                      fontSize: "14px",
                      fontWeight: 600,
                      color: selectedType === opt.value ? "#0d9488" : "var(--color-text-muted)",
                      margin: "0 auto 8px",
                    }}
                  >
                    {opt.icon}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "var(--color-text-primary)",
                    }}
                  >
                    {opt.label}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: "11px",
                      color: "var(--color-text-secondary)",
                      marginTop: "2px",
                    }}
                  >
                    {opt.description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <div>
            <label
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--color-text-primary)",
                display: "block",
                marginBottom: "6px",
              }}
            >
              Describe what you want to create
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Connect to Slack to send notifications, or create a reusable competitive analysis template..."
              rows={4}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && description.trim()) {
                  e.preventDefault();
                  handleStart();
                }
              }}
              style={{
                width: "100%",
                padding: "10px",
                border: "1px solid var(--color-border)",
                borderRadius: "6px",
                fontFamily: "var(--font-ui)",
                fontSize: "13px",
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <div
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: "12px",
                color: "#dc2626",
              }}
            >
              {error}
            </div>
          )}

          <button
            onClick={handleStart}
            disabled={!description.trim() || loading}
            style={{
              padding: "10px 20px",
              borderRadius: "6px",
              border: "none",
              backgroundColor:
                !description.trim() || loading ? "var(--color-border-muted)" : "#0d9488",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: "13px",
              fontWeight: 600,
              cursor:
                !description.trim() || loading ? "not-allowed" : "pointer",
              alignSelf: "flex-start",
            }}
          >
            {loading ? "Starting..." : "Start Building"}
          </button>
        </div>
      )}

      {/* Adaptive Q&A phase */}
      {isQA && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0px",
          }}
        >
          {/* Detected type badge */}
          {detectedType && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "12px",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "10px",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--color-text-muted)",
                }}
              >
                Creating:
              </span>
              <span
                style={{
                  display: "inline-block",
                  padding: "2px 10px",
                  borderRadius: "9999px",
                  fontSize: "11px",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                  backgroundColor: "#f0fdfa",
                  color: "#0d9488",
                  textTransform: "capitalize",
                }}
              >
                {detectedType === "integration" ? "Data Source" : detectedType}
              </span>
            </div>
          )}

          <CompletenessBar value={completeness} phase={phase} />

          {/* Chat-style answer history */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              marginBottom: questions.length > 0 ? "16px" : "0",
            }}
          >
            {answers.map((a, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {/* System question bubble */}
                <div style={{ display: "flex", justifyContent: "flex-start" }}>
                  <div
                    style={{
                      maxWidth: "85%",
                      padding: "12px 16px",
                      borderRadius: "12px 12px 12px 4px",
                      backgroundColor: "var(--color-base)",
                      border: "1px solid var(--color-border)",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
                    }}
                  >
                    <span
                      style={{
                        display: "block",
                        fontFamily: "var(--font-mono)",
                        fontSize: "10px",
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                        marginBottom: "6px",
                        color: "var(--color-text-muted)",
                        opacity: 0.6,
                      }}
                    >
                      Rooben
                    </span>
                    <p
                      style={{
                        margin: 0,
                        fontFamily: "var(--font-ui)",
                        fontSize: "14px",
                        lineHeight: 1.6,
                        color: "var(--color-text-primary)",
                      }}
                    >
                      {a.q}
                    </p>
                  </div>
                </div>
                {/* User answer bubble */}
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div
                    style={{
                      maxWidth: "85%",
                      padding: "12px 16px",
                      borderRadius: "12px 12px 4px 12px",
                      backgroundColor: "#0d9488",
                      color: "#ffffff",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
                    }}
                  >
                    <span
                      style={{
                        display: "block",
                        fontFamily: "var(--font-mono)",
                        fontSize: "10px",
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                        marginBottom: "6px",
                        opacity: 0.6,
                      }}
                    >
                      You
                    </span>
                    <p
                      style={{
                        margin: 0,
                        fontFamily: "var(--font-ui)",
                        fontSize: "14px",
                        lineHeight: 1.6,
                      }}
                    >
                      {a.a}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Current question (one at a time) */}
          {!loading && questions.length > 0 && questions[currentQuestionIndex] && (
            <div
              className="animate-fade-in-up"
              style={{ display: "flex", flexDirection: "column", gap: "8px" }}
            >
              {/* System question bubble */}
              <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "4px" }}>
                <div
                  style={{
                    maxWidth: "85%",
                    padding: "12px 16px",
                    borderRadius: "12px 12px 12px 4px",
                    backgroundColor: "var(--color-base)",
                    border: "1px solid var(--color-border)",
                    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontFamily: "var(--font-mono)",
                      fontSize: "10px",
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      marginBottom: "6px",
                      color: "var(--color-text-muted)",
                      opacity: 0.6,
                    }}
                  >
                    Rooben
                  </span>
                  <p
                    style={{
                      margin: 0,
                      fontFamily: "var(--font-ui)",
                      fontSize: "14px",
                      lineHeight: 1.6,
                      color: "var(--color-text-primary)",
                    }}
                  >
                    {questions[currentQuestionIndex].text}
                  </p>
                </div>
              </div>

              {/* Question counter */}
              {questions.length > 1 && (
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "10px",
                    letterSpacing: "0.06em",
                    color: "var(--color-text-muted)",
                    marginBottom: "4px",
                  }}
                >
                  Question {currentQuestionIndex + 1} of {questions.length} in this round
                </div>
              )}

              {/* Answer input area */}
              <QuestionItem
                key={`${phase}-${currentQuestionIndex}`}
                question={questions[currentQuestionIndex]}
                onAnswer={handleSequentialAnswer}
                disabled={loading}
              />
            </div>
          )}

          {loading && (
            <div
              style={{
                display: "flex",
                justifyContent: "flex-start",
                marginTop: "16px",
                marginBottom: "16px",
              }}
            >
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: "12px 12px 12px 4px",
                  backgroundColor: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
                }}
              >
                <span
                  style={{
                    display: "block",
                    fontFamily: "var(--font-mono)",
                    fontSize: "10px",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    marginBottom: "6px",
                    color: "var(--color-text-muted)",
                    opacity: 0.6,
                  }}
                >
                  Rooben
                </span>
                <div style={{ display: "flex", gap: "3px", alignItems: "center" }}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      style={{
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        backgroundColor: "#0d9488",
                        opacity: 0.4,
                        display: "inline-block",
                        animation: `builder-pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                      }}
                    />
                  ))}
                  <span
                    style={{
                      marginLeft: "6px",
                      fontFamily: "var(--font-ui)",
                      fontSize: "12px",
                      color: "var(--color-text-muted)",
                      fontStyle: "italic",
                    }}
                  >
                    Thinking...
                  </span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div
              style={{
                fontFamily: "var(--font-ui)",
                fontSize: "12px",
                color: "#dc2626",
                marginTop: "8px",
              }}
            >
              {error}
            </div>
          )}

          <div ref={chatBottomRef} />

          <style>{`
            @keyframes builder-pulse {
              0%, 100% { opacity: 0.3; transform: scale(1); }
              50% { opacity: 1; transform: scale(1.2); }
            }
          `}</style>
        </div>
      )}

      {/* Review phase */}
      {isReview && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          <CompletenessBar value={completeness} phase={phase} />

          {/* Collapsible Q&A summary */}
          {answers.length > 0 && (
            <details
              style={{
                backgroundColor: "var(--color-base)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
                padding: "0",
              }}
            >
              <summary
                style={{
                  padding: "12px 16px",
                  fontFamily: "var(--font-mono)",
                  fontSize: "11px",
                  letterSpacing: "0.06em",
                  color: "var(--color-text-muted)",
                  cursor: "pointer",
                  userSelect: "none",
                }}
              >
                Q&A History ({answers.length} answers)
              </summary>
              <div
                style={{
                  padding: "0 16px 12px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                {answers.map((a, i) => (
                  <div key={i} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <div
                      style={{
                        fontFamily: "var(--font-ui)",
                        fontSize: "12px",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      {a.q}
                    </div>
                    <div
                      style={{
                        padding: "6px 10px",
                        backgroundColor: "#f0fdfa",
                        borderRadius: "6px",
                        fontFamily: "var(--font-ui)",
                        fontSize: "12px",
                        color: "var(--color-text-primary)",
                      }}
                    >
                      {a.a}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}

          <div
            style={{
              backgroundColor: "var(--color-base)",
              border: "1px solid var(--color-border)",
              borderRadius: "8px",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "10px",
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "var(--color-text-muted)",
              }}
            >
              Extension Manifest Preview
            </div>

            {manifest && (
              <div>
                <h3
                  style={{
                    fontFamily: "var(--font-ui)",
                    fontSize: "16px",
                    fontWeight: 600,
                    color: "var(--color-text-primary)",
                    margin: "0 0 4px 0",
                  }}
                >
                  {(manifest.name as string) || "Extension"}
                </h3>
                <p
                  style={{
                    fontFamily: "var(--font-ui)",
                    fontSize: "13px",
                    color: "var(--color-text-secondary)",
                    margin: 0,
                  }}
                >
                  {(manifest.description as string) || ""}
                </p>
              </div>
            )}

            <div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "10px",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--color-text-muted)",
                  marginBottom: "8px",
                }}
              >
                YAML Config
              </div>
              <pre
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "11px",
                  color: "var(--color-text-primary)",
                  backgroundColor: "var(--color-surface-2)",
                  padding: "12px",
                  borderRadius: "4px",
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  maxHeight: "300px",
                }}
              >
                {yamlPreview}
              </pre>
            </div>

            {error && (
              <div
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: "12px",
                  color: "#dc2626",
                }}
              >
                {error}
              </div>
            )}

            <div style={{ display: "flex", gap: "8px" }}>
              <button
                onClick={handleInstall}
                disabled={loading}
                style={{
                  padding: "10px 20px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor: "#0d9488",
                  color: "#ffffff",
                  fontFamily: "var(--font-ui)",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: loading ? "wait" : "pointer",
                  opacity: loading ? 0.6 : 1,
                }}
              >
                {loading ? "Installing..." : "Install Extension"}
              </button>
              <button
                onClick={() => {
                  setPhase("refinement");
                  setQuestions([]);
                  handleAnswer("continue refining");
                }}
                disabled={loading}
                style={{
                  padding: "10px 20px",
                  borderRadius: "6px",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-base)",
                  color: "var(--color-text-secondary)",
                  fontFamily: "var(--font-ui)",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: loading ? "wait" : "pointer",
                  opacity: loading ? 0.6 : 1,
                }}
              >
                Continue Refining
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Success state */}
      {installed && (
        <div
          style={{
            backgroundColor: "#f0fdf4",
            border: "1px solid #bbf7d0",
            borderRadius: "8px",
            padding: "28px",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "32px", marginBottom: "12px" }}>&#10003;</div>
          <h3
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: "16px",
              fontWeight: 600,
              color: "#16a34a",
              margin: "0 0 8px 0",
            }}
          >
            {installedType || "Extension"} Created
          </h3>
          <p
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: "13px",
              color: "var(--color-text-secondary)",
              margin: "0 0 20px 0",
            }}
          >
            Your extension <strong>{installedName}</strong> has been installed
            and is ready to use.
          </p>
          <div style={{ display: "flex", gap: "8px", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              onClick={() => router.push("/integrations")}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                border: "none",
                backgroundColor: "#0d9488",
                color: "#ffffff",
                fontFamily: "var(--font-ui)",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Back to Hub
            </button>
            <button
              onClick={() => router.push("/integrations/library")}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-base)",
                color: "var(--color-text-secondary)",
                fontFamily: "var(--font-ui)",
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              Browse Library
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
