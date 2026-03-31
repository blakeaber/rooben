"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { isProEnabled } from "@/lib/pro-loader";

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workflows",
    items: [
      { href: "/", label: "Past Runs", icon: "W" },
      { href: "/workflows/new", label: "Create New", icon: "+" },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/integrations", label: "Integrations", icon: "\u222B" },
      { href: "/settings", label: "Settings", icon: "\u2699" },
    ],
  },
];

// Dynamically load Pro nav groups when Pro is installed
let proNavGroups: NavGroup[] = [];
if (isProEnabled) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const proConfig = require("@rooben-pro/dashboard/components/layout/sidebar-nav-config");
    proNavGroups = (proConfig.PRO_NAV_GROUPS ?? []).map((group: NavGroup) => ({
      ...group,
      items: group.items.map((item: NavItem) => ({
        ...item,
        href: `/pro${item.href}`,
      })),
    }));
  } catch {
    // Pro not available — no nav items added
  }
}

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/" || href === "/workflows/new" || href === "/settings") {
      return pathname === href;
    }
    if (href === "/integrations") {
      return pathname === "/integrations" || pathname.startsWith("/integrations/");
    }
    return pathname.startsWith(href);
  };

  return (
    <aside
      className="relative flex w-56 shrink-0 flex-col"
      style={{
        backgroundColor: "var(--color-base)",
        borderRight: "1px solid var(--color-border)",
      }}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div
        className="px-4 py-5"
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        <div className="animate-fade-in stagger-1" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              borderRadius: 6,
              background: "var(--gradient-rooben)",
              backgroundSize: "200% 200%",
              color: "#ffffff",
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              fontWeight: 700,
            }}
            aria-hidden="true"
          >
            R
          </span>
          <h1
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 17,
              fontWeight: 700,
              letterSpacing: "-0.01em",
              color: "var(--color-text-primary)",
              userSelect: "none",
              margin: 0,
            }}
          >
            Rooben
          </h1>
        </div>
        <p
          className="label-xs mt-1 animate-fade-in stagger-2"
          style={{ margin: 0 }}
        >
          Your taste is the product
        </p>
      </div>

      {/* Nav Groups */}
      <nav className="flex-1 px-2 pb-2 overflow-y-auto" role="navigation">
        {[...NAV_GROUPS, ...proNavGroups].map((group) => (
          <div key={group.label}>
            <div className="px-2 pt-4 pb-1">
              <span className="label-xs">{group.label}</span>
            </div>
            {group.items.map((item) => {
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 10px",
                    marginBottom: 2,
                    borderRadius: 6,
                    borderLeft: active
                      ? "2px solid var(--color-accent)"
                      : "2px solid transparent",
                    backgroundColor: active
                      ? "var(--color-accent-dim)"
                      : "transparent",
                    color: active
                      ? "var(--color-accent)"
                      : "var(--color-text-secondary)",
                    textDecoration: "none",
                    transition:
                      "background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease",
                    outline: "none",
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.backgroundColor =
                        "var(--color-surface-3)";
                      (e.currentTarget as HTMLAnchorElement).style.color =
                        "var(--color-text-primary)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.backgroundColor =
                        "transparent";
                      (e.currentTarget as HTMLAnchorElement).style.color =
                        "var(--color-text-secondary)";
                    }
                  }}
                  onFocus={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.outline =
                      "2px solid var(--color-accent)";
                    (e.currentTarget as HTMLAnchorElement).style.outlineOffset = "2px";
                  }}
                  onBlur={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.outline = "none";
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 26,
                      height: 26,
                      borderRadius: 6,
                      border: active
                        ? "1px solid rgba(20, 184, 166, 0.3)"
                        : "1px solid var(--color-border)",
                      backgroundColor: active
                        ? "rgba(20, 184, 166, 0.08)"
                        : "var(--color-surface-2)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      fontWeight: 600,
                      color: active
                        ? "var(--color-accent)"
                        : "var(--color-text-muted)",
                      flexShrink: 0,
                      transition: "all 0.15s ease",
                    }}
                  >
                    {item.icon}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: 13,
                      fontWeight: active ? 600 : 400,
                      letterSpacing: "0.01em",
                      lineHeight: 1.2,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      flex: 1,
                    }}
                  >
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div
        style={{
          borderTop: "1px solid var(--color-border)",
          padding: "10px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
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
          v1.0.0
        </span>
        <ThemeToggle />
      </div>
    </aside>
  );
}
