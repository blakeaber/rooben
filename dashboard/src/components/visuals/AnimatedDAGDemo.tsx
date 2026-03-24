"use client";

import { useState, useEffect, useRef, useCallback } from "react";

/* ─── Demo data ────────────────────────────────────────────────────────────── */
interface DemoNode {
  id: string;
  label: string;
  x: number;
  y: number;
  status: "pending" | "in_progress" | "verifying" | "passed";
  score?: number;
}

interface DemoEdge {
  from: string;
  to: string;
}

const INITIAL_NODES: DemoNode[] = [
  { id: "upload", label: "Upload Context", x: 280, y: 30, status: "pending" },
  { id: "plan", label: "Plan Workflow", x: 280, y: 100, status: "pending" },
  { id: "research", label: "Market Research", x: 100, y: 200, status: "pending" },
  { id: "data", label: "Data Analysis", x: 460, y: 200, status: "pending" },
  { id: "draft", label: "Draft Report", x: 180, y: 300, status: "pending" },
  { id: "review", label: "Verify & Score", x: 380, y: 300, status: "pending" },
  { id: "deliver", label: "Deliver Result", x: 280, y: 390, status: "pending" },
  { id: "outputs", label: "Get Outputs", x: 280, y: 460, status: "pending" },
];

const EDGES: DemoEdge[] = [
  { from: "upload", to: "plan" },
  { from: "plan", to: "research" },
  { from: "plan", to: "data" },
  { from: "research", to: "draft" },
  { from: "data", to: "review" },
  { from: "draft", to: "review" },
  { from: "review", to: "deliver" },
  { from: "deliver", to: "outputs" },
];

/* Sequence: [nodeId, targetStatus, delayMs, score?] */
const TIMELINE: [string, DemoNode["status"], number, number?][] = [
  ["upload", "in_progress", 0],
  ["upload", "passed", 600, 100],
  ["plan", "in_progress", 800],
  ["plan", "verifying", 2000],
  ["plan", "passed", 2600, 98],
  ["research", "in_progress", 3000],
  ["data", "in_progress", 3200],
  ["research", "verifying", 4800],
  ["data", "verifying", 5000],
  ["research", "passed", 5600, 95],
  ["data", "passed", 5800, 92],
  ["draft", "in_progress", 6200],
  ["draft", "verifying", 8000],
  ["draft", "passed", 8600, 91],
  ["review", "in_progress", 9000],
  ["review", "verifying", 10600],
  ["review", "passed", 11200, 96],
  ["deliver", "in_progress", 11600],
  ["deliver", "passed", 12400, 94],
  ["outputs", "in_progress", 12800],
  ["outputs", "passed", 13400, 99],
];

const COST_STEPS = [
  { at: 0, cost: 0 },
  { at: 2000, cost: 0.03 },
  { at: 3500, cost: 0.08 },
  { at: 5000, cost: 0.14 },
  { at: 6500, cost: 0.20 },
  { at: 8500, cost: 0.27 },
  { at: 10500, cost: 0.33 },
  { at: 12500, cost: 0.37 },
];

/* ─── Status → visual mapping ──────────────────────────────────────────────── */
function statusColor(s: DemoNode["status"]): string {
  switch (s) {
    case "pending":     return "rgba(255,255,255,0.06)";
    case "in_progress": return "rgba(20,184,166,0.15)";
    case "verifying":   return "rgba(99,102,241,0.15)";
    case "passed":      return "rgba(22,163,74,0.15)";
  }
}

function statusBorder(s: DemoNode["status"]): string {
  switch (s) {
    case "pending":     return "rgba(255,255,255,0.08)";
    case "in_progress": return "rgba(20,184,166,0.5)";
    case "verifying":   return "rgba(99,102,241,0.5)";
    case "passed":      return "rgba(22,163,74,0.5)";
  }
}

function statusGlow(s: DemoNode["status"]): string {
  switch (s) {
    case "pending":     return "none";
    case "in_progress": return "0 0 16px rgba(20,184,166,0.3)";
    case "verifying":   return "0 0 16px rgba(99,102,241,0.3)";
    case "passed":      return "0 0 20px rgba(22,163,74,0.3)";
  }
}

function statusLabel(s: DemoNode["status"]): string {
  switch (s) {
    case "pending":     return "PENDING";
    case "in_progress": return "RUNNING";
    case "verifying":   return "VERIFYING";
    case "passed":      return "PASSED";
  }
}

function statusLabelColor(s: DemoNode["status"]): string {
  switch (s) {
    case "pending":     return "#64748b";
    case "in_progress": return "#14b8a6";
    case "verifying":   return "#818cf8";
    case "passed":      return "#4ade80";
  }
}

/* ─── Component ────────────────────────────────────────────────────────────── */
export function AnimatedDAGDemo() {
  const [nodes, setNodes] = useState<DemoNode[]>(INITIAL_NODES);
  const [cost, setCost] = useState(0);
  const timerRefs = useRef<ReturnType<typeof setTimeout>[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const hasStarted = useRef(false);

  const runDemo = useCallback(() => {
    // Reset
    setNodes(INITIAL_NODES.map((n) => ({ ...n, status: "pending", score: undefined })));
    setCost(0);
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];

    for (const [nodeId, status, delay, score] of TIMELINE) {
      const t = setTimeout(() => {
        setNodes((prev) =>
          prev.map((n) => (n.id === nodeId ? { ...n, status, score: score ?? n.score } : n))
        );
      }, delay);
      timerRefs.current.push(t);
    }

    for (const step of COST_STEPS) {
      const t = setTimeout(() => setCost(step.cost), step.at);
      timerRefs.current.push(t);
    }

    // Loop after completion
    const restart = setTimeout(() => runDemo(), 16000);
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
      { threshold: 0.2 }
    );

    if (containerRef.current) observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      timerRefs.current.forEach(clearTimeout);
    };
  }, [runDemo]);

  const width = 580;
  const height = 500;

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        maxWidth: width,
        margin: "0 auto",
      }}
    >
      {/* Cost ticker */}
      <div
        style={{
          position: "absolute",
          top: 8,
          right: 12,
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 12px",
          borderRadius: 6,
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: cost > 0.3 ? "#fbbf24" : "#4ade80",
          zIndex: 10,
          transition: "color 0.3s ease",
        }}
      >
        <span style={{ color: "#64748b", fontSize: 10 }}>COST</span>
        ${cost.toFixed(2)}
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: "100%", height: "auto" }}
        aria-label="Animated workflow execution demo"
      >
        {/* Arrow marker definitions */}
        <defs>
          <marker
            id="arrow-active"
            viewBox="0 0 10 8"
            refX="9"
            refY="4"
            markerWidth="8"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 4 L 0 8 z" fill="rgba(20,184,166,0.5)" />
          </marker>
          <marker
            id="arrow-inactive"
            viewBox="0 0 10 8"
            refX="9"
            refY="4"
            markerWidth="8"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 4 L 0 8 z" fill="rgba(255,255,255,0.12)" />
          </marker>
        </defs>

        {/* Edges — cubic bezier curves */}
        {EDGES.map((edge) => {
          const from = nodes.find((n) => n.id === edge.from)!;
          const to = nodes.find((n) => n.id === edge.to)!;
          const isActive =
            from.status === "in_progress" ||
            from.status === "verifying" ||
            to.status === "in_progress";

          const x1 = from.x;
          const y1 = from.y + 18;
          const x2 = to.x;
          const y2 = to.y - 18;
          const midY = (y1 + y2) / 2;

          return (
            <path
              key={`${edge.from}-${edge.to}`}
              d={`M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`}
              fill="none"
              stroke={isActive ? "rgba(20,184,166,0.5)" : "rgba(255,255,255,0.08)"}
              strokeWidth={isActive ? 2 : 1}
              strokeDasharray={isActive ? "6 4" : "none"}
              markerEnd={isActive ? "url(#arrow-active)" : "url(#arrow-inactive)"}
              style={{
                transition: "stroke 0.4s ease, stroke-width 0.3s ease",
                animation: isActive ? "flow-dash 1s linear infinite" : "none",
              }}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => (
          <g key={node.id}>
            <rect
              x={node.x - 70}
              y={node.y - 18}
              width={140}
              height={36}
              rx={8}
              fill={statusColor(node.status)}
              stroke={statusBorder(node.status)}
              strokeWidth={1}
              style={{
                transition: "fill 0.4s ease, stroke 0.4s ease",
                filter: statusGlow(node.status) !== "none" ? `drop-shadow(${statusGlow(node.status)})` : "none",
              }}
            />
            {/* Node label */}
            <text
              x={node.x}
              y={node.y - 1}
              textAnchor="middle"
              fill="#e2e8f0"
              fontFamily="var(--font-ui)"
              fontSize={11}
              fontWeight={500}
            >
              {node.label}
            </text>
            {/* Status badge */}
            <text
              x={node.x}
              y={node.y + 12}
              textAnchor="middle"
              fill={statusLabelColor(node.status)}
              fontFamily="var(--font-mono)"
              fontSize={8}
              fontWeight={600}
              letterSpacing="0.08em"
            >
              {statusLabel(node.status)}
              {node.score !== undefined ? ` ${node.score}%` : ""}
            </text>

            {/* Check mark for passed */}
            {node.status === "passed" && (
              <text
                x={node.x + 60}
                y={node.y + 2}
                fill="#4ade80"
                fontSize={14}
                fontWeight={700}
                className="animate-check-pop"
              >
                &#10003;
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
