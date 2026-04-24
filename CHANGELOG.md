# Changelog

## [0.2.0] - 2026-04-24

Post-launch cleanup pass. OSS core is now cleanly decoupled from rooben-pro,
the dashboard runs end-to-end from a single `make demo` command with a
seeded workflow, and a six-layer test harness guarantees the README
quickstart actually works from a fresh clone.

### Changed
- **OSS / Pro boundary tightened.** All `rooben_pro` imports removed from
  the OSS core. The CLI now exposes only the `filesystem` state backend;
  persistent backends are contributed by Pro via the extension protocol.
  `rooben go` no longer advertises `--template` (a runtime stub that
  required rooben-pro). `check_spec_integrations` is OSS-native; Pro extends
  it via the extension protocol.
- **Repository hygiene.** `.DS_Store` files untracked, `.gitignore`
  strengthened with comprehensive patterns for Python, Node, test, and
  editor artifacts.
- **Docker-compose stack now includes the dashboard** — `docker compose up`
  boots postgres + mcp-gateway + api + dashboard with a shared network.
  Phase E Dockerfile bakes the internal API URL in at build time.

### Added
- **`make demo`** — one-command boot of the full stack with a seeded demo
  workflow. No API key required. Visit `http://localhost:3000/workflows/demo`
  after ~2 minutes of build + warm-up.
- **End-to-end test harness**:
  - `tests/test_readme_quickstart.py` — 14 parametrized tests that run the
    literal README commands via `sys.executable -m rooben.cli` to prove
    the quickstart works from a fresh install.
  - `tests/test_docker_compose_smoke.py` — 6 tests (marked `docker`) that
    bring the demo stack up with `--wait --build`, assert all services
    healthy, probe OpenAPI surface, and verify the dashboard proxies to
    the api service correctly.
  - `tests/e2e/test_evaluator_journey.py` — 6 agent-browser tests for the
    evaluator's first-15-minutes journey across the dashboard.
  - `dashboard/` — Vitest + React Testing Library with 31 tests across 5
    components (StatusBadge, EmptyStateCard, BudgetGauge, SetupGate, Sidebar);
    91% statement coverage on that set.
- **CI** expanded from 3 jobs to 6: `lint`, `test` (Python 3.11+3.12
  matrix), `readme-quickstart`, `dashboard-test`, `e2e-docker`, `validate`.
  All green on the v0.2.0 commit.
- **Makefile targets**: `make test-readme`, `make test-smoke`, `make
  test-e2e`, `make test-fe`, `make test-all`.

### Fixed
- CI restored to green after a period of Pro-integration-induced failures.
- `actions/checkout` and `actions/setup-python` upgraded to non-deprecated
  majors (Node 20 → 24 transition).

## [0.1.0] - 2026-03-24

### Added
- Initial Release
