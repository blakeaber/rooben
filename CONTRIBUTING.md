# Contributing to Rooben

Thank you for your interest in contributing to Rooben! This guide covers everything you need to get started.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/rooben.git`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Run tests: `pytest tests/ --ignore=tests/e2e -v --timeout=60`
5. Verify linting: `ruff check src/ tests/`

## Architecture Overview

Rooben follows a **spec-driven orchestration** architecture. See [ARCHITECTURE.md](docs/guides/ARCHITECTURE.md) for a full system diagram and module map.

Key concepts:
- **Specification** — YAML/JSON contract defining deliverables, agents, and acceptance criteria
- **Orchestrator** — Central engine that drives plan → execute → verify → deliver
- **Agents** — Pluggable workers (LLM, MCP, HTTP, subprocess transports)
- **Verifiers** — Test runners + LLM judges that validate task output
- **Extensions** — pip-installable plugins for agents, templates, and integrations

Core source is in `src/rooben/`. The Next.js dashboard lives in `dashboard/`.

## Development

### Requirements

- Python 3.11+
- Node 20+ (for dashboard development)
- Docker (for full-stack local dev)

### Makefile Commands

```bash
make install    # Local Python + Node setup
make test       # Run tests (skip E2E)
make test-all   # Run all tests including E2E
make lint       # Check style with ruff
make fmt        # Auto-format with ruff
make dev        # Start full stack (API + Dashboard + Postgres) via Docker
make dev-api    # Just API + Postgres
make dev-dash   # Just Dashboard (assumes API running)
```

### Code Style

- **Linter/formatter**: [Ruff](https://docs.astral.sh/ruff/) — 100-char line length, Python 3.11 target
- **Type hints**: Required for all public APIs. Use `from __future__ import annotations` for forward references.
- **Models**: Use [Pydantic](https://docs.pydantic.dev/) `BaseModel` for data structures.
- **Protocols**: Use `typing.Protocol` for extension points (not ABC where possible).
- **Logging**: Use `structlog.get_logger()` with structured key-value pairs.
- **Async**: All I/O-bound code should be async. Use `asyncio.gather()` for concurrent work.

### Testing

- **Framework**: pytest with pytest-asyncio (auto mode)
- **Timeout**: Default 30s per test
- **Structure**: Tests mirror source layout in `tests/`
- **Mocking**: Use the mock providers in `tests/helpers.py` for LLM-dependent tests

```bash
# Run a specific test file
pytest tests/test_orchestrator.py -v

# Run tests matching a pattern
pytest tests/ -k "test_circuit" -v

# Skip E2E tests (requires browser)
pytest tests/ --ignore=tests/e2e -v --timeout=60
```

## Adding New Functionality

### New Agent Transport

1. Implement `AgentProtocol` from `src/rooben/agents/protocol.py`
2. Add the transport enum value to `AgentTransport` in `src/rooben/spec/models.py`
3. Register the builder in `AgentRegistry._build_agent()` (`src/rooben/agents/registry.py`)
4. Add tests in `tests/`
5. Document in `docs/guides/CUSTOM-AGENTS.md`

### New LLM Provider

1. Implement `LLMProvider` protocol from `src/rooben/planning/provider.py`
2. Add provider initialization to CLI (`src/rooben/cli.py`) and dashboard factory
3. Register pricing in `src/rooben/billing/costs.py`
4. Add tests with mock responses

### New Verifier

1. Implement `Verifier` protocol from `src/rooben/verification/verifier.py`
2. Wire into the tiered verification chain (`src/rooben/verification/tiered.py`)

### New Extension

1. Create a directory under `extensions/` (agents, templates, or integrations)
2. Add a `rooben-extension.yaml` manifest (see existing extensions for schema)
3. See `docs/guides/CUSTOM-AGENTS.md` for full packaging guide

## Pull Requests

### Before Submitting

1. Create a feature branch from `main`
2. Make your changes with clear, focused commits
3. Add tests for new functionality
4. Run the full test suite: `make test`
5. Run the linter: `make lint`
6. Format your code: `make fmt`

### PR Checklist

- [ ] Tests pass (`pytest tests/ --ignore=tests/e2e -v --timeout=60`)
- [ ] Linter passes (`ruff check src/ tests/`)
- [ ] New public APIs have type hints
- [ ] Breaking changes documented in PR description
- [ ] New features have corresponding tests

### Commit Messages

Follow conventional commits style:
- `feat: add Bedrock provider support`
- `fix: handle empty task dependencies in planner`
- `refactor: extract orchestrator finalization into _finalize_phase`
- `docs: add custom agents guide`
- `test: add circuit breaker integration test`

## Code of Conduct

Be respectful, constructive, and collaborative. We're all here to build something great.
