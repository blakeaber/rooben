"use client";

export interface IntegrationCheck {
  name: string;
  integration: string;
  status: "available" | "not_installed" | "credentials_expired" | "not_configured";
  connect_url: string;
  required: boolean;
}

interface IntegrationStatusBarProps {
  checks: IntegrationCheck[];
}

const STATUS_CONFIG = {
  available: {
    label: "Connected",
    color: "var(--color-accent)",
    bgColor: "rgba(13, 148, 136, 0.08)",
    borderColor: "rgba(13, 148, 136, 0.2)",
    icon: "\u2713",
  },
  not_installed: {
    label: "Not installed",
    color: "#d97706",
    bgColor: "rgba(217, 119, 6, 0.08)",
    borderColor: "rgba(217, 119, 6, 0.2)",
    icon: "!",
  },
  not_configured: {
    label: "Not configured",
    color: "#d97706",
    bgColor: "rgba(217, 119, 6, 0.08)",
    borderColor: "rgba(217, 119, 6, 0.2)",
    icon: "!",
  },
  credentials_expired: {
    label: "Credentials expired",
    color: "#dc2626",
    bgColor: "rgba(220, 38, 38, 0.08)",
    borderColor: "rgba(220, 38, 38, 0.2)",
    icon: "\u2717",
  },
};

export function IntegrationStatusBar({ checks }: IntegrationStatusBarProps) {
  if (!checks || checks.length === 0) {
    return null;
  }

  return (
    <div
      className="hud-card"
      style={{ padding: 16, marginBottom: 16 }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 12,
        }}
      >
        <span
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 24,
            height: 24,
            borderRadius: 6,
            backgroundColor: "var(--color-accent-dim)",
            border: "1px solid rgba(13, 148, 136, 0.2)",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            fontWeight: 600,
            color: "var(--color-accent)",
          }}
        >
          I
        </span>
        <span
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            fontWeight: 600,
            color: "var(--color-text-primary)",
            letterSpacing: "0.01em",
          }}
        >
          Required Integrations
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {checks.map((check) => {
          const config = STATUS_CONFIG[check.status] || STATUS_CONFIG.not_installed;
          return (
            <div
              key={check.name}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 12px",
                borderRadius: 6,
                border: `1px solid ${config.borderColor}`,
                backgroundColor: config.bgColor,
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  fontWeight: 700,
                  color: config.color,
                  width: 16,
                  textAlign: "center",
                }}
              >
                {config.icon}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--color-text-primary)",
                  flex: 1,
                }}
              >
                {check.integration}
                {check.required && (
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--color-text-muted)",
                      marginLeft: 6,
                    }}
                  >
                    required
                  </span>
                )}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: 12,
                  color: config.color,
                }}
              >
                {config.label}
              </span>
              {check.status !== "available" && check.connect_url && (
                <a
                  href={check.connect_url}
                  style={{
                    fontFamily: "var(--font-ui)",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--color-accent)",
                    textDecoration: "none",
                  }}
                >
                  {check.status === "credentials_expired" ? "Reconnect" : "Connect"}
                </a>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function hasBlockingIntegrations(checks: IntegrationCheck[]): boolean {
  return checks.some(
    (c) => c.required && c.status !== "available"
  );
}
