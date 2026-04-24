import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders a recognized status with the configured label", () => {
    render(<StatusBadge status="passed" />);
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it("maps in_progress to 'In Progress' (underscore → space)", () => {
    render(<StatusBadge status="in_progress" />);
    expect(screen.getByText("In Progress")).toBeInTheDocument();
  });

  it.each([
    ["pending", "Pending"],
    ["planning", "Planning"],
    ["ready", "Ready"],
    ["verifying", "Verifying"],
    ["blocked", "Blocked"],
  ] as const)("maps %s → %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("title-cases an unknown status as a fallback", () => {
    render(<StatusBadge status="quarantined" />);
    expect(screen.getByText("Quarantined")).toBeInTheDocument();
  });

  it("converts underscores to spaces in fallback labels", () => {
    render(<StatusBadge status="rate_limited" />);
    expect(screen.getByText("Rate limited")).toBeInTheDocument();
  });
});
