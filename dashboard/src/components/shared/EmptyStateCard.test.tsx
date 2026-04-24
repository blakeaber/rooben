import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock next/link as a plain <a> — the test doesn't care about client-nav.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { EmptyStateCard } from "./EmptyStateCard";

describe("EmptyStateCard", () => {
  it("renders title and description", () => {
    render(<EmptyStateCard title="Nothing yet" description="Run something to see it here." />);
    expect(screen.getByRole("heading", { name: "Nothing yet" })).toBeInTheDocument();
    expect(screen.getByText(/Run something/)).toBeInTheDocument();
  });

  it("does not render an icon when not provided", () => {
    const { container } = render(
      <EmptyStateCard title="No icon" description="…" />,
    );
    // Only one direct text-wrapping div, no separate icon wrapper
    expect(container.textContent).toContain("No icon");
    expect(container.querySelector('[style*="fontSize: 28"]')).toBeNull();
  });

  it("renders an icon when provided", () => {
    render(<EmptyStateCard icon="🚀" title="Ready" description="…" />);
    expect(screen.getByText("🚀")).toBeInTheDocument();
  });

  it("renders the CTA link when both ctaLabel and ctaHref are provided", () => {
    render(
      <EmptyStateCard
        title="Get started"
        description="…"
        ctaLabel="Create one"
        ctaHref="/workflows/new"
      />,
    );
    const link = screen.getByRole("link", { name: "Create one" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/workflows/new");
  });

  it("omits the CTA when only one of the pair is provided", () => {
    render(<EmptyStateCard title="x" description="y" ctaLabel="Click" />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
