"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Dot,
  type DotProps,
} from "recharts";
import type { VerificationFeedback } from "@/lib/types";

interface ScoreTrendChartProps {
  feedback: VerificationFeedback[];
}

// Custom dot — simple solid circle, color reflects pass/fail
function SolidDot(props: DotProps & { payload?: { passed: boolean } }) {
  const { cx, cy, payload } = props;
  if (cx === undefined || cy === undefined) return null;
  const passed = payload?.passed ?? false;
  const color  = passed ? "#16a34a" : "#dc2626";

  return (
    <circle cx={cx} cy={cy} r={4} fill={color} stroke="var(--color-base)" strokeWidth={1.5} />
  );
}

// Tooltip styled for light theme
function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ value: number; payload: { attempt: string; passed: boolean } }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const { value, payload: data } = payload[0];
  const pct    = Math.round(value * 100);
  const passed = data.passed;
  const color  = passed ? "#16a34a" : "#dc2626";

  return (
    <div
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        borderRadius: 4,
        padding: "6px 10px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <div
        style={{
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
          fontSize: 10,
          letterSpacing: "0.08em",
          marginBottom: 2,
        }}
      >
        {data.attempt}
      </div>
      <div
        style={{
          color,
          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
          fontSize: 14,
          fontWeight: 700,
        }}
      >
        {pct}%
      </div>
      <div
        style={{
          color: color,
          fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
          fontSize: 9,
          letterSpacing: "0.06em",
          marginTop: 1,
        }}
      >
        {passed ? "PASSED" : "FAILED"}
      </div>
    </div>
  );
}

export function ScoreTrendChart({ feedback }: ScoreTrendChartProps) {
  if (feedback.length === 0) return null;

  const data = feedback.map((fb) => ({
    attempt: `#${fb.attempt}`,
    score:   fb.score,
    passed:  fb.passed,
  }));

  const lineColor = "#0d9488";

  return (
    <div style={{ height: 180 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 12, right: 16, bottom: 4, left: -8 }}
        >
          {/* Threshold reference line at 0.7 */}
          <ReferenceLine
            y={0.7}
            stroke="#d9770644"
            strokeDasharray="4 3"
            label={{
              value: "0.7",
              position: "insideTopRight",
              fill: "#d9770688",
              fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)',
              fontSize: 9,
            }}
          />

          <XAxis
            dataKey="attempt"
            tick={{
              fill: "var(--color-text-muted)",
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 10,
            }}
            axisLine={{ stroke: "var(--color-border)" }}
            tickLine={false}
          />

          <YAxis
            domain={[0, 1]}
            tickCount={6}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{
              fill: "var(--color-text-muted)",
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 10,
            }}
            axisLine={{ stroke: "var(--color-border)" }}
            tickLine={false}
            width={38}
          />

          <Tooltip
            content={<ChartTooltip />}
            cursor={{
              stroke: "var(--color-border)",
              strokeWidth: 1,
              strokeDasharray: "4 3",
            }}
          />

          <Line
            type="monotone"
            dataKey="score"
            stroke={lineColor}
            strokeWidth={1.5}
            dot={({ key, ...rest }) => <SolidDot key={key} {...(rest as DotProps & { payload: { passed: boolean } })} />}
            activeDot={false}
            isAnimationActive={true}
            animationDuration={600}
            animationEasing="ease-out"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
