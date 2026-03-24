"use client";

import { useState, useRef, useEffect } from "react";

interface IdeaInputProps {
  onBuild: (idea: string) => void;
  onRefine: (idea: string) => void;
  onExampleLaunch: (idea: string) => void;
  isLaunching?: boolean;
  disabled?: boolean;
  initialIdea?: string;
}

const EXAMPLE_IDEAS = [
  "Analyze my Stripe revenue trends and draft a board update",
  "Build a REST API with auth, tests, and Docker",
  "Review this quarter's support tickets and find patterns",
  "Plan my meals for the week — healthy, under $12/serving, no dairy",
];

export function IdeaInput({
  onBuild,
  onRefine,
  onExampleLaunch,
  isLaunching,
  disabled,
  initialIdea,
}: IdeaInputProps) {
  const [idea, setIdea] = useState(initialIdea ?? "");
  const [launchingExample, setLaunchingExample] = useState<string | null>(null);
  const [typewriterText, setTypewriterText] = useState("");
  const [typewriterIdx, setTypewriterIdx] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isDisabled = disabled || isLaunching;

  // Sync initialIdea when it arrives asynchronously (e.g. from spec fetch)
  useEffect(() => {
    if (initialIdea) setIdea(initialIdea);
  }, [initialIdea]);

  // Reset pill state when launching ends (e.g. on error)
  useEffect(() => {
    if (!isLaunching) setLaunchingExample(null);
  }, [isLaunching]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Typewriter placeholder effect
  useEffect(() => {
    const currentExample = EXAMPLE_IDEAS[typewriterIdx];
    let charIdx = 0;
    let deleting = false;
    let pauseTimer: ReturnType<typeof setTimeout> | null = null;

    const tick = () => {
      if (!deleting) {
        charIdx++;
        setTypewriterText(currentExample.slice(0, charIdx));
        if (charIdx >= currentExample.length) {
          deleting = true;
          pauseTimer = setTimeout(tick, 2000); // pause before deleting
          return;
        }
        pauseTimer = setTimeout(tick, 45); // typing speed
      } else {
        charIdx--;
        setTypewriterText(currentExample.slice(0, charIdx));
        if (charIdx <= 0) {
          setTypewriterIdx((i) => (i + 1) % EXAMPLE_IDEAS.length);
          return;
        }
        pauseTimer = setTimeout(tick, 25); // deleting speed
      }
    };

    pauseTimer = setTimeout(tick, 300);

    return () => {
      if (pauseTimer) clearTimeout(pauseTimer);
    };
  }, [typewriterIdx]);

  const handleBuild = () => {
    if (idea.trim() && !isDisabled) {
      onBuild(idea.trim());
    }
  };

  const handleRefine = () => {
    if (idea.trim() && !isDisabled) {
      onRefine(idea.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && !e.metaKey) {
      e.preventDefault();
      handleBuild();
    } else if (e.key === "Enter" && e.metaKey) {
      e.preventDefault();
      handleRefine();
    }
  };

  const handleExampleClick = (example: string) => {
    if (isDisabled) return;
    setLaunchingExample(example);
    onExampleLaunch(example);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        padding: "0 24px",
      }}
    >
      {/* Title */}
      <h2
        className="animate-fade-in-up stagger-1"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 28,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          letterSpacing: "-0.02em",
          margin: "0 0 8px",
          textAlign: "center",
        }}
      >
        What would you like Rooben to do?
      </h2>
      <p
        className="animate-fade-in-up stagger-2"
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 15,
          color: "var(--color-text-secondary)",
          margin: "0 0 32px",
          textAlign: "center",
          maxWidth: 460,
          lineHeight: 1.5,
        }}
      >
        Describe your idea and Rooben will bring it to life &mdash; or refine the
        details together first.
      </p>

      {/* Input area */}
      <div style={{ width: "100%", maxWidth: 560 }}>
        <div
          className="animate-fade-in-up stagger-3"
          style={{
            position: "relative",
            borderRadius: 12,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-base)",
            boxShadow: "var(--shadow-md)",
            transition: "border-color 0.2s ease, box-shadow 0.2s ease",
          }}
        >
          <textarea
            ref={textareaRef}
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isDisabled}
            placeholder={typewriterText || "Describe what you want to build..."}
            rows={3}
            style={{
              width: "100%",
              padding: "16px 16px 56px",
              border: "none",
              borderRadius: 12,
              fontFamily: "var(--font-ui)",
              fontSize: 15,
              color: "var(--color-text-primary)",
              backgroundColor: "transparent",
              resize: "none",
              outline: "none",
              lineHeight: 1.5,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 10,
              right: 10,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: "var(--color-text-muted)",
                letterSpacing: "0.04em",
              }}
            >
              ENTER to build · CMD+ENTER to refine
            </span>
            <button
              type="button"
              onClick={handleRefine}
              disabled={!idea.trim() || isDisabled}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-base)",
                color:
                  idea.trim() && !isDisabled
                    ? "var(--color-text-secondary)"
                    : "var(--color-text-muted)",
                fontFamily: "var(--font-ui)",
                fontSize: 13,
                fontWeight: 600,
                cursor:
                  idea.trim() && !isDisabled ? "pointer" : "not-allowed",
                transition: "all 0.15s ease",
              }}
            >
              Refine & customize
            </button>
            <button
              type="button"
              onClick={handleBuild}
              disabled={!idea.trim() || isDisabled}
              style={{
                padding: "6px 16px",
                borderRadius: 6,
                border: "none",
                backgroundColor:
                  idea.trim() && !isDisabled
                    ? "var(--color-accent)"
                    : "var(--color-surface-3)",
                color:
                  idea.trim() && !isDisabled
                    ? "#ffffff"
                    : "var(--color-text-muted)",
                fontFamily: "var(--font-ui)",
                fontSize: 13,
                fontWeight: 600,
                cursor:
                  idea.trim() && !isDisabled ? "pointer" : "not-allowed",
                transition: "all 0.15s ease",
              }}
            >
              {isLaunching ? "Launching..." : "YOLO"}
            </button>
          </div>
        </div>
      </div>

      {/* Quick-start examples */}
      <div
        className="animate-fade-in-up stagger-4"
        style={{
          marginTop: 24,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: 8,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--color-text-muted)",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            marginRight: 4,
            alignSelf: "center",
          }}
        >
          Try:
        </span>
        {EXAMPLE_IDEAS.slice(0, 3).map((example) => (
          <button
            key={example}
            type="button"
            disabled={isDisabled}
            onClick={() => handleExampleClick(example)}
            style={{
              padding: "5px 12px",
              borderRadius: 16,
              border: "1px solid var(--color-border)",
              backgroundColor:
                launchingExample === example
                  ? "var(--color-accent-dim)"
                  : "var(--color-surface-1)",
              color:
                launchingExample === example
                  ? "var(--color-accent)"
                  : "var(--color-text-secondary)",
              fontFamily: "var(--font-ui)",
              fontSize: 12,
              cursor: isDisabled ? "not-allowed" : "pointer",
              transition: "all 0.15s ease",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              maxWidth: 220,
            }}
            onMouseEnter={(e) => {
              if (launchingExample !== example) {
                (e.currentTarget as HTMLButtonElement).style.borderColor =
                  "var(--color-accent)";
                (e.currentTarget as HTMLButtonElement).style.color =
                  "var(--color-accent)";
              }
            }}
            onMouseLeave={(e) => {
              if (launchingExample !== example) {
                (e.currentTarget as HTMLButtonElement).style.borderColor =
                  "var(--color-border)";
                (e.currentTarget as HTMLButtonElement).style.color =
                  "var(--color-text-secondary)";
              }
            }}
          >
            {launchingExample === example ? "Launching..." : example}
          </button>
        ))}
      </div>

    </div>
  );
}
