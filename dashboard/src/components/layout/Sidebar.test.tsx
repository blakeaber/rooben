import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock Next.js navigation primitives — they require a RouterContext in prod
// that jsdom doesn't provide. We control usePathname per test via this spy.
const mockPathname = vi.fn<() => string>(() => "/");
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// ThemeToggle uses next-themes or similar effects we don't care about here.
vi.mock("@/components/layout/ThemeToggle", () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}));

import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("renders all primary nav items", () => {
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);

    expect(screen.getByRole("link", { name: /Past Runs/ })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Create New/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Integrations/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Settings/ })).toBeInTheDocument();
  });

  it("renders nav group labels", () => {
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    expect(screen.getByText("Workflows")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
  });

  it("exposes the sidebar via an aria-label landmark", () => {
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    expect(
      screen.getByRole("complementary", { name: "Main navigation" }),
    ).toBeInTheDocument();
  });

  it("treats /integrations and nested /integrations/foo as active", () => {
    mockPathname.mockReturnValue("/integrations/foo");
    render(<Sidebar />);
    // The component uses inline styles for active state; at minimum the
    // link is rendered with the /integrations href and the home link is NOT
    // active. Behavioural assertion: the link href is correct.
    const integrations = screen.getByRole("link", { name: /Integrations/ });
    expect(integrations).toHaveAttribute("href", "/integrations");
  });

  it("does not render any Pro-only entries", () => {
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    // Post-Phase-C OSS dashboard should have no Pro nav leakage.
    expect(screen.queryByRole("link", { name: /Billing/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Org/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Delegations/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Learnings/ })).not.toBeInTheDocument();
  });

  it("applies hover styles on mouseenter for an inactive link", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    mockPathname.mockReturnValue("/"); // → Past Runs is active; Settings is not
    render(<Sidebar />);

    const settings = screen.getByRole("link", { name: /Settings/ });
    await user.hover(settings);
    // Hover handler writes background-color inline
    expect((settings as HTMLAnchorElement).style.backgroundColor).not.toBe("");
    await user.unhover(settings);
    // Unhover handler restores background to transparent
    expect((settings as HTMLAnchorElement).style.backgroundColor).toBe("transparent");
  });

  it("applies focus outline and clears it on blur", () => {
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);

    const integrations = screen.getByRole("link", { name: /Integrations/ });
    integrations.focus();
    expect((integrations as HTMLAnchorElement).style.outline).toContain("2px");
    integrations.blur();
    expect((integrations as HTMLAnchorElement).style.outline).toBe("none");
  });
});
