# AGENTS.md — rooben (OSS)

The agent entrypoint for this repo. Read this first; it is the single source of
truth for how rooben is built and how to work in it. Deeper architecture lives in
[`docs/guides/ARCHITECTURE.md`](docs/guides/ARCHITECTURE.md).

---

## What it is

**rooben** (v0.2.1, Apache-2.0) is a **spec-driven multi-agent orchestrator**. Plain
English (or a YAML spec) → an LLM planner decomposes it into a DAG of tasks →
specialized agents (LLM / MCP / HTTP / subprocess) execute in parallel → a chained
verifier (pytest runner + LLM judge) scores every output against acceptance criteria →
budget caps (tokens / USD / wall-time) are enforced and per-call cost is tracked.

Core loop: **plan → execute → verify → deliver.** Two surfaces — a CLI and a Next.js
web dashboard. This is the open-source core that the separate `rooben-pro` extends; as
of v0.2.0 the OSS core has **no `rooben_pro` imports** (decoupled).

## Flow at a glance

```
spec (YAML or `rooben go "<sentence>"`)
   ▼  load_spec
Planner (LLM → task DAG)                         src/rooben/planning/
   ▼
Orchestrator (concurrent dispatch, dep order)    src/rooben/orchestrator.py (Orchestrator.run)
   ├─ Agents (LLM / MCP / HTTP / subprocess)     src/rooben/agents/   → mcp-gateway (Node)
   ├─ Verifier (tiered: pytest + LLM judge)      src/rooben/verification/
   └─ Budget / sanitizer / rate-limit            src/rooben/security/
   ▼
State backend: filesystem (.rooben/state, CLI default) | postgres (dashboard SoT)
```

## Module map

| Path | Role | Key files / symbols |
|---|---|---|
| `src/rooben/` | The engine. | `orchestrator.py` (`Orchestrator.run`), `domain.py` (`TaskResult`), `cli.py` (Click `main`), `config.py` (`Settings.from_env`, `get_settings`), `public_api.py` (the stable extension surface) |
| `src/rooben/planning/` | Planner + LLM providers. | `provider.py` (`LLMProvider` Protocol, `GenerationResult`), `anthropic`/`openai`/`ollama`/`bedrock` providers, `plan_judge`, `checker` |
| `src/rooben/agents/` | Agent transports (Protocols). | `protocol.py` (`AgentProtocol`), `registry.py` (`AgentRegistry`), `llm_agent`, `mcp_agent`, `mcp_client`/`mcp_pool` |
| `src/rooben/verification/` | Tiered verification. | `tiered`, `llm_judge`, `heuristic`, `test_runner` |
| `src/rooben/security/` | Guardrails. | `budget.py` (`BudgetExceeded`), `sanitizer`, `rate_limiter` |
| `src/rooben/state/` | Persistence. | `filesystem.py`, `postgres.py` (both implement the `StateBackend` Protocol) |
| `src/rooben/dashboard/` | FastAPI app *inside* the package. | `app.py` (`create_app` factory), `server.py` (`run_dashboard`), `routes/`, `extension_protocol.py` (⚠️ the rooben-pro contract) |
| `src/rooben/extensions/` | Extension machinery. | `loader.py`, `registry.py`, `installer.py`, `protocols.py` (`@runtime_checkable`) |
| `src/rooben/_demo_orchestration.py` | The zero-key CLI demo (`DemoLLMProvider`). |
| `dashboard/` (top-level) | **Next.js 15 / React 19** frontend. | `src/app/`, `components/dag/TaskDAG.tsx` (`@xyflow/react`), `components/shared/BudgetGauge.tsx`, `app/workflows/[id]/verification/page.tsx` |
| `extensions/` (top-level) | Bundled extension *content* (Tier-1 data). | `agents/`, `integrations/`, `templates/`, `_index.json` |
| `examples/` | Runnable specs + demo. | `demo_orchestration.py`, `hello_api.yaml`, `job_matcher.yaml`, `realtime_dashboard.yaml` |
| `mcp-gateway/` | Node/Express service spawning npx MCP servers. |
| `tests/` | unit + integration + `e2e/` (agent-browser) + docker smoke. |

## Conventions (match these exactly)

- **`from __future__ import annotations`** atop every module. **Absolute imports only** (`from rooben.domain import ...`).
- **Lazy-import heavy deps** (anthropic, asyncpg, mcp) *inside* functions, not at module top — `rooben/__init__.py` lazy-loads `public_api` via `__getattr__`; `AnthropicProvider.generate` imports `anthropic` at call time. Preserve this.
- **Public API contract:** extensions depend on `rooben/public_api.py`, never internals. `dashboard/extension_protocol.py` is the ⚠️ EXTENSION CONTRACT — changing those signatures breaks `rooben-pro` (gated by `tests/test_extension_protocol.py`).
- **Config:** never `os.environ.get()` ad hoc — `config.py:Settings.from_env()` → cached `get_settings()` / `reset_settings()`.
- **Result objects, not exceptions, for domain flow:** `TaskResult` (`error: str | None`), `VerificationResult`, `GenerationResult`. Exceptions reserved for hard limits: `BudgetExceeded`, `PlanningFailed`, `LLMUnavailableError`. **Never-throw loaders:** extension loading wraps each manifest `try/except → logger.warning → continue`. Transient-ness centralized in `resilience/api_retry.py:is_transient_error()`.
- **Logging:** `structlog.get_logger()` with event-name-first kwargs — `log.info("agent_registry.registered", agent_id=...)`. (`extensions/` + parts of `dashboard/` use stdlib logging — match the local file.)
- **Seams are `typing.Protocol`:** `AgentProtocol`, `LLMProvider`, `Verifier`, `StateBackend`, `Planner`. DI by constructor injection; the dashboard uses module-global singletons (`get_deps`/`set_deps`).
- **Two extension systems:** (1) entry-point plugins under group `rooben.extensions`; (2) manifest-based `rooben-extension.yaml` discovered by `loader.py` (bundled `extensions/` + user `.rooben/extensions/`).
- **Tests:** `asyncio_mode = "auto"`; `timeout = 30`; one marker `docker` (skip with `-m "not docker"`). Fixtures `mock_provider` (`MockLLMProvider`, routes by system-prompt substring) + `sample_spec` in `conftest.py`. `__test__ = False` on model classes prefixed `Test`.

## CLI / entrypoints

`pyproject.toml` installs a **`rooben`** console command (`rooben = "rooben.cli:main"`).

| Command | What it does |
|---|---|
| `rooben demo` | **Zero-key** 7-part showcase — runs the real engine with mock providers (see Demo surfaces). |
| `rooben doctor` · `rooben init` | Env health check · scaffold `.rooben/` + `.env` |
| `rooben run <spec>` | Execute a spec. Flags: `--provider {anthropic,openai,ollama,bedrock}`, `--model[-planner/-agent/-verifier]`, `--backend filesystem`, `--dry-run/--preview/--verbose` |
| `rooben go "<sentence>"` | NL → spec → run (needs a key) |
| `rooben validate <spec>` | Validate a spec (free, no key) |
| `rooben refine` / `resume` / `cancel` / `status` | Interactive spec Q&A / resume / cancel / status |
| `rooben dashboard --port 8420 [--dev]` | Launch the dashboard |
| `rooben billing estimate <provider> <model>` · `integrations list` · `extensions list` | Cost estimate · registries (free) |

**Makefile:** `make demo` (zero-key seeded dashboard), `make dev`/`up`/`down`, `make api` (`uvicorn rooben.dashboard.app:create_app --factory`), `make test` / `test-readme` / `test-smoke -m docker` / `test-e2e` / `test-fe` / `test-all`, `make lint`/`fmt` (ruff). **CI** (`.github/workflows/ci.yaml`): lint → test (3.11/3.12) + readme-quickstart + dashboard Vitest → e2e-docker smoke + validate-extensions.

## How to add X

- **An agent transport** → implement `AgentProtocol` (`agents/protocol.py`); register a builder in `agents/registry.py`.
- **An LLM provider** → implement the `LLMProvider` Protocol (`planning/provider.py`); copy `anthropic` provider (lazy-import the SDK).
- **A bundled extension** (agent/integration/template) → add content under top-level `extensions/` with a `rooben-extension.yaml` manifest; `loader.py` discovers it. Keep it depending on `public_api.py` only.
- **A dashboard page** → copy a page under `dashboard/src/app/workflows/`; data via the SSE/`useSSE` hook.

## Demo surfaces (fidelity ground truth — READ before demoing)

rooben is **unusually demo-ready**: two purpose-built **zero-API-key** paths. The
engine is REAL in both; only the LLM outputs / data are seeded for repeatability —
so for a reel these are "real software, scripted inputs," never present the stubbed
LLM as a live model call.

| Surface | Fidelity | Detail |
|---|---|---|
| `rooben demo` (`_demo_orchestration.py`, `DemoLLMProvider`) | **scripted inputs / real engine** | Runs real plan→execute→verify→budget→sanitize; LLM outputs are deterministic stubs. Demo 3 prints `Tasks: 4 passed / 4 total`; Demo 5 trips a real `BudgetExceeded`. Zero key/network, runs in seconds. Best CLI capture. |
| `make demo` → `/workflows/demo` | **scripted data / real UI** | `scripts/seed-demo.sql` seeds one completed "Books API" workflow (3 tasks, scores 0.92/0.88/0.95, ~$0.075 cost) rendered by the real dashboard: animated `TaskDAG.tsx`, `BudgetGauge.tsx`, verification inspector. No LLM calls. Best visual capture. |
| `rooben run` / `go` / `refine` | **LIVE** | Real LLM execution — needs `ANTHROPIC_API_KEY`. |
| `validate` / `doctor` / `billing estimate` / `integrations list` | **LIVE, no key** | Real, free — good supporting B-roll. |

Committed `proof-*.png` + `docs/assets/demo.gif` + `demo.tape` (VHS script) confirm these screens render.

## Docs index

[`README.md`](README.md) (mature, with GIFs + no-key quickstart) · [`docs/guides/ARCHITECTURE.md`](docs/guides/ARCHITECTURE.md) · [`docs/guides/CUSTOM-AGENTS.md`](docs/guides/CUSTOM-AGENTS.md) · [`docs/guides/HARNESS-ENGINEERING.md`](docs/guides/HARNESS-ENGINEERING.md) · [`CHANGELOG.md`](CHANGELOG.md)

<!-- agent-ready:baseline 35d80849ece9561f748779d955eba33b77e55369 2026-06-26 -->
