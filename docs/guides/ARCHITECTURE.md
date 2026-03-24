# Architecture

Target audience: developers who want to contribute to or build on Rooben.

## Overview

Rooben is a spec-driven, multi-agent orchestration framework. You describe what you want in a YAML specification (or plain English), and Rooben decomposes it into a DAG of tasks, dispatches those tasks to specialized agents running in parallel, verifies every output, tracks cost per call, and delivers the result. The core loop is: **plan → execute → verify → deliver**.

The framework is built around five `typing.Protocol` extension points. Every major subsystem (planning, agent execution, verification, state persistence, LLM access) is swappable. Rooben ships with production implementations for each protocol but third-party packages can replace any of them without touching core code.

## System Architecture

```
                         ┌──────────────────┐
                         │  Specification   │  YAML / JSON / rooben go
                         │  (spec/models)   │
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │     Planner      │  LLM-based decomposition
                         │  (planning/)     │  into workstreams + tasks
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │   Orchestrator   │  Central engine
                         │  (orchestrator)  │  Budget · Circuit breaker
                         └────────┬─────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        ┌──────────┐       ┌──────────┐       ┌──────────┐
        │ Agent A  │       │ Agent B  │       │ Agent C  │  Parallel
        │ (LLM)   │       │ (MCP)    │       │ (HTTP)   │  execution
        └────┬─────┘       └────┬─────┘       └────┬─────┘
             └───────────────────┼───────────────────┘
                                 ▼
                        ┌────────────────┐
                        │    Verifier    │  Test runner → LLM judge
                        │ (verification) │  ChainedVerifier
                        └───────┬────────┘
                                ▼
                        ┌────────────────┐
                        │  StateBackend  │  Persist → Report → Learn
                        │  (state/)      │
                        └────────────────┘
```

## Module Map

| Directory | Responsibility |
|---|---|
| `orchestrator.py` | Central execution engine. Drives the plan → execute → verify loop, enforces budgets, manages concurrency via semaphores, and emits events. |
| `spec/` | Specification schema (`Specification`, `AgentSpec`, `Deliverable`, `GlobalBudget`, etc.) and YAML/JSON loader. The input contract. |
| `planning/` | `Planner` protocol + `LLMPlanner` implementation. Decomposes a spec into `WorkflowState` with workstreams and tasks. `LLMProvider` protocol + `AnthropicProvider` live here. |
| `agents/` | `AgentProtocol` and four transport implementations: LLM, MCP, HTTP, Subprocess. Also contains `AgentRegistry`, MCP client/pool, and integration credential resolution. |
| `verification/` | `Verifier` protocol, `ChainedVerifier`, `LLMJudgeVerifier`, and test runner. Short-circuits on first failure. |
| `state/` | `StateBackend` protocol + `FilesystemBackend`. Atomic persistence of `WorkflowState`. |
| `domain.py` | Runtime state models: `WorkflowState`, `Workflow`, `Workstream`, `Task`, `TaskResult`, `TokenUsage`, `VerificationFeedback`. |
| `context/` | `ContextBuilder` — priority-ordered prompt assembly. Injects task description, dependency outputs, verification feedback from prior attempts, and codebase index results. |
| `memory/` | Learning store stub (no-op in OSS). Extension point for cross-run knowledge persistence. |
| `resilience/` | `CircuitBreaker` (three-state: closed → open → half_open) and `CheckpointManager` for periodic state snapshots. |
| `security/` | `BudgetTracker` (tokens, tasks, wall-time, concurrency), `RateLimiter`, `OutputSanitizer` (credential redaction). |
| `billing/` | `CostRegistry` — per-provider, per-model pricing. Calculates USD cost from `TokenUsage`. |
| `refinement/` | Interactive spec authoring. `rooben refine` interviews the user and builds a validated specification. |
| `extensions/` | Plugin discovery via `importlib.metadata` entry points (`rooben.extensions` group). Extension protocols for custom backends, exporters, and notifiers. |
| `dashboard/` | FastAPI backend. Routes for workflows, tasks, agents, events (WebSocket + SSE), integrations, and more. Serves a Next.js static export in production. |
| `observability/` | `WorkflowReporter` (post-run summaries) and `DiagnosticAnalyzer` (triggered when >40% of tasks fail). |
| `public_api.py` | Stable SDK surface. Re-exports all protocols, core models, and the `Orchestrator`. |
| `cli.py` | CLI interface (`rooben run`, `rooben go`, `rooben refine`, `rooben dashboard`, `rooben demo`, etc.). |

## Core Protocols

Five protocols define the extension surface. All are defined as `typing.Protocol` classes and re-exported from `src/rooben/public_api.py`.

| Protocol | File | Purpose |
|---|---|---|
| `AgentProtocol` | `agents/protocol.py` | Execute a `Task`, return a `TaskResult`. Methods: `execute(task)`, `health_check()`. |
| `Planner` | `planning/planner.py` | Decompose a `Specification` into a `WorkflowState` containing workstreams and tasks. Single method: `plan(spec, workflow_id)`. |
| `Verifier` | `verification/verifier.py` | Verify a task's output against acceptance criteria. Single method: `verify(task, result) → VerificationResult`. |
| `StateBackend` | `state/protocol.py` | Persist and load `WorkflowState`. Methods: `initialize()`, `save_state()`, `load_state()`, `update_task()`, `update_workflow()`, `close()`. |
| `LLMProvider` | `planning/provider.py` | Text generation interface. Methods: `generate(system, prompt)`, `generate_multi(system, messages)`. Returns `GenerationResult` with `TokenUsage`. |

## Data Flow

1. **Spec creation** — A `Specification` is loaded from YAML (`spec/loader.py`), generated from a sentence (`rooben go`), or built interactively (`rooben refine`). The spec declares the goal, deliverables, acceptance criteria, agent roster, constraints, and budget.

2. **Planning** — The `Orchestrator` passes the spec to the `Planner`. The `LLMPlanner` sends the spec to an LLM, which returns a structured decomposition: workstreams (logical groups like "Backend API", "Frontend UI") and tasks with dependency edges. The result is a populated `WorkflowState` containing a DAG of `Task` objects.

3. **Execution** — The orchestrator enters its main loop. On each iteration it calls `WorkflowState.get_ready_tasks()` to find tasks whose dependencies are all `PASSED`. Ready tasks are dispatched concurrently via `asyncio.gather`, each acquiring the global semaphore (max concurrent agents) and per-agent semaphore before execution. The `ContextBuilder` enriches each task's prompt with dependency outputs, prior verification feedback, and optional codebase index context.

4. **Agent execution** — The `AgentRegistry` resolves the assigned agent ID to an `AgentProtocol` implementation. The agent executes the task and returns a `TaskResult` with output text, artifacts, generated tests, and token usage. Output is run through `OutputSanitizer` to redact credentials.

5. **Verification** — The task result is passed to the `Verifier`. The `ChainedVerifier` runs verifiers in sequence (e.g., test runner then LLM judge), short-circuiting on the first failure. If verification fails and retries remain, the task returns to `PENDING` with feedback stored in `task.attempt_feedback` for the next attempt.

6. **Budget enforcement** — After every agent call, token usage is recorded in `BudgetTracker`. The orchestrator checks wall-time on every loop iteration. If any limit is exceeded, `BudgetExceeded` is raised and the workflow fails.

7. **Resilience** — The `CircuitBreaker` tracks consecutive failures and identical error signatures. When it opens, all remaining tasks are failed immediately. The `CheckpointManager` snapshots state to the backend at configurable intervals.

8. **Finalization** — When all tasks reach terminal states, the orchestrator marks the workflow completed or failed, generates a `WorkflowReport`, triggers `DiagnosticAnalyzer` if failure rate exceeds 40%, and generates a workflow report.

## Agent Transports

Defined in `spec/models.py` as `AgentTransport` enum. Each maps to an implementation in `agents/`.

| Transport | Implementation | When to use |
|---|---|---|
| **LLM** | `agents/registry.py` (inline) | Default. Claude, GPT-4o, or any `LLMProvider`. The agent sends the enriched prompt to the LLM and parses the response. Best for code generation, analysis, writing. |
| **MCP** | `agents/mcp_agent.py` | Model Context Protocol servers. The agent runs an agentic tool-use loop: LLM generates tool calls, MCP server executes them, results feed back. Use when agents need external tools (web search, file system, databases). Configured via `mcp_servers` in the agent spec. Supports `stdio` and `sse` transports. |
| **HTTP** | `agents/http_agent.py` | Delegate to any REST API. The agent POSTs the task to the configured `endpoint` and returns the response. Use for existing microservices or external APIs. |
| **Subprocess** | `agents/subprocess_agent.py` | Run a Python callable in an isolated subprocess. The `endpoint` field is a dotted path (e.g., `mypackage.tasks.run_analysis`). Use for CPU-bound work, untrusted code, or when you need process isolation. |

## Dashboard

The dashboard is a FastAPI backend (`dashboard/app.py`) with a Next.js frontend served as a static export.

**Backend** — `create_app()` registers 18+ route modules covering workflows, tasks, agents, events, scheduling, integrations, credentials, and more. On startup, the lifespan handler creates an `asyncpg` connection pool, applies SQL migrations, and populates the credential cache.

**Frontend connection** — In development, Next.js runs on `:3000` and the FastAPI backend on `:8420`, connected via CORS. In production, the Next.js static export is mounted at `/` via `StaticFiles`.

**Real-time events** — The `EventBroadcaster` (`dashboard/routes/events.py`) supports two channels:
- **WebSocket** (`/api/events/ws`) — Global broadcast. All connected clients receive every event. Used by the dashboard for live DAG monitoring.
- **SSE** (`/api/events/stream/{workflow_id}`) — Per-workflow subscription. Clients receive only events for a specific workflow.

The orchestrator emits events via its `event_callback` parameter. Event types include: `workflow.planned`, `workflow.completed`, `task.started`, `task.progress`, `task.passed`, `task.failed`, `task.cancelled`, `task.verification_failed`, `llm.usage`.

**Auth** — Route-level auth dependency resolved at request time. If `ROOBEN_API_KEYS` is set, requests must include a matching Bearer token.

## Extension System

Extensions use Python's standard `importlib.metadata` entry points (PEP 621), the same mechanism as pytest and Flask plugins.

**Discovery** — `extensions/registry.py` scans the `rooben.extensions` entry point group at first access. Each entry point must reference a callable that returns an extension object.

**Registration** — In `pyproject.toml`:
```toml
[project.entry-points."rooben.extensions"]
my_extension = "my_package:register"
```

**Extension types** — The bundled extension system supports templates (spec YAML files), integrations (MCP server configs with credential resolution), and agents (pre-configured agent specs with `rooben-extension.yaml` manifests). The orchestrator also auto-registers agents with 2+ capabilities as local extensions after successful workflows.

**Bundled extensions** — The `extensions/` directory ships with templates, integrations, and agent presets as `rooben-extension.yaml` manifests. User-installed extensions live in `.rooben/extensions/`.

## Key Design Decisions

**Protocol-based extensibility** — All major subsystems are defined as `typing.Protocol` classes, not abstract base classes. This enables structural subtyping: any class with the right method signatures satisfies the protocol without inheritance. The `public_api.py` module acts as the stable API surface; internal implementations can change freely.

**Budget enforcement** — `BudgetTracker` (`security/budget.py`) enforces four dimensions: total tokens, total tasks, wall-clock seconds, and concurrent agents. The global concurrency limit is implemented as an `asyncio.Semaphore` acquired before every agent dispatch. Per-agent semaphores provide additional per-agent concurrency control. Any limit breach raises `BudgetExceeded`, which the orchestrator catches to fail the workflow.

**Circuit breaker** — `CircuitBreaker` (`resilience/circuit_breaker.py`) uses the standard three-state pattern (closed → open → half_open). It opens on either N consecutive failures or N identical error hashes, preventing runaway costs when a systemic issue (bad API key, down service) causes repeated failures. After a cooldown period, it transitions to half_open and allows one probe request.

**Extensible memory** — The `memory/` module provides a `LearningStoreProtocol` extension point for cross-run knowledge persistence. The OSS version ships with a no-op stub; third-party packages can implement the protocol for persistent learning storage.

**Verification as first-class concern** — Every task output goes through verification before being marked complete. `ChainedVerifier` composes multiple strategies (test runner + LLM judge) in sequence, short-circuiting on first failure. Failed verification triggers retry with prior feedback injected into the prompt, giving the agent explicit instructions on what to fix.

**Spec-as-contract** — The `Specification` model separates structured fields (Pydantic-validated types, enums, constraints) from semi-structured fields (free-text markdown for LLM reasoning). This gives the planner rich context while keeping machine-readable fields deterministic. The spec's `content_hash()` enables dedup and caching of plans.

**Output sanitization** — `OutputSanitizer` (`security/sanitizer.py`) automatically redacts API keys, passwords, and tokens from all agent outputs and artifacts before they are stored or displayed. This runs on every `TaskResult` before verification.
