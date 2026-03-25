# Rooben & Harness Engineering

Target audience: anyone evaluating Rooben or trying to understand where it sits in the broader AI tooling landscape.

## What is Harness Engineering?

Harness engineering is the emerging discipline of building the **infrastructure layer that surrounds AI models** to make them effective in production. Where prompt engineering focuses on *what you say to the model*, harness engineering focuses on *everything else*: how tasks reach the model, how outputs are verified, how context is assembled, how costs are controlled, and how multiple agents coordinate.

The discipline encompasses:

| Concern | What it covers |
|---|---|
| Context management | Assembling, prioritizing, and truncating what the model sees |
| Tool integration | Connecting models to external capabilities (filesystems, APIs, databases) |
| Multi-agent orchestration | Coordinating multiple AI agents with dependencies |
| Verification & evaluation | Automated pipelines to validate AI outputs |
| Memory & knowledge | Persisting learnings across sessions and runs |
| Cost & budget control | Enforcing spending limits on token usage and dollars |
| Safety guardrails | Sandboxing, permission systems, credential redaction |
| Workflow orchestration | DAG-based execution with retry logic and resilience |
| Observability | Monitoring, logging, and real-time dashboards |

Examples in the wild include Claude Code (hooks, MCP servers, permission modes, context compression), LangChain/LangGraph, CrewAI, AutoGen, and IDE integrations like Cursor and Windsurf.

## How Rooben Maps to Harness Engineering

Every major harness engineering concern has a corresponding Rooben subsystem:

| Harness Concern | Rooben Implementation | Key Module |
|---|---|---|
| Context management | `ContextBuilder` — priority-ordered, budget-aware prompt assembly | `context/builder.py` |
| Tool integration | MCP agent transport with bundled server configs | `agents/mcp_agent.py` |
| Multi-agent orchestration | `Orchestrator` — DAG-based concurrent execution | `orchestrator.py` |
| Verification | `ChainedVerifier` — test runner + LLM judge with feedback injection | `verification/verifier.py` |
| Memory | `LearningStoreProtocol` — cross-run knowledge persistence | `memory/protocol.py` |
| Budget control | `BudgetTracker` — tokens, tasks, wall-time, concurrency, USD | `security/budget.py` |
| Safety | `OutputSanitizer` — automatic credential redaction | `security/sanitizer.py` |
| Workflow orchestration | `LLMPlanner` — spec decomposition into validated DAGs | `planning/llm_planner.py` |
| Observability | FastAPI dashboard with WebSocket/SSE real-time events | `dashboard/` |
| Extensibility | Six pluggable `typing.Protocol` interfaces | `public_api.py` |

## Similarities

**1. Context is king.** Both Rooben and harness engineering tools recognize that what reaches the model matters as much as the model itself. Rooben's `ContextBuilder` mirrors how tools like Claude Code manage context compression — prioritizing high-value information and truncating gracefully under token budgets.

**2. Tool integration as a first-class concern.** Harness engineering tools provide mechanisms for models to call external tools. Rooben does this via its MCP agent transport, supporting both stdio and SSE server connections, plus HTTP and subprocess transports for non-LLM backends.

**3. Verification loops.** Modern harness engineering emphasizes closing the feedback loop. Rooben's chained verification (test runner → LLM judge → retry with structured feedback) parallels how Claude Code uses linters, type checkers, and test runners as verification hooks.

**4. Budget and cost awareness.** Both treat token and dollar spend as something to actively manage. Rooben enforces hard limits across four dimensions; harness engineering tools track usage with configurable caps.

**5. Pluggable architecture.** Both favor composability. Rooben's six protocols (`LLMProvider`, `AgentProtocol`, `Verifier`, `Planner`, `StateBackend`, `LearningStoreProtocol`) mirror how harness engineering tools use middleware, plugins, and configuration to swap components.

**6. Resilience patterns.** Circuit breakers, retries with backoff, and checkpointing appear in both Rooben and mature harness engineering systems as essential production primitives.

## Differences

| Dimension | Harness Engineering (General) | Rooben |
|---|---|---|
| **Scope** | Often single-agent with tool access | Multi-agent by default — DAGs of coordinated agents |
| **Specification** | Implicit (code defines behavior) | Explicit spec-as-contract (YAML reviewed before execution) |
| **Verification** | External (CI, linters, manual review) | Built-in as a core primitive, mandatory for task completion |
| **Interaction model** | Interactive / conversational (chat, IDE) | Declarative / autonomous (describe → approve → watch) |
| **Planning** | Human-driven or single-step | LLM-driven decomposition with validation (`PlanChecker` + `PlanJudge`) |
| **Agent types** | Usually one transport type | Four transports (LLM, MCP, HTTP, Subprocess) in one workflow |
| **Budget enforcement** | Advisory / observational | Hard enforcement (raises exceptions, halts execution) |
| **Learning** | Session-scoped or tool-specific | Cross-run protocol with semantic query and curation |

## What is Unique About Rooben

**Spec-as-contract.** No other major framework makes the user review and approve a machine-generated execution plan — complete with agents, deliverables, acceptance criteria, and budget — before any work begins. This is transparency by design, not as an afterthought.

**Verification as a first-class primitive.** While harness engineering tools *can* verify outputs, Rooben makes verification mandatory and composable. Every task passes through a `ChainedVerifier` before being marked complete. Failed tasks receive structured feedback that gets injected into retry prompts, creating a tight improvement loop.

**Four-dimensional budget enforcement.** Tokens, tasks, wall-time, and concurrency all have hard limits with asyncio-safe enforcement. Most harness engineering tools track cost but don't enforce hard stops mid-execution.

**Heterogeneous agent transports.** A single Rooben workflow can mix pure LLM agents, MCP tool-calling agents, HTTP microservices, and subprocess workers. Most frameworks assume homogeneous agent types.

**Interactive specification refinement.** The `rooben refine` command conducts a Q&A loop to collaboratively build a specification from vague intent — a structured alternative to the free-form chat paradigm.

**Cross-domain applicability.** Unlike code-focused harness tools (Cursor, Claude Code), Rooben handles code, documents, research, data pipelines, and any deliverable type, making it a general-purpose orchestration harness.

## What Harness Engineering Covers That Rooben Does Not

**Real-time interactive collaboration.** Tools like Claude Code and Cursor provide tight human-in-the-loop interaction at every step (inline suggestions, diff views, conversational iteration). Rooben's model is more autonomous — you approve the plan, then watch it execute.

**IDE and editor integration.** Harness engineering often involves deep integration with development environments (LSP, inline completions, syntax-aware context). Rooben operates at the workflow level, not the keystroke level.

**Granular permission models.** Claude Code's per-tool, per-directory permission system is a harness engineering pattern that Rooben doesn't deeply explore. Rooben focuses on budget enforcement and credential sanitization instead.

**User-configurable hooks.** Event-driven hooks (pre-commit, post-tool-call, session-start) let users inject custom behavior into the pipeline. Rooben emits events for its dashboard but doesn't expose a user-configurable hook system.

**Dynamic context compression.** Techniques like conversation summarization and sliding-window context management for long interactive sessions. Rooben's `ContextBuilder` does priority-based truncation but doesn't implement dynamic compression for ongoing conversations.

## Summary

Rooben is a purpose-built harness engineering framework that goes deeper on orchestration, verification, and budget enforcement than most general-purpose harness engineering tools.

Where general harness engineering excels at making a *single agent* maximally effective in an interactive context (IDE integration, real-time collaboration, permission sandboxing), Rooben excels at making *multiple agents* deliver verified results autonomously within controlled budgets.

They are complementary. Harness engineering is the broader discipline; Rooben is a specific, opinionated implementation that pushes certain harness engineering patterns — verification, budgeting, spec-as-contract — further than the field's current norm.
