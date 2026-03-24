"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const COMMAND = 'rooben go "Write a competitive analysis of the AI agent market"';

const OUTPUT_LINES = [
  { text: "  Planning workflow...", color: "#14b8a6", delay: 800 },
  { text: "  Spec validated. 3 agents assigned.", color: "#94a3b8", delay: 1400 },
  { text: "", color: "", delay: 1600 },
  { text: "  [agent-1] Market Research    ████████░░  running", color: "#14b8a6", delay: 2000 },
  { text: "  [agent-2] Data Analysis      ████████░░  running", color: "#818cf8", delay: 2400 },
  { text: "  [agent-1] Market Research    ██████████  passed  95%", color: "#4ade80", delay: 4000 },
  { text: "  [agent-2] Data Analysis      ██████████  passed  92%", color: "#4ade80", delay: 4600 },
  { text: "  [agent-3] Draft Report       ████████░░  running", color: "#14b8a6", delay: 5200 },
  { text: "  [agent-3] Draft Report       ██████████  passed  91%", color: "#4ade80", delay: 7000 },
  { text: "", color: "", delay: 7200 },
  { text: "  Verification: 3/3 passed. Score: 93%", color: "#4ade80", delay: 7600 },
  { text: "  Cost: $0.37 (under $1.00 budget)", color: "#fbbf24", delay: 8000 },
  { text: "  Output saved: competitive-analysis.md", color: "#94a3b8", delay: 8400 },
];

export function TerminalDemo() {
  const [typedChars, setTypedChars] = useState(0);
  const [visibleLines, setVisibleLines] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const hasStarted = useRef(false);
  const timerRefs = useRef<ReturnType<typeof setTimeout>[]>([]);

  const runDemo = useCallback(() => {
    setTypedChars(0);
    setVisibleLines(0);
    setIsTyping(true);
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];

    // Typing animation for the command
    for (let i = 0; i <= COMMAND.length; i++) {
      const t = setTimeout(() => setTypedChars(i), i * 35);
      timerRefs.current.push(t);
    }

    // After typing completes, show output lines
    const typingDone = COMMAND.length * 35 + 200;
    const t0 = setTimeout(() => setIsTyping(false), typingDone);
    timerRefs.current.push(t0);

    for (let i = 0; i < OUTPUT_LINES.length; i++) {
      const t = setTimeout(
        () => setVisibleLines(i + 1),
        typingDone + OUTPUT_LINES[i].delay
      );
      timerRefs.current.push(t);
    }

    // Loop
    const totalDuration = typingDone + 10000;
    const restart = setTimeout(() => runDemo(), totalDuration);
    timerRefs.current.push(restart);
  }, []);

  useEffect(() => {
    if (hasStarted.current) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasStarted.current) {
          hasStarted.current = true;
          runDemo();
        }
      },
      { threshold: 0.3 }
    );

    if (containerRef.current) observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      timerRefs.current.forEach(clearTimeout);
    };
  }, [runDemo]);

  return (
    <div
      ref={containerRef}
      style={{
        maxWidth: 640,
        margin: "0 auto",
        borderRadius: 12,
        overflow: "hidden",
        backgroundColor: "#0d1117",
        border: "1px solid rgba(255,255,255,0.08)",
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        lineHeight: 1.7,
      }}
    >
      {/* Title bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 16px",
          background: "rgba(255,255,255,0.03)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
        <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
        <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
        <span style={{ marginLeft: 8, fontSize: 11, color: "#64748b" }}>Terminal</span>
      </div>

      {/* Terminal content */}
      <div style={{ padding: "16px 20px", minHeight: 280 }}>
        {/* Command line */}
        <div>
          <span style={{ color: "#4ade80" }}>$ </span>
          <span style={{ color: "#e2e8f0" }}>
            {COMMAND.slice(0, typedChars)}
          </span>
          {isTyping && (
            <span
              style={{ color: "#14b8a6", animation: "blink 1s step-end infinite" }}
            >
              |
            </span>
          )}
        </div>

        {/* Output lines */}
        {OUTPUT_LINES.slice(0, visibleLines).map((line, i) => (
          <div
            key={i}
            style={{
              color: line.color || "transparent",
              opacity: 0,
              animation: "fadeIn 0.3s ease forwards",
              minHeight: line.text ? undefined : 8,
            }}
          >
            {line.text || "\u00A0"}
          </div>
        ))}
      </div>

      {/* Inline styles for animations */}
      <style>{`
        @keyframes blink { 50% { opacity: 0; } }
        @keyframes fadeIn { to { opacity: 1; } }
      `}</style>
    </div>
  );
}
