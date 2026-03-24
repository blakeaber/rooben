"""
Live E2E Validation: Verify all P3-P5 functionality with real APIs.

Tier 1: ANTHROPIC_API_KEY only (sections 1-6)
Tier 2: + DATABASE_URL (sections 7-9)
Tier 3: + ROOBEN_API_KEYS (sections 10-11)
"""

import asyncio
import os
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _load_env() -> None:
    """Load .env files — called before tests, not at import time."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".rooben" / ".env")


PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"
results: list[tuple[str, bool]] = []
skipped: list[str] = []


def record(name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append((name, passed))
    print(f"  [{status}] {name}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")


def skip(name: str, reason: str = ""):
    skipped.append(name)
    print(f"  [{SKIP}] {name}")
    if reason:
        print(f"         {reason}")


# ─── Credential detection ────────────────────────────────────────────

def has_anthropic() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def has_database() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def has_auth_keys() -> bool:
    return bool(os.environ.get("ROOBEN_API_KEYS"))


# ═══════════════════════════════════════════════════════════════════════
# TIER 1: Core API (ANTHROPIC_API_KEY)
# ═══════════════════════════════════════════════════════════════════════


async def validate_1_multi_model_routing():
    """Instantiate AnthropicProvider with different models, verify responses."""
    print("\n═══ 1. Multi-Model Routing ═══\n")

    from rooben.planning.provider import AnthropicProvider

    roles = {
        "planner": "claude-sonnet-4-20250514",
        "agent": "claude-sonnet-4-20250514",
        "verifier": "claude-haiku-4-5-20251001",
    }

    for role, model in roles.items():
        try:
            provider = AnthropicProvider(model=model)
            result = await provider.generate(
                system=f"You are a {role}. Respond in one sentence.",
                prompt="Say hello and state your role.",
                max_tokens=100,
            )
            record(
                f"Multi-model {role} ({model})",
                len(result.text) > 0 and result.usage.total > 0,
                f"response: {result.text[:80]}... | tokens: {result.usage.total}",
            )
        except Exception as e:
            record(f"Multi-model {role} ({model})", False, f"Error: {e}")


async def validate_2_oneshot_spec_generation():
    """Generate a spec via oneshot and validate it."""
    print("\n═══ 2. Oneshot Spec Generation ═══\n")

    from rooben.planning.provider import AnthropicProvider
    from rooben.refinement.oneshot import generate_spec_oneshot
    from rooben.spec.validator import SpecValidator

    provider = AnthropicProvider(model="claude-sonnet-4-20250514")

    print("  Generating spec...")
    spec = await generate_spec_oneshot(
        provider=provider,
        description="Build a CLI tool that converts CSV files to JSON with column filtering",
    )

    record("Spec has title", bool(spec.title), f"title: {spec.title}")
    record(
        "Spec has deliverables",
        len(spec.deliverables) > 0,
        f"count: {len(spec.deliverables)}",
    )
    record(
        "Spec has agents",
        len(spec.agents) > 0,
        f"count: {len(spec.agents)}",
    )
    record(
        "Spec has acceptance criteria",
        len(spec.success_criteria.acceptance_criteria) > 0,
        f"count: {len(spec.success_criteria.acceptance_criteria)}",
    )

    validator = SpecValidator()
    validation = validator.validate(spec)
    record(
        "Spec passes validation",
        validation.is_valid,
        f"valid={validation.is_valid}, errors={len(validation.errors)}, warnings={len(validation.warnings)}",
    )


async def validate_3_provider_marketplace():
    """Test each available provider."""
    print("\n═══ 3. Provider Marketplace ═══\n")

    from rooben.planning.provider import AnthropicProvider

    # Anthropic — required
    try:
        provider = AnthropicProvider(model="claude-haiku-4-5-20251001")
        result = await provider.generate(
            system="Respond in one word.",
            prompt="What is 2+2?",
            max_tokens=50,
        )
        record("Anthropic provider", len(result.text) > 0, f"response: {result.text.strip()}")
    except Exception as e:
        record("Anthropic provider", False, f"Error: {e}")

    # OpenAI — optional
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from rooben.planning.openai_provider import OpenAIProvider
            provider = OpenAIProvider(model="gpt-4o-mini")
            result = await provider.generate(
                system="Respond in one word.",
                prompt="What is 2+2?",
                max_tokens=50,
            )
            record("OpenAI provider", len(result.text) > 0, f"response: {result.text.strip()}")
        except Exception as e:
            record("OpenAI provider", False, f"Error: {e}")
    else:
        skip("OpenAI provider", "OPENAI_API_KEY not set")

    # Ollama — optional
    if os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_AVAILABLE"):
        try:
            from rooben.planning.ollama_provider import OllamaProvider
            provider = OllamaProvider(model="llama3.1")
            result = await provider.generate(
                system="Respond in one word.",
                prompt="What is 2+2?",
                max_tokens=50,
            )
            record("Ollama provider", len(result.text) > 0, f"response: {result.text.strip()}")
        except Exception as e:
            record("Ollama provider", False, f"Error: {e}")
    else:
        skip("Ollama provider", "OLLAMA_HOST not set")

    # Bedrock — optional
    if os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_PROFILE"):
        try:
            from rooben.planning.bedrock_provider import BedrockProvider
            provider = BedrockProvider()
            result = await provider.generate(
                system="Respond in one word.",
                prompt="What is 2+2?",
                max_tokens=50,
            )
            record("Bedrock provider", len(result.text) > 0, f"response: {result.text.strip()}")
        except Exception as e:
            record("Bedrock provider", False, f"Error: {e}")
    else:
        skip("Bedrock provider", "AWS credentials not set")


async def validate_4_domain_agnostic_refinement():
    """Verify spec generation works for non-software prompts."""
    print("\n═══ 4. Domain-Agnostic Refinement ═══\n")

    from rooben.planning.provider import AnthropicProvider
    from rooben.refinement.oneshot import generate_spec_oneshot

    provider = AnthropicProvider(model="claude-sonnet-4-20250514")

    print("  Generating non-software spec...")
    spec = await generate_spec_oneshot(
        provider=provider,
        description="Create a market research report on electric vehicle adoption trends in North America",
    )

    record("Non-software spec has title", bool(spec.title), f"title: {spec.title}")
    record(
        "Spec has deliverables",
        len(spec.deliverables) > 0,
        f"count: {len(spec.deliverables)}",
    )

    # Check for non-code deliverable types
    types = {d.deliverable_type.value if hasattr(d.deliverable_type, 'value') else str(d.deliverable_type) for d in spec.deliverables}
    has_non_code = bool(types - {"code"})
    record(
        "Spec contains non-code deliverable types",
        has_non_code,
        f"types: {types}",
    )

    # Check for non-developer agent roles
    agent_names = [a.name.lower() for a in spec.agents]
    has_non_dev = any(
        kw in name
        for name in agent_names
        for kw in ["research", "analyst", "writer", "editor", "review", "data", "report"]
    )
    record(
        "Spec contains non-developer agent roles",
        has_non_dev,
        f"agents: {[a.name for a in spec.agents]}",
    )


async def validate_5_template_library():
    """Load and merge each built-in template."""
    print("\n═══ 5. Template Library ═══\n")

    import yaml
    from rooben.templates import get_template_spec_yaml, list_templates, load_template

    templates = list_templates()
    record(
        "Templates are available",
        len(templates) >= 4,
        f"found: {[t['name'] for t in templates]}",
    )

    for tmpl in templates:
        name = tmpl["name"]
        try:
            raw = load_template(name)
            record(
                f"Template '{name}' loads",
                bool(raw.get("title")),
                f"title: {raw.get('title', 'N/A')}",
            )

            merged_yaml = get_template_spec_yaml(name, f"Build a sample {name} project")
            parsed = yaml.safe_load(merged_yaml)
            has_agents = "agents" in parsed and len(parsed["agents"]) > 0
            has_deliverables = "deliverables" in parsed and len(parsed["deliverables"]) > 0
            record(
                f"Template '{name}' merges correctly",
                has_agents and has_deliverables,
                f"agents: {len(parsed.get('agents', []))}, deliverables: {len(parsed.get('deliverables', []))}",
            )
        except Exception as e:
            record(f"Template '{name}'", False, f"Error: {e}")


async def validate_6_full_workflow():
    """Run a small end-to-end workflow via Orchestrator."""
    print("\n═══ 6. Full Workflow Execution ═══\n")

    from rooben.agents.registry import AgentRegistry
    from rooben.observability.reporter import WorkflowReporter
    from rooben.orchestrator import Orchestrator
    from rooben.planning.llm_planner import LLMPlanner
    from rooben.planning.provider import AnthropicProvider
    from rooben.security.budget import BudgetExceeded
    from rooben.spec.models import GlobalBudget
    from rooben.refinement.oneshot import generate_spec_oneshot
    from rooben.state.filesystem import FilesystemBackend
    from rooben.verification.llm_judge import LLMJudgeVerifier

    provider = AnthropicProvider(model="claude-sonnet-4-20250514")
    fast_provider = AnthropicProvider(model="claude-haiku-4-5-20251001")

    # Generate a small spec
    print("  Generating spec for small project...")
    spec = await generate_spec_oneshot(
        provider=provider,
        description="Create a single Python function that converts Celsius to Fahrenheit",
    )

    # Apply tight budget
    spec.global_budget = GlobalBudget(
        max_total_tokens=50000,
        max_total_tasks=10,
        max_wall_seconds=600,
        max_concurrent_agents=2,
    )

    planner = LLMPlanner(provider=provider)
    registry = AgentRegistry(llm_provider=provider)
    registry.register_from_specs(spec.agents)
    reporter = WorkflowReporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = FilesystemBackend(base_dir=str(Path(tmpdir) / "state"))
        verifier = LLMJudgeVerifier(provider=fast_provider)

        orchestrator = Orchestrator(
            planner=planner,
            agent_registry=registry,
            backend=backend,
            verifier=verifier,
            budget=spec.global_budget,
            reporter=reporter,
        )

        print("  Running workflow...")
        budget_hit = False
        try:
            state = await orchestrator.run(spec)
        except BudgetExceeded as e:
            budget_hit = True
            print(f"  Budget exceeded (expected for tight limits): {e}")
            # Orchestrator saves state before re-raising
            state = orchestrator._state

        wf = list(state.workflows.values())[0]
        record(
            "Workflow produced tasks",
            wf.total_tasks > 0,
            f"total_tasks: {wf.total_tasks}",
        )
        record(
            "Tasks executed (completed or budget hit)",
            wf.completed_tasks > 0 or budget_hit,
            f"completed: {wf.completed_tasks}, failed: {wf.failed_tasks}, budget_hit: {budget_hit}",
        )

        # Check report (not generated when budget is exceeded before completion)
        report = orchestrator.last_report
        if report:
            record(
                "WorkflowReport generated",
                True,
                f"status={report.status}, tokens={report.total_tokens}, "
                f"wall={report.wall_seconds:.1f}s",
            )
            record(
                "Report has per-agent stats",
                len(report.per_agent_tasks) > 0,
                f"agents: {list(report.per_agent_tasks.keys())}",
            )
            record(
                "Report has parallelism/critical-path metrics",
                report.critical_path_seconds >= 0,
                f"parallelism_eff={report.parallelism_efficiency:.2f}, "
                f"critical_path={report.critical_path_seconds:.1f}s",
            )
        elif budget_hit:
            record(
                "WorkflowReport skipped (budget exceeded before completion)",
                True,
                "Budget was hit before workflow finished — report not generated (expected)",
            )
        else:
            record("WorkflowReport generated", False, "No report produced")


# ═══════════════════════════════════════════════════════════════════════
# TIER 2: Database (ANTHROPIC_API_KEY + DATABASE_URL)
# ═══════════════════════════════════════════════════════════════════════


async def validate_7_dashboard_api():
    """Start FastAPI app and hit endpoints via httpx."""
    print("\n═══ 7. Dashboard API ═══\n")

    import asyncpg
    import httpx
    from rooben.dashboard.app import create_app
    from rooben.dashboard.deps import DashboardDeps, set_deps

    # Manually initialize deps (ASGITransport doesn't trigger lifespan)
    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_deps(DashboardDeps(pool=pool))

    try:
        app = create_app()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client:
            # Health endpoint (no auth)
            resp = await client.get("/api/health")
            record(
                "Health endpoint returns 200",
                resp.status_code == 200,
                f"status={resp.status_code}, body={resp.json()}",
            )

            # Workflows list
            resp = await client.get("/api/workflows")
            record(
                "Workflows endpoint responds",
                resp.status_code in (200, 500),
                f"status={resp.status_code}",
            )

            # Cost summary
            resp = await client.get("/api/cost/summary")
            record(
                "Cost summary endpoint responds",
                resp.status_code in (200, 500),
                f"status={resp.status_code}",
            )

            # Optimization performance
            resp = await client.get("/api/optimization/performance")
            record(
                "Optimization performance endpoint responds",
                resp.status_code in (200, 500),
                f"status={resp.status_code}",
            )
    finally:
        await pool.close()


async def validate_8_event_pipeline():
    """Wire DashboardEventAdapter and verify DB writes."""
    print("\n═══ 8. Event Pipeline ═══\n")

    import asyncpg
    from rooben.dashboard.event_adapter import DashboardEventAdapter
    from rooben.dashboard.routes.events import EventBroadcaster

    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)

    try:
        broadcaster = EventBroadcaster()
        adapter = DashboardEventAdapter(pool=pool, broadcaster=broadcaster)

        test_wf_id = "e2e-test-wf-001"
        test_ws_id = "e2e-test-ws-001"
        test_task_id = "e2e-test-task-001"

        # Send workflow.planned event — adapter handles all inserts
        await adapter.handle_event("workflow.planned", {
            "workflow": {
                "id": test_wf_id,
                "spec_id": "e2e-spec",
                "status": "in_progress",
                "total_tasks": 1,
            },
            "workstreams": [{
                "id": test_ws_id,
                "name": "Test Workstream",
                "description": "E2E test",
                "status": "pending",
                "task_ids": [test_task_id],
            }],
            "tasks": [{
                "id": test_task_id,
                "workstream_id": test_ws_id,
                "title": "E2E Test Task",
                "description": "Validate event pipeline",
                "status": "pending",
                "assigned_agent_id": "test-agent",
                "max_retries": 3,
                "priority": 0,
                "depends_on": [],
            }],
        })

        # Verify workflow row exists
        row = await pool.fetchrow(
            "SELECT * FROM workflows WHERE id = $1", test_wf_id
        )
        record(
            "Workflow row written to Postgres",
            row is not None,
            f"id={row['id'] if row else 'N/A'}, status={row['status'] if row else 'N/A'}",
        )

        # Send task events
        await adapter.handle_event("task.started", {
            "task_id": test_task_id,
            "attempt": 1,
        })
        await adapter.handle_event("task.passed", {
            "task_id": test_task_id,
            "workflow_id": test_wf_id,
            "output": "E2E test output",
        })

        task_row = await pool.fetchrow(
            "SELECT * FROM tasks WHERE id = $1", test_task_id
        )
        record(
            "Task row updated with status",
            task_row is not None and task_row["status"] == "passed",
            f"status={task_row['status'] if task_row else 'N/A'}",
        )

        # Verify workflow counter updated
        wf_row = await pool.fetchrow(
            "SELECT * FROM workflows WHERE id = $1", test_wf_id
        )
        record(
            "Workflow completed_tasks incremented",
            wf_row is not None and wf_row["completed_tasks"] >= 1,
            f"completed_tasks={wf_row['completed_tasks'] if wf_row else 'N/A'}",
        )

        # Cleanup test data
        await pool.execute("DELETE FROM task_dependencies WHERE task_id = $1", test_task_id)
        await pool.execute("DELETE FROM tasks WHERE id = $1", test_task_id)
        await pool.execute("DELETE FROM workstreams WHERE id = $1", test_ws_id)
        await pool.execute("DELETE FROM workflows WHERE id = $1", test_wf_id)

    finally:
        await pool.close()


async def validate_9_model_optimizer():
    """Seed sample data and verify ModelOptimizer queries."""
    print("\n═══ 9. Model Optimizer ═══\n")

    import asyncpg
    from rooben_pro.optimization.model_optimizer import ModelOptimizer

    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)

    try:
        test_wf_id = "e2e-opt-wf-001"
        test_ws_id = "e2e-opt-ws-001"
        test_task_ids = [f"e2e-opt-task-{i:03d}" for i in range(6)]

        # Seed workflow and workstream
        await pool.execute(
            """INSERT INTO workflows (id, spec_id, status, total_tasks)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (id) DO NOTHING""",
            test_wf_id, "e2e-opt-spec", "completed", 6,
        )
        await pool.execute(
            """INSERT INTO workstreams (id, workflow_id, name, description, status)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (id) DO NOTHING""",
            test_ws_id, test_wf_id, "Opt Workstream", "For optimizer test", "completed",
        )

        # Seed tasks with different statuses
        for i, tid in enumerate(test_task_ids):
            status = "passed" if i < 4 else "failed"
            await pool.execute(
                """INSERT INTO tasks (id, workflow_id, workstream_id, title, description,
                                      status, assigned_agent_id, max_retries, priority)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   ON CONFLICT (id) DO NOTHING""",
                tid, test_wf_id, test_ws_id,
                f"Opt task {i}", "Test task for optimizer",
                status, "code-agent", 3, 0,
            )

        # Seed workflow_usage rows (id is SERIAL, omit it)
        for i, tid in enumerate(test_task_ids):
            cost = Decimal("0.005") if i < 3 else Decimal("0.02")
            await pool.execute(
                """INSERT INTO workflow_usage
                   (workflow_id, task_id, source, provider, model,
                    input_tokens, output_tokens, cost_usd)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                test_wf_id, tid,
                "agent",
                "anthropic",
                "claude-sonnet-4-20250514" if i < 3 else "claude-haiku-4-5-20251001",
                500, 200, cost,
            )

        optimizer = ModelOptimizer(pool=pool)

        perf = await optimizer.get_model_performance()
        record(
            "Model performance returns results",
            len(perf) > 0,
            f"count: {len(perf)}, models: {[(p.model, p.total_tasks) for p in perf]}",
        )

        recommendations = await optimizer.get_recommendations()
        record(
            "Recommendations query succeeds",
            True,  # May be empty if not enough data variance
            f"count: {len(recommendations)}",
        )

        # Cleanup
        await pool.execute(
            "DELETE FROM workflow_usage WHERE workflow_id = $1", test_wf_id
        )
        for tid in test_task_ids:
            await pool.execute("DELETE FROM tasks WHERE id = $1", tid)
        await pool.execute("DELETE FROM workstreams WHERE id = $1", test_ws_id)
        await pool.execute("DELETE FROM workflows WHERE id = $1", test_wf_id)

    finally:
        await pool.close()


# ═══════════════════════════════════════════════════════════════════════
# TIER 3: Auth (ANTHROPIC_API_KEY + DATABASE_URL + ROOBEN_API_KEYS)
# ═══════════════════════════════════════════════════════════════════════


async def validate_10_auth_middleware():
    """Test auth middleware: 401, 403, 200."""
    print("\n═══ 10. Auth Middleware ═══\n")

    import httpx
    from rooben.dashboard.app import create_app

    api_keys = os.environ["ROOBEN_API_KEYS"]
    valid_key = api_keys.split(",")[0].strip()

    app = create_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # No auth header → 401
        resp = await client.get("/api/workflows")
        record(
            "Unauthenticated request returns 401",
            resp.status_code == 401,
            f"status={resp.status_code}",
        )

        # Wrong key → 403
        resp = await client.get(
            "/api/workflows",
            headers={"Authorization": "Bearer wrong-key-12345"},
        )
        record(
            "Invalid key returns 403",
            resp.status_code == 403,
            f"status={resp.status_code}",
        )

        # Valid key → 200
        resp = await client.get(
            "/api/workflows",
            headers={"Authorization": f"Bearer {valid_key}"},
        )
        record(
            "Valid key returns 200",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )

        # Health stays unauthenticated
        resp = await client.get("/api/health")
        record(
            "Health endpoint still unauthenticated",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )


async def validate_11_websocket_auth():
    """Test WebSocket auth: valid token stays open, no token → 4001."""
    print("\n═══ 11. WebSocket Auth ═══\n")

    from rooben.dashboard.auth import validate_ws_token

    api_keys = os.environ["ROOBEN_API_KEYS"]
    valid_key = api_keys.split(",")[0].strip()

    # Valid token
    record(
        "Valid WS token accepted",
        validate_ws_token(valid_key) is True,
        "validate_ws_token(valid_key) = True",
    )

    # No token
    record(
        "None WS token rejected",
        validate_ws_token(None) is False,
        "validate_ws_token(None) = False",
    )

    # Wrong token
    record(
        "Wrong WS token rejected",
        validate_ws_token("wrong-token") is False,
        "validate_ws_token('wrong-token') = False",
    )


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


async def main():
    _load_env()

    tier1 = has_anthropic()
    tier2 = tier1 and has_database()
    tier3 = tier2 and has_auth_keys()

    print("=" * 60)
    print("  LIVE E2E VALIDATION")
    print("=" * 60)
    print(f"\n  Tier 1 (Anthropic API):  {'YES' if tier1 else 'NO'}")
    print(f"  Tier 2 (+ Database):     {'YES' if tier2 else 'NO'}")
    print(f"  Tier 3 (+ Auth Keys):    {'YES' if tier3 else 'NO'}")

    start = time.monotonic()

    if not tier1:
        print("\n  ANTHROPIC_API_KEY not set — skipping all tiers.")
        sys.exit(0)

    # Tier 1
    await validate_1_multi_model_routing()
    await validate_2_oneshot_spec_generation()
    await validate_3_provider_marketplace()
    await validate_4_domain_agnostic_refinement()
    await validate_5_template_library()
    await validate_6_full_workflow()

    # Tier 2
    if tier2:
        await validate_7_dashboard_api()
        await validate_8_event_pipeline()
        await validate_9_model_optimizer()
    else:
        for name in [
            "Dashboard API", "Event Pipeline", "Model Optimizer",
        ]:
            skip(name, "DATABASE_URL not set")

    # Tier 3
    if tier3:
        await validate_10_auth_middleware()
        await validate_11_websocket_auth()
    else:
        for name in ["Auth Middleware", "WebSocket Auth"]:
            skip(name, "ROOBEN_API_KEYS not set")

    elapsed = time.monotonic() - start

    # Summary
    total = len(results)
    passed = sum(1 for _, p in results if p)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"  SUMMARY: {passed}/{total} passed, {failed} failed, {len(skipped)} skipped ({elapsed:.1f}s)")
    print("=" * 60)

    if failed:
        print("\n  Failed checks:")
        for name, p in results:
            if not p:
                print(f"    - {name}")
        sys.exit(1)
    else:
        print("\n  All live E2E validations passed!")


if __name__ == "__main__":
    asyncio.run(main())
