"use client";

import { useState, useRef, useEffect, useMemo } from "react";

export interface ChatMessage {
  id: string;
  role: "system" | "user";
  content: string;
  choices?: string[];
  allowFreeform?: boolean;
  timestamp: number;
}

interface RefinementChatProps {
  messages: ChatMessage[];
  completeness: number;
  phase: string;
  onAnswer: (answer: string) => void;
  onAccept: () => void;
  onContinue: () => void;
  isThinking: boolean;
  isReviewReady: boolean;
}

export function RefinementChat({
  messages,
  completeness,
  phase,
  onAnswer,
  onAccept,
  onContinue,
  isThinking,
  isReviewReady,
}: RefinementChatProps) {
  const [input, setInput] = useState("");
  const [selectedChoices, setSelectedChoices] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  useEffect(() => {
    if (!isThinking && !isReviewReady) {
      inputRef.current?.focus();
    }
  }, [isThinking, isReviewReady]);

  const lastSystemMessage = [...messages]
    .reverse()
    .find((m) => m.role === "system");
  const hasChoices =
    lastSystemMessage?.choices && lastSystemMessage.choices.length > 0;

  const handleSend = () => {
    const answer = selectedChoices.length > 0
      ? selectedChoices.join(", ")
      : input.trim();
    if (!answer || isThinking) return;
    onAnswer(answer);
    setInput("");
    setSelectedChoices([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 140px)",
        maxWidth: 680,
        margin: "0 auto",
      }}
    >
      {/* Progress bar */}
      <div
        className="animate-fade-in"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "0 0 16px",
        }}
      >
        <div
          style={{
            flex: 1,
            height: 4,
            borderRadius: 2,
            backgroundColor: "var(--color-surface-3)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${Math.round(completeness * 100)}%`,
              height: "100%",
              borderRadius: 2,
              backgroundColor: "var(--color-accent)",
              transition: "width 0.5s ease",
            }}
          />
        </div>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--color-text-muted)",
            letterSpacing: "0.04em",
            flexShrink: 0,
          }}
        >
          {Math.round(completeness * 100)}%
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--color-text-muted)",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            padding: "2px 8px",
            borderRadius: 4,
            backgroundColor: "var(--color-surface-3)",
            flexShrink: 0,
          }}
        >
          {phase}
        </span>
      </div>

      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "8px 0",
        }}
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            className="animate-fade-in-up"
            style={{
              display: "flex",
              justifyContent:
                msg.role === "user" ? "flex-end" : "flex-start",
              marginBottom: 16,
            }}
          >
            <div
              style={{
                maxWidth: "85%",
                padding: "12px 16px",
                borderRadius:
                  msg.role === "user"
                    ? "12px 12px 4px 12px"
                    : "12px 12px 12px 4px",
                backgroundColor:
                  msg.role === "user" ? "var(--color-accent)" : "var(--color-base)",
                color:
                  msg.role === "user"
                    ? "#ffffff"
                    : "var(--color-text-primary)",
                border:
                  msg.role === "user"
                    ? "none"
                    : "1px solid var(--color-border)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              {/* Role label */}
              <span
                style={{
                  display: "block",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  marginBottom: 6,
                  opacity: 0.6,
                }}
              >
                {msg.role === "user" ? "You" : "Rooben"}
              </span>

              {/* Content */}
              <p
                style={{
                  margin: 0,
                  fontFamily: "var(--font-ui)",
                  fontSize: 14,
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                }}
              >
                {msg.content}
              </p>
            </div>
          </div>
        ))}

        {/* Thinking indicator with rotating messages */}
        {isThinking && (
          <ThinkingIndicator />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Review actions (when spec is ready) */}
      {isReviewReady && !isThinking && (
        <div
          className="animate-fade-in-up"
          style={{
            padding: "16px 0",
            display: "flex",
            gap: 12,
            justifyContent: "center",
            borderTop: "1px solid var(--color-border)",
          }}
        >
          <button
            onClick={onAccept}
            style={{
              padding: "10px 24px",
              borderRadius: 8,
              border: "none",
              backgroundColor: "var(--color-accent)",
              color: "#ffffff",
              fontFamily: "var(--font-ui)",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            Review Specification
          </button>
          <button
            onClick={onContinue}
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
            Keep Refining
          </button>
        </div>
      )}

      {/* Input area */}
      {!isReviewReady && (
        <div
          style={{
            padding: "12px 0 0",
            borderTop: "1px solid var(--color-border)",
          }}
        >
          {/* Choice chips (when available) */}
          {hasChoices && !isThinking && (
            <div
              className="animate-fade-in-up"
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                marginBottom: 12,
              }}
            >
              {lastSystemMessage!.choices!.map((choice) => {
                const isSelected = selectedChoices.includes(choice);
                return (
                  <button
                    key={choice}
                    type="button"
                    data-testid="choice-chip"
                    onClick={() => {
                      setSelectedChoices((prev) =>
                        prev.includes(choice)
                          ? prev.filter((c) => c !== choice)
                          : [...prev, choice],
                      );
                      setInput("");
                    }}
                    style={{
                      padding: "7px 14px",
                      borderRadius: 20,
                      border: isSelected
                        ? "1.5px solid var(--color-accent)"
                        : "1px solid var(--color-border)",
                      backgroundColor: isSelected
                        ? "var(--color-accent-dim)"
                        : "var(--color-base)",
                      color: isSelected
                        ? "var(--color-accent)"
                        : "var(--color-text-secondary)",
                      fontFamily: "var(--font-ui)",
                      fontSize: 13,
                      fontWeight: isSelected ? 600 : 400,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {choice}
                  </button>
                );
              })}
            </div>
          )}

          {/* Text input */}
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "flex-end",
            }}
          >
            <div
              style={{
                flex: 1,
                position: "relative",
              }}
            >
              <input
                ref={inputRef}
                type="text"
                value={selectedChoices.length > 0 ? selectedChoices.join(", ") : input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setSelectedChoices([]);
                }}
                onKeyDown={handleKeyDown}
                disabled={isThinking}
                placeholder={
                  hasChoices
                    ? "Pick one or more options above, or type your own answer..."
                    : "Type your answer..."
                }
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 8,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-base)",
                  fontFamily: "var(--font-ui)",
                  fontSize: 14,
                  color: "var(--color-text-primary)",
                  outline: "none",
                  transition: "border-color 0.15s ease",
                }}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={isThinking || (!input.trim() && selectedChoices.length === 0)}
              style={{
                padding: "10px 18px",
                borderRadius: 8,
                border: "none",
                backgroundColor:
                  !isThinking && (input.trim() || selectedChoices.length > 0)
                    ? "var(--color-accent)"
                    : "var(--color-surface-3)",
                color:
                  !isThinking && (input.trim() || selectedChoices.length > 0)
                    ? "#ffffff"
                    : "var(--color-text-muted)",
                fontFamily: "var(--font-ui)",
                fontSize: 13,
                fontWeight: 600,
                cursor:
                  !isThinking && (input.trim() || selectedChoices.length > 0)
                    ? "pointer"
                    : "not-allowed",
                transition: "all 0.15s ease",
                flexShrink: 0,
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}

      {/* Pulse animation */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </div>
  );
}

// ─── Thinking indicator with rotating fun messages ──────────────────────────

const THINKING_MESSAGES = [
  "Thinking...",
  "Cranking the gears...",
  "Assembling the spec...",
  "Pondering your request...",
  "Consulting the agents...",
  "Mapping out the plan...",
  "Brewing up ideas...",
  "Connecting the dots...",
  "Running the numbers...",
  "Drafting the blueprint...",
  "Calibrating precision...",
  "Sharpening the details...",
  "Wrangling the specs...",
  "Tuning the engines...",
  "Almost there...",
];

function ThinkingIndicator() {
  const [msgIndex, setMsgIndex] = useState(0);
  // Pick a random start point so it doesn't always begin with "Thinking..."
  const shuffled = useMemo(() => {
    const arr = [...THINKING_MESSAGES];
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % shuffled.length);
    }, 2500);
    return () => clearInterval(id);
  }, [shuffled]);

  return (
    <div
      className="animate-fade-in"
      style={{
        display: "flex",
        justifyContent: "flex-start",
        marginBottom: 16,
      }}
    >
      <div
        style={{
          padding: "12px 16px",
          borderRadius: "12px 12px 12px 4px",
          backgroundColor: "var(--color-base)",
          border: "1px solid var(--color-border)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <span
          style={{
            display: "block",
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            marginBottom: 6,
            color: "var(--color-text-muted)",
          }}
        >
          Rooben
        </span>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <div style={{ display: "flex", gap: 3 }}>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  backgroundColor: "var(--color-accent)",
                  opacity: 0.4,
                  animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                }}
              />
            ))}
          </div>
          <span
            key={msgIndex}
            className="animate-fade-in"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              color: "var(--color-text-muted)",
              fontStyle: "italic",
            }}
          >
            {shuffled[msgIndex]}
          </span>
        </div>
      </div>
    </div>
  );
}
