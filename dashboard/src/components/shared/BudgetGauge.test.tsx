import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// recharts relies on ResizeObserver and SVG measurement that aren't reliable
// in jsdom. Mock the primitives we use to tiny stubs that still render the
// props we care about (the numeric value).
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="recharts-container">{children}</div>
  ),
  RadialBarChart: ({
    children,
    data,
  }: {
    children: React.ReactNode;
    data: { value: number }[];
  }) => (
    <div data-testid="radial-chart" data-value={data?.[0]?.value ?? 0}>
      {children}
    </div>
  ),
  RadialBar: ({ fill }: { fill: string }) => (
    <div data-testid="radial-bar" data-fill={fill} />
  ),
  PolarAngleAxis: () => <div data-testid="polar-angle" />,
}));

import { BudgetGauge } from "./BudgetGauge";

describe("BudgetGauge", () => {
  it("renders the provided label", () => {
    render(<BudgetGauge label="Tokens" used={100} max={1000} />);
    expect(screen.getByText("Tokens")).toBeInTheDocument();
  });

  it("computes percentage from used / max", () => {
    render(<BudgetGauge label="X" used={250} max={1000} />);
    const chart = screen.getByTestId("radial-chart");
    expect(chart.getAttribute("data-value")).toBe("25");
  });

  it("caps percentage at 100 when used exceeds max", () => {
    render(<BudgetGauge label="X" used={2000} max={1000} />);
    const chart = screen.getByTestId("radial-chart");
    expect(chart.getAttribute("data-value")).toBe("100");
  });

  it("handles max = 0 without NaN", () => {
    render(<BudgetGauge label="X" used={50} max={0} />);
    const chart = screen.getByTestId("radial-chart");
    expect(chart.getAttribute("data-value")).toBe("0");
  });

  it("uses red fill when budget variant is near limit", () => {
    render(<BudgetGauge label="X" used={900} max={1000} />);
    const bar = screen.getByTestId("radial-bar");
    expect(bar.getAttribute("data-fill")).toBe("#dc2626");
  });

  it("uses green fill when progress variant is mostly complete", () => {
    render(<BudgetGauge label="X" used={900} max={1000} variant="progress" />);
    const bar = screen.getByTestId("radial-bar");
    expect(bar.getAttribute("data-fill")).toBe("#16a34a");
  });

  it("uses amber fill when budget variant is mid-range", () => {
    render(<BudgetGauge label="X" used={700} max={1000} />);
    const bar = screen.getByTestId("radial-bar");
    expect(bar.getAttribute("data-fill")).toBe("#d97706");
  });
});
