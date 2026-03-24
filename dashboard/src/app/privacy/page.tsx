"use client";

import { useEffect } from "react";

export default function PrivacyPage() {
  useEffect(() => {
    const sidebar = document.querySelector(
      "aside[aria-label='Main navigation']"
    ) as HTMLElement;
    if (sidebar) sidebar.style.display = "none";
    const main = document.querySelector("main") as HTMLElement;
    if (main) {
      main.style.padding = "0";
      main.style.backgroundColor = "transparent";
    }
    document.body.style.backgroundColor = "#0a0e1a";
    document.body.style.color = "#f1f5f9";
    return () => {
      if (sidebar) sidebar.style.display = "";
      if (main) {
        main.style.padding = "";
        main.style.backgroundColor = "";
      }
      document.body.style.backgroundColor = "";
      document.body.style.color = "";
    };
  }, []);

  return (
    <div
      data-theme="dark"
      style={{
        backgroundColor: "#0a0e1a",
        color: "#f1f5f9",
        fontFamily: "var(--font-ui)",
        minHeight: "100vh",
        padding: "80px 24px",
      }}
    >
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <a
          href="/landing"
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 13,
            color: "#14b8a6",
            textDecoration: "none",
            display: "inline-block",
            marginBottom: 32,
          }}
        >
          &larr; Back to home
        </a>

        <h1
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: 36,
            fontWeight: 800,
            letterSpacing: "-0.02em",
            margin: "0 0 8px",
          }}
        >
          Privacy Policy
        </h1>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "#64748b",
            letterSpacing: "0.04em",
            marginBottom: 48,
          }}
        >
          Last updated: March 2026
        </p>

        <Section title="1. Introduction">
          Rooben (&ldquo;we&rdquo;, &ldquo;our&rdquo;, &ldquo;the
          Service&rdquo;) respects your privacy. This Privacy Policy explains
          how we collect, use, and protect your information when you use our
          platform.
        </Section>

        <Section title="2. Information We Collect">
          <strong>Account Information:</strong> Email address and name when you
          join the waitlist or create an account.
          <br />
          <br />
          <strong>Usage Data:</strong> Workflow metadata, task counts, and
          aggregate cost information to provide the Service and improve
          performance.
          <br />
          <br />
          <strong>API Keys:</strong> Your third-party API keys are stored
          encrypted and used only to execute workflows on your behalf. We never
          share or log the content of your API keys.
          <br />
          <br />
          <strong>Workflow Content:</strong> The descriptions and outputs of
          your workflows are processed to deliver results. Self-hosted
          instances store all data locally.
        </Section>

        <Section title="3. How We Use Your Information">
          We use your information to: (a) provide and maintain the Service;
          (b) send you important updates about your account; (c) improve
          platform performance and reliability; (d) enforce our Terms of
          Service. We do not sell your personal information.
        </Section>

        <Section title="4. Data Storage and Security">
          Data is stored in encrypted databases. API keys are encrypted at
          rest. Self-hosted users retain full control over their data. We
          implement industry-standard security measures to protect your
          information.
        </Section>

        <Section title="5. Third-Party Services">
          When executing workflows, your content is sent to the AI providers
          you configure (e.g., Anthropic, OpenAI). These providers have their
          own privacy policies. We recommend reviewing them before use.
        </Section>

        <Section title="6. Data Retention">
          Workflow data is retained as long as your account is active. You can
          delete your workflows and data at any time through the dashboard.
          Waitlist entries are retained until you request removal.
        </Section>

        <Section title="7. Cookies and Analytics">
          We use minimal, privacy-friendly analytics (Plausible) that do not
          use cookies and do not track individual users. No personal data is
          shared with analytics providers.
        </Section>

        <Section title="8. Your Rights">
          You have the right to: (a) access your personal data; (b) request
          correction of inaccurate data; (c) request deletion of your data;
          (d) export your workflow data. Contact us to exercise these rights.
        </Section>

        <Section title="9. Children&apos;s Privacy">
          The Service is not intended for users under 13 years of age. We do
          not knowingly collect information from children.
        </Section>

        <Section title="10. Changes to This Policy">
          We may update this Privacy Policy from time to time. We will notify
          you of significant changes through the Service or by email.
        </Section>

        <Section title="11. Contact">
          For privacy-related questions or requests, please open an issue on
          our GitHub repository or contact us through the platform.
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 36 }}>
      <h2
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 20,
          fontWeight: 700,
          color: "#f1f5f9",
          margin: "0 0 12px",
        }}
      >
        {title}
      </h2>
      <div
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 15,
          color: "#94a3b8",
          lineHeight: 1.7,
          margin: 0,
        }}
      >
        {children}
      </div>
    </div>
  );
}
