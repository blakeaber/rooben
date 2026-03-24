"use client";

import { useEffect } from "react";

export default function TermsPage() {
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
          Terms of Service
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

        <Section title="1. Acceptance of Terms">
          By accessing or using Rooben (&ldquo;the Service&rdquo;), you
          agree to be bound by these Terms of Service. If you do not agree, do
          not use the Service.
        </Section>

        <Section title="2. Description of Service">
          Rooben is an AI-powered workflow orchestration platform that
          enables users to describe work in plain English and have it executed
          by coordinated AI agents. The Service includes a web dashboard, CLI
          tool, and API.
        </Section>

        <Section title="3. User Accounts">
          You are responsible for maintaining the confidentiality of your API
          keys and account credentials. You agree to accept responsibility for
          all activities that occur under your account.
        </Section>

        <Section title="4. Acceptable Use">
          You agree not to use the Service to: (a) violate any applicable laws
          or regulations; (b) generate harmful, abusive, or illegal content;
          (c) attempt to bypass safety or verification mechanisms; (d) reverse
          engineer the platform beyond what is permitted by the open-source
          license.
        </Section>

        <Section title="5. API Keys and Third-Party Services">
          Rooben uses your own API keys to access third-party AI providers
          (e.g., Anthropic, OpenAI). You are solely responsible for complying
          with the terms of service of those providers and for any costs
          incurred through their APIs.
        </Section>

        <Section title="6. Cost and Billing">
          The self-hosted CLI is free and open source. The hosted platform may
          include free and paid tiers. Per-workflow budget enforcement is a
          feature of the platform but does not guarantee exact cost limits due
          to the nature of third-party API pricing.
        </Section>

        <Section title="7. Intellectual Property">
          Workflow outputs generated through the Service belong to you. The
          Rooben platform, brand, and codebase are the property of the
          Rooben team, subject to the applicable open-source license for
          the CLI.
        </Section>

        <Section title="8. Disclaimers">
          THE SERVICE IS PROVIDED &ldquo;AS IS&rdquo; WITHOUT WARRANTIES OF
          ANY KIND. AI-generated outputs may contain errors. Verification
          scores indicate confidence, not guarantees. You are responsible for
          reviewing and validating all outputs before use.
        </Section>

        <Section title="9. Limitation of Liability">
          TO THE MAXIMUM EXTENT PERMITTED BY LAW, Rooben AND ITS
          OPERATORS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL,
          CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING FROM YOUR USE OF THE
          SERVICE.
        </Section>

        <Section title="10. Changes to Terms">
          We may update these Terms from time to time. Continued use of the
          Service after changes constitutes acceptance of the revised Terms.
        </Section>

        <Section title="11. Contact">
          For questions about these Terms, please open an issue on our GitHub
          repository or contact us through the platform.
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
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 15,
          color: "#94a3b8",
          lineHeight: 1.7,
          margin: 0,
        }}
      >
        {children}
      </p>
    </div>
  );
}
