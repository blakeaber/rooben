"use client";

import { RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from "recharts";

interface BudgetGaugeProps {
  label: string;
  used: number;
  max: number;
  unit?: string;
  /** "budget" (default): high % = red (spending limit).
   *  "progress": high % = green (task completion). */
  variant?: "budget" | "progress";
}

function gaugeColor(pct: number, variant: "budget" | "progress"): string {
  if (variant === "progress") {
    // Progress: more complete = better
    if (pct >= 80) return "#16a34a";
    if (pct >= 40) return "#0d9488";
    return "var(--color-text-muted)";
  }
  // Budget: higher consumption = more concerning
  if (pct >= 85) return "#dc2626";
  if (pct >= 60) return "#d97706";
  return "#16a34a";
}

export function BudgetGauge({ label, used, max, unit = "", variant = "budget" }: BudgetGaugeProps) {
  const pct = max > 0 ? Math.min((used / max) * 100, 100) : 0;
  const color = gaugeColor(pct, variant);

  const data = [{ value: pct }];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "4px",
      }}
    >
      {/* Gauge */}
      <div style={{ position: "relative", width: 140, height: 140 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="68%"
            outerRadius="100%"
            data={data}
            startAngle={220}
            endAngle={-40}
            barSize={10}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar
              background={{ fill: "var(--color-surface-3)" }}
              dataKey="value"
              cornerRadius={6}
              fill={color}
            />
          </RadialBarChart>
        </ResponsiveContainer>

        {/* Center content */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "22px",
              fontWeight: 700,
              color,
              lineHeight: 1,
            }}
          >
            {pct.toFixed(0)}%
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "9px",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
              marginTop: "4px",
            }}
          >
            {label}
          </div>
        </div>
      </div>

      {/* Usage readout */}
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          color: "var(--color-text-secondary)",
          letterSpacing: "0.05em",
          textAlign: "center",
        }}
      >
        <span style={{ color: "var(--color-text-primary)" }}>
          {used.toLocaleString()}
          {unit}
        </span>
        <span style={{ color: "var(--color-text-muted)", margin: "0 4px" }}>/</span>
        {max.toLocaleString()}
        {unit}
      </div>

      {/* Threshold tick marks */}
      <div
        style={{
          display: "flex",
          gap: "6px",
          marginTop: "2px",
        }}
      >
        {(variant === "progress"
          ? [
              { label: "LOW", color: "var(--color-text-muted)", active: pct < 40 },
              { label: "MID", color: "#0d9488", active: pct >= 40 && pct < 80 },
              { label: "DONE", color: "#16a34a", active: pct >= 80 },
            ]
          : [
              { label: "OK", color: "#16a34a", active: pct < 60 },
              { label: "WARN", color: "#d97706", active: pct >= 60 && pct < 85 },
              { label: "CRIT", color: "#dc2626", active: pct >= 85 },
            ]
        ).map((tier) => (
          <span
            key={tier.label}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "9px",
              letterSpacing: "0.1em",
              color: tier.active ? tier.color : "var(--color-text-muted)",
              opacity: tier.active ? 1 : 0.4,
              transition: "color 0.3s, opacity 0.3s",
            }}
          >
            {tier.label}
          </span>
        ))}
      </div>
    </div>
  );
}
