"use client";

import { useState } from "react";

type Tab = "getting-started" | "concepts" | "api";

const TABS: { id: Tab; label: string }[] = [
  { id: "getting-started", label: "Getting Started" },
  { id: "concepts", label: "Concepts" },
  { id: "api", label: "API Reference" },
];

export default function DocsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("getting-started");

  return (
    <div style={{ padding: "48px 24px", maxWidth: 860, margin: "0 auto" }}>
      <h1
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 36,
          fontWeight: 800,
          letterSpacing: "-0.02em",
          margin: "0 0 8px",
          color: "#f1f5f9",
        }}
      >
        Documentation
      </h1>
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 15,
          color: "#64748b",
          margin: "0 0 36px",
        }}
      >
        Everything you need to get started with Rooben.
      </p>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 40,
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "10px 20px",
              background: "none",
              border: "none",
              borderBottom:
                activeTab === tab.id
                  ? "2px solid #14b8a6"
                  : "2px solid transparent",
              color: activeTab === tab.id ? "#14b8a6" : "#64748b",
              fontFamily: "var(--font-ui)",
              fontSize: 14,
              fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "getting-started" && <GettingStarted />}
      {activeTab === "concepts" && <Concepts />}
      {activeTab === "api" && <ApiReference />}
    </div>
  );
}

function GettingStarted() {
  return (
    <div>
      <DocSection title="Install the CLI">
        <p>Install Rooben with pip:</p>
        <CodeBlock>pip install rooben</CodeBlock>
      </DocSection>

      <DocSection title="Initialize your project">
        <p>Run the setup wizard to configure your AI provider and API key:</p>
        <CodeBlock>rooben init</CodeBlock>
        <p>
          This creates a <code>.rooben/</code> directory with your configuration
          and validates connectivity to your chosen provider.
        </p>
      </DocSection>

      <DocSection title="Run your first workflow">
        <p>Describe what you want in plain English:</p>
        <CodeBlock>rooben go &quot;Build a REST API that manages a recipe collection with FastAPI, including tests&quot;</CodeBlock>
        <p>
          Rooben will generate a specification, decompose it into tasks, assign
          agents, execute in parallel where possible, and verify every output.
        </p>
      </DocSection>

      <DocSection title="Launch the dashboard">
        <p>Start the web dashboard for a visual workflow experience:</p>
        <CodeBlock>rooben dashboard</CodeBlock>
        <p>
          Open <code>http://localhost:8420</code> in your browser. The
          dashboard provides real-time monitoring, cost tracking, and workflow
          management.
        </p>
      </DocSection>

      <DocSection title="Set a budget">
        <p>Control costs with per-workflow budget limits:</p>
        <CodeBlock>rooben go &quot;Generate a competitive analysis report&quot; --budget 2.00</CodeBlock>
        <p>
          Agents will work within the specified budget. If the budget is
          exhausted, execution pauses and you can choose to continue or stop.
        </p>
      </DocSection>
    </div>
  );
}

function Concepts() {
  return (
    <div>
      <DocSection title="Workflows">
        <p>
          A <strong>workflow</strong> is the top-level unit of work. When you
          describe what you want, Rooben generates a structured specification
          and decomposes it into tasks organized in workstreams.
        </p>
      </DocSection>

      <DocSection title="Specifications">
        <p>
          Before execution begins, Rooben creates a <strong>spec</strong>{" "}
          &mdash; a contract that defines what will be built, acceptance
          criteria, and verification strategy. You can review and refine the
          spec before approving execution.
        </p>
      </DocSection>

      <DocSection title="Tasks and Workstreams">
        <p>
          Tasks are individual units of work assigned to agents. They are
          organized into <strong>workstreams</strong> (parallel tracks) with
          dependency ordering. Tasks that can run in parallel do so
          automatically.
        </p>
      </DocSection>

      <DocSection title="Agents">
        <p>
          Agents are the AI workers that execute tasks. Each agent has a
          specific role (coder, researcher, writer, reviewer) and can be
          configured with different models, integrations, and prompt templates.
        </p>
      </DocSection>

      <DocSection title="Verification">
        <p>
          Every task output is verified against its acceptance criteria.
          Rooben uses LLM-based judges to score outputs, and tasks that
          fail verification are automatically retried with feedback. The
          verification score tells you how confident the system is in each
          result.
        </p>
      </DocSection>

      <DocSection title="Budget Enforcement">
        <p>
          Per-workflow budgets are enforced in real time. Token usage and costs
          are tracked for every agent call. If a workflow approaches its
          budget limit, execution is paused to prevent overruns.
        </p>
      </DocSection>

    </div>
  );
}

function ApiReference() {
  return (
    <div>
      <DocSection title="Base URL">
        <p>
          The dashboard API runs at <code>http://localhost:8420</code> by
          default. All API routes are prefixed with <code>/api</code>.
        </p>
      </DocSection>

      <DocSection title="Authentication">
        <p>
          Pass your API key as a Bearer token in the Authorization header:
        </p>
        <CodeBlock>Authorization: Bearer your-api-key</CodeBlock>
      </DocSection>

      <DocSection title="POST /api/run">
        <p>Launch a new workflow from a description.</p>
        <CodeBlock>{`{
  "description": "Build a REST API with FastAPI",
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "budget": 5.00
}`}</CodeBlock>
      </DocSection>

      <DocSection title="GET /api/workflows">
        <p>
          List all workflows. Supports pagination with <code>?limit=</code>{" "}
          and <code>?offset=</code> query parameters.
        </p>
      </DocSection>

      <DocSection title="GET /api/workflows/:id">
        <p>Get workflow details including status, tasks, and cost.</p>
      </DocSection>

      <DocSection title="GET /api/workflows/:id/tasks">
        <p>List all tasks for a workflow with their statuses and outputs.</p>
      </DocSection>

      <DocSection title="GET /api/cost/workflow/:id">
        <p>
          Get detailed cost breakdown for a workflow, including per-task and
          per-agent costs.
        </p>
      </DocSection>

      <DocSection title="POST /api/refine">
        <p>Refine a specification interactively before execution.</p>
        <CodeBlock>{`{
  "description": "Build a REST API with FastAPI",
  "feedback": "Add pagination and rate limiting"
}`}</CodeBlock>
      </DocSection>

      <DocSection title="WebSocket Events">
        <p>
          Connect to <code>ws://localhost:8420/ws/events</code> for real-time
          workflow updates. Events include task status changes, cost updates,
          and verification results.
        </p>
      </DocSection>
    </div>
  );
}

function DocSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 40 }}>
      <h2
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: 22,
          fontWeight: 700,
          color: "#f1f5f9",
          margin: "0 0 12px",
          letterSpacing: "-0.01em",
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
        }}
      >
        {children}
      </div>
    </div>
  );
}

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        color: "#e2e8f0",
        backgroundColor: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 8,
        padding: "14px 18px",
        margin: "12px 0",
        overflowX: "auto",
        lineHeight: 1.6,
      }}
    >
      <code>{children}</code>
    </pre>
  );
}
