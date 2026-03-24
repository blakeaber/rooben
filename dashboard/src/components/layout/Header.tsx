import Link from "next/link";

interface Breadcrumb {
  label: string;
  href?: string;
}

interface HeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: Breadcrumb[];
  /** Optional right-side slot for actions, badges, or controls */
  actions?: React.ReactNode;
}

export function Header({ title, subtitle, breadcrumbs, actions }: HeaderProps) {
  return (
    <header
      className="animate-fade-in-up stagger-1 mb-6"
      role="banner"
    >
      {/* ── Breadcrumb trail ──────────────────────────────────────────────── */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav
          aria-label="Breadcrumb"
          className="mb-2 flex items-center gap-1"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          {breadcrumbs.map((bc, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && (
                <span
                  aria-hidden="true"
                  style={{ color: "var(--color-text-muted)", margin: "0 2px" }}
                >
                  /
                </span>
              )}
              {bc.href ? (
                <Link
                  href={bc.href}
                  style={{
                    color: "var(--color-text-muted)",
                    textDecoration: "none",
                    transition: "color 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.color =
                      "var(--color-accent)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.color =
                      "var(--color-text-muted)";
                  }}
                >
                  {bc.label}
                </Link>
              ) : (
                <span style={{ color: "var(--color-text-secondary)" }}>
                  {bc.label}
                </span>
              )}
            </span>
          ))}
        </nav>
      )}

      {/* ── Title row ─────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: "1.625rem",
              fontWeight: 700,
              letterSpacing: "-0.01em",
              lineHeight: 1.2,
              color: "var(--color-text-primary)",
              margin: 0,
            }}
          >
            {title}
          </h1>

          {subtitle && (
            <p
              style={{
                marginTop: 6,
                fontFamily: "var(--font-ui)",
                fontSize: 13,
                color: "var(--color-text-secondary)",
                letterSpacing: "0.01em",
              }}
            >
              {subtitle}
            </p>
          )}
        </div>

        {/* Right-side action slot */}
        {actions && (
          <div
            style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 8 }}
          >
            {actions}
          </div>
        )}
      </div>

      {/* ── Divider ───────────────────────────────────────────────────────── */}
      <div
        className="animate-fade-in stagger-3"
        style={{
          marginTop: 16,
          height: 1,
          backgroundColor: "var(--color-border)",
        }}
        aria-hidden="true"
      />
    </header>
  );
}
