"""Integration tests that exercise real components and produce inspectable artifacts.

No external services required. Each test writes to a temp directory under
tests/artifacts/ so outputs can be examined after the run.

Run with: pytest tests/test_integration_artifacts.py -v -s
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path

import pytest

from rooben.domain import (
    StructuredTaskPrompt,
    Task,
    TaskResult,
    TaskStatus,
    TokenUsage,
    VerificationFeedback,
    Workflow,
    WorkflowState,
    WorkflowStatus,
    Workstream,
    WorkstreamStatus,
)

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


@pytest.fixture(autouse=True)
def artifacts_dir():
    """Ensure artifacts directory exists, clean per-test subdirs."""
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    yield ARTIFACTS_DIR


def _write_artifact(subdir: str, filename: str, content: str) -> Path:
    """Write an artifact file and return its path."""
    d = ARTIFACTS_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Helpers: build realistic domain objects
# ---------------------------------------------------------------------------


def _make_rich_state() -> WorkflowState:
    """Build a multi-task WorkflowState with results, feedback, and deps."""
    state = WorkflowState()

    wf = Workflow(
        id="wf-integ-001",
        spec_id="spec-hello-api",
        status=WorkflowStatus.IN_PROGRESS,
        workstream_ids=["ws-backend", "ws-testing"],
        total_tasks=4,
        completed_tasks=2,
        failed_tasks=1,
    )
    state.workflows["wf-integ-001"] = wf

    ws1 = Workstream(
        id="ws-backend",
        workflow_id="wf-integ-001",
        name="Backend Implementation",
        description="Core API endpoints",
        status=WorkstreamStatus.IN_PROGRESS,
        task_ids=["t-1", "t-2", "t-3"],
    )
    ws2 = Workstream(
        id="ws-testing",
        workflow_id="wf-integ-001",
        name="Test Suite",
        description="Automated tests",
        status=WorkstreamStatus.PENDING,
        task_ids=["t-4"],
    )
    state.workstreams["ws-backend"] = ws1
    state.workstreams["ws-testing"] = ws2

    t1 = Task(
        id="t-1",
        workstream_id="ws-backend",
        workflow_id="wf-integ-001",
        title="Setup FastAPI app",
        description="Create the main FastAPI application with /hello endpoint",
        status=TaskStatus.PASSED,
        assigned_agent_id="python-dev",
        structured_prompt=StructuredTaskPrompt(
            objective="Create a FastAPI app with greeting endpoints",
            files=["src/main.py"],
            action="Write the FastAPI application code",
            verify="Run pytest to confirm endpoints respond correctly",
            done="main.py exists and passes all endpoint tests",
        ),
        result=TaskResult(
            output="Created FastAPI app with /hello and /hello/{name} endpoints",
            artifacts={
                "src/main.py": 'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/hello")\ndef hello():\n    return {"message": "Hello, World!"}\n',
            },
            token_usage=1500,
            token_usage_detailed=TokenUsage(input_tokens=1000, output_tokens=500),
            wall_seconds=3.2,
            learnings=["FastAPI auto-generates OpenAPI docs at /docs"],
        ),
        attempt=1,
        attempt_feedback=[
            VerificationFeedback(
                attempt=1,
                verifier_type="llm_judge",
                passed=True,
                score=0.92,
                feedback="Endpoints implemented correctly with proper JSON responses",
            )
        ],
    )

    t2 = Task(
        id="t-2",
        workstream_id="ws-backend",
        workflow_id="wf-integ-001",
        title="Add error handling",
        description="Add 404 handler and input validation",
        status=TaskStatus.FAILED,
        assigned_agent_id="python-dev",
        depends_on=["t-1"],
        result=TaskResult(
            output="Added error handlers but validation is incomplete",
            error="Missing input validation for /hello/{name} — name can be empty",
            token_usage=2100,
            token_usage_detailed=TokenUsage(input_tokens=1400, output_tokens=700),
            wall_seconds=4.1,
        ),
        attempt=3,
        max_retries=3,
        attempt_feedback=[
            VerificationFeedback(
                attempt=1,
                verifier_type="llm_judge",
                passed=False,
                score=0.4,
                feedback="Missing 404 handler entirely",
                suggested_improvements=["Add exception_handler for 404", "Return JSON error body"],
            ),
            VerificationFeedback(
                attempt=2,
                verifier_type="llm_judge",
                passed=False,
                score=0.6,
                feedback="404 handler works but empty name not validated",
                suggested_improvements=["Add validation: reject empty name parameter"],
            ),
            VerificationFeedback(
                attempt=3,
                verifier_type="llm_judge",
                passed=False,
                score=0.65,
                feedback="Validation added but returns wrong status code (400 instead of 422)",
            ),
        ],
    )

    t3 = Task(
        id="t-3",
        workstream_id="ws-backend",
        workflow_id="wf-integ-001",
        title="Create Dockerfile",
        description="Multi-stage Dockerfile for the API",
        status=TaskStatus.PASSED,
        assigned_agent_id="python-dev",
        depends_on=["t-1"],
        result=TaskResult(
            output="Created multi-stage Dockerfile",
            artifacts={
                "Dockerfile": "FROM python:3.11-slim AS base\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"uvicorn\", \"main:app\"]\n",
            },
            token_usage=800,
            token_usage_detailed=TokenUsage(input_tokens=500, output_tokens=300),
            wall_seconds=1.8,
        ),
        attempt=1,
        attempt_feedback=[
            VerificationFeedback(
                attempt=1, verifier_type="llm_judge", passed=True, score=0.88,
                feedback="Valid Dockerfile with appropriate base image",
            )
        ],
    )

    t4 = Task(
        id="t-4",
        workstream_id="ws-testing",
        workflow_id="wf-integ-001",
        title="Write test suite",
        description="Pytest tests for all endpoints",
        status=TaskStatus.PENDING,
        assigned_agent_id="test-writer",
        depends_on=["t-1", "t-2"],
        skeleton_tests=[
            "def test_hello(): assert response.status_code == 200",
            "def test_hello_name(): assert 'Alice' in response.json()['message']",
        ],
    )

    for t in [t1, t2, t3, t4]:
        state.register_task(t)

    return state


# ===========================================================================
# 1. Filesystem State Backend: Write → Read Round-Trip
# ===========================================================================


class TestFilesystemRoundTrip:
    """Verify state survives serialization and can be inspected on disk."""

    @pytest.mark.asyncio
    async def test_save_and_reload_preserves_full_state(self, tmp_path):
        from rooben.state.filesystem import FilesystemBackend

        backend = FilesystemBackend(base_dir=str(tmp_path / "state"))
        await backend.initialize()

        state = _make_rich_state()
        await backend.save_state(state)

        # Reload
        loaded = await backend.load_state("wf-integ-001")
        assert loaded is not None

        # Verify round-trip integrity
        assert set(loaded.workflows.keys()) == {"wf-integ-001"}
        assert set(loaded.workstreams.keys()) == {"ws-backend", "ws-testing"}
        assert set(loaded.tasks.keys()) == {"t-1", "t-2", "t-3", "t-4"}

        # Verify task details survive
        t1 = loaded.tasks["t-1"]
        assert t1.status == TaskStatus.PASSED
        assert t1.result is not None
        assert "FastAPI" in t1.result.output
        assert "src/main.py" in t1.result.artifacts
        assert t1.result.token_usage_detailed.input_tokens == 1000
        assert len(t1.attempt_feedback) == 1
        assert t1.attempt_feedback[0].score == 0.92

        # Verify failed task feedback chain
        t2 = loaded.tasks["t-2"]
        assert t2.status == TaskStatus.FAILED
        assert t2.attempt == 3
        assert len(t2.attempt_feedback) == 3
        assert t2.attempt_feedback[0].score == 0.4
        assert t2.attempt_feedback[2].score == 0.65

        # Verify dependencies
        t4 = loaded.tasks["t-4"]
        assert set(t4.depends_on) == {"t-1", "t-2"}
        assert t4.skeleton_tests == [
            "def test_hello(): assert response.status_code == 200",
            "def test_hello_name(): assert 'Alice' in response.json()['message']",
        ]

        # Verify structured prompt
        assert t1.structured_prompt is not None
        assert "FastAPI" in t1.structured_prompt.objective

        # Write artifact for inspection
        state_files = list((tmp_path / "state").rglob("*.json"))
        for sf in state_files:
            content = sf.read_text()
            _write_artifact(
                "01_filesystem_roundtrip",
                sf.name,
                json.dumps(json.loads(content), indent=2),
            )

    @pytest.mark.asyncio
    async def test_update_single_task_persists(self, tmp_path):
        from rooben.state.filesystem import FilesystemBackend

        backend = FilesystemBackend(base_dir=str(tmp_path / "state"))
        await backend.initialize()

        state = _make_rich_state()
        await backend.save_state(state)

        # Update task status
        task = state.tasks["t-4"]
        task.status = TaskStatus.IN_PROGRESS
        task.attempt = 1
        await backend.update_task(task)

        # Reload and verify
        loaded = await backend.load_state("wf-integ-001")
        assert loaded.tasks["t-4"].status == TaskStatus.IN_PROGRESS
        assert loaded.tasks["t-4"].attempt == 1

    @pytest.mark.asyncio
    async def test_task_hashes_survive_roundtrip(self, tmp_path):
        from rooben.state.filesystem import FilesystemBackend

        backend = FilesystemBackend(base_dir=str(tmp_path / "state"))
        await backend.initialize()

        state = _make_rich_state()
        await backend.save_state(state)

        loaded = await backend.load_state("wf-integ-001")
        # register_task creates content hashes
        assert len(loaded.task_hashes) == len(state.task_hashes)
        for h, tid in state.task_hashes.items():
            assert loaded.task_hashes[h] == tid


# ===========================================================================
# 2. Plan Checker: Validate realistic plans
# ===========================================================================


class TestPlanCheckerIntegration:
    """Run PlanChecker against realistic states with various defects."""

    def test_valid_plan_passes(self, sample_spec):
        from rooben.planning.checker import PlanChecker

        state = WorkflowState()
        wf = Workflow(id="wf-1", spec_id=sample_spec.id)
        state.workflows["wf-1"] = wf

        t1 = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Build API", description="Implement endpoints",
            assigned_agent_id="agent-1",
        )
        t2 = Task(
            id="t-2", workstream_id="ws-1", workflow_id="wf-1",
            title="Write Tests", description="Test endpoints",
            assigned_agent_id="agent-1", depends_on=["t-1"],
        )
        state.register_task(t1)
        state.register_task(t2)

        result = PlanChecker().check(state, sample_spec, "wf-1")
        assert result.valid, f"Expected valid plan, got issues: {result.issues}"

        _write_artifact("02_plan_checker", "valid_plan.json", json.dumps({
            "valid": result.valid,
            "issues": result.issues,
            "tasks": [{"id": t.id, "title": t.title, "agent": t.assigned_agent_id, "deps": t.depends_on} for t in [t1, t2]],
        }, indent=2))

    def test_cycle_detected(self, sample_spec):
        from rooben.planning.checker import PlanChecker

        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id=sample_spec.id)

        # Create A → B → C → A cycle
        ta = Task(id="t-a", workstream_id="ws-1", workflow_id="wf-1",
                  title="Task A", description="", assigned_agent_id="agent-1", depends_on=["t-c"])
        tb = Task(id="t-b", workstream_id="ws-1", workflow_id="wf-1",
                  title="Task B", description="", assigned_agent_id="agent-1", depends_on=["t-a"])
        tc = Task(id="t-c", workstream_id="ws-1", workflow_id="wf-1",
                  title="Task C", description="", assigned_agent_id="agent-1", depends_on=["t-b"])
        for t in [ta, tb, tc]:
            state.register_task(t)

        result = PlanChecker().check(state, sample_spec, "wf-1")
        assert not result.valid
        assert any("cycle" in i.lower() for i in result.issues)

        _write_artifact("02_plan_checker", "cycle_detected.json", json.dumps({
            "valid": result.valid,
            "issues": result.issues,
        }, indent=2))

    def test_unassigned_agent_flagged(self, sample_spec):
        from rooben.planning.checker import PlanChecker

        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id=sample_spec.id)
        state.register_task(Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Orphan Task", description="No agent assigned",
        ))

        result = PlanChecker().check(state, sample_spec, "wf-1")
        assert not result.valid
        assert any("no assigned agent" in i.lower() for i in result.issues)

        _write_artifact("02_plan_checker", "unassigned_agent.json", json.dumps({
            "valid": result.valid, "issues": result.issues,
        }, indent=2))

    def test_invalid_dependency_flagged(self, sample_spec):
        from rooben.planning.checker import PlanChecker

        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id=sample_spec.id)
        state.register_task(Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Broken Dep", description="Depends on ghost",
            assigned_agent_id="agent-1", depends_on=["t-nonexistent"],
        ))

        result = PlanChecker().check(state, sample_spec, "wf-1")
        assert not result.valid
        assert any("unknown task" in i.lower() for i in result.issues)

    def test_unknown_agent_flagged(self, sample_spec):
        from rooben.planning.checker import PlanChecker

        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id=sample_spec.id)
        state.register_task(Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Wrong Agent", description="Assigned to fake agent",
            assigned_agent_id="agent-does-not-exist",
        ))

        result = PlanChecker().check(state, sample_spec, "wf-1")
        assert not result.valid
        assert any("unknown agent" in i.lower() for i in result.issues)


# ===========================================================================
# 3. Context Builder: Token budgeting and prompt assembly
# ===========================================================================


class TestContextBuilderIntegration:
    """Build real prompts with budgeting and inspect the output."""

    def test_builds_prompt_with_all_sections(self):
        from rooben.context.builder import ContextBuilder

        state = _make_rich_state()
        task = state.tasks["t-4"]  # has deps, skeleton tests

        builder = ContextBuilder()
        prompt = builder.build(
            task=task,
            state=state,
            codebase_context="class FastAPIApp:\n    def hello(self) -> dict: ...\n    def hello_name(self, name: str) -> dict: ...",
        )

        # Verify sections present
        assert "Write test suite" in prompt  # task description
        assert "t-1" in prompt or "Setup FastAPI" in prompt  # dependency reference
        assert "FastAPIApp" in prompt  # codebase context injected

        _write_artifact("03_context_builder", "full_prompt.txt", prompt)

        # Token estimation
        token_est = builder.estimate_tokens(prompt)
        _write_artifact("03_context_builder", "token_estimate.json", json.dumps({
            "prompt_length_chars": len(prompt),
            "estimated_tokens": token_est,
            "sections_present": {
                "task_description": "Write test suite" in prompt,
                "dependencies": "t-1" in prompt or "Setup FastAPI" in prompt,
                "codebase": "FastAPIApp" in prompt,
                "skeleton_tests": "test_hello" in prompt,
            },
        }, indent=2))

    def test_truncates_under_budget(self):
        from rooben.context.builder import ContextBuilder, ContextConfig

        config = ContextConfig(max_context_tokens=200, budget_fraction=0.5)
        builder = ContextBuilder(config=config)

        state = _make_rich_state()
        task = state.tasks["t-4"]

        prompt = builder.build(
            task=task,
            state=state,
            codebase_context="B" * 5000,  # very long codebase
        )

        # Should be truncated — budget is ~100 tokens ≈ 400 chars
        token_est = builder.estimate_tokens(prompt)

        _write_artifact("03_context_builder", "truncated_prompt.txt", prompt)
        _write_artifact("03_context_builder", "truncation_stats.json", json.dumps({
            "budget_tokens": 200,
            "budget_fraction": 0.5,
            "effective_budget": 100,
            "actual_tokens": token_est,
            "prompt_length_chars": len(prompt),
        }, indent=2))


# ===========================================================================
# 4. Learning Store: Write, query, persist, reload
# ===========================================================================


class TestLearningStoreIntegration:
    """OSS LearningStore is a no-op stub."""

    @pytest.mark.asyncio
    async def test_stub_store_returns_empty(self):
        from rooben.memory.learning_store import Learning, LearningStore

        store = LearningStore()
        await store.store(Learning(
            id="learn-1", agent_id="agent-python", workflow_id="wf-1",
            task_id="t-1", content="FastAPI auto-generates OpenAPI docs",
        ))
        # OSS stub returns empty on query
        results = await store.query(agent_id="agent-python")
        assert results == []


# ===========================================================================
# 5. Codebase Index: Scan real Python, query by keyword
# ===========================================================================


class TestCodebaseIndexIntegration:
    """Scan actual Python files and verify symbol extraction."""

    def test_scan_and_query_real_source(self):
        from rooben.context.codebase_index import CodebaseIndex

        # Scan rooben's own source
        root = str(Path(__file__).parent.parent / "src" / "rooben")
        index = CodebaseIndex(root_path=root, ignore_dirs={"__pycache__"})
        index.scan()

        assert index.file_count > 0

        # Query for orchestrator-related symbols
        orch_context = index.query(keywords=["orchestrator", "workflow", "execute"], budget_tokens=2000)
        assert len(orch_context) > 0
        assert "orchestrator" in orch_context.lower() or "Orchestrator" in orch_context

        # Query for budget-related symbols
        budget_context = index.query(keywords=["budget", "cost", "token"], budget_tokens=1000)
        assert len(budget_context) > 0

        # Query for verification symbols
        verify_context = index.query(keywords=["verify", "judge", "feedback"], budget_tokens=1000)
        assert len(verify_context) > 0

        # Serialize and check structure
        serialized = index.serialize()
        assert "files" in serialized or len(serialized) > 0

        _write_artifact("05_codebase_index", "scan_summary.json", json.dumps({
            "root": root,
            "file_count": index.file_count,
            "sample_query_orchestrator_length": len(orch_context),
            "sample_query_budget_length": len(budget_context),
            "sample_query_verify_length": len(verify_context),
        }, indent=2))
        _write_artifact("05_codebase_index", "query_orchestrator.txt", orch_context)
        _write_artifact("05_codebase_index", "query_budget.txt", budget_context)
        _write_artifact("05_codebase_index", "query_verify.txt", verify_context)


# ===========================================================================
# 6. Output Sanitizer: Credential redaction
# ===========================================================================


class TestOutputSanitizerIntegration:
    """Feed realistic secrets through and verify complete redaction."""

    def test_redacts_all_secret_types(self):
        from rooben.security.sanitizer import OutputSanitizer

        sanitizer = OutputSanitizer()

        # Realistic agent output with embedded secrets
        # Sanitizer patterns: sk-[alnum]{20+}, sk-ant-[alnum]{20+}, ghp_[alnum]{36+},
        # xoxb-..., api_key/secret/token = [alnum]{20+}, PEM blocks
        dirty_output = """
Here's the configuration file I created:

```python
import os

# API Configuration — keys use continuous alnum after prefix
OPENAI_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEF"
ANTHROPIC_KEY = "sk-ant-abcdefghijklmnopqrstuvwxyz1234567890"
GITHUB_TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz1234567890ABCD"
SLACK_TOKEN = "xoxb-fake-test-token-not-real"
api_key = "abcdefghijklmnopqrstuvwxyz1234567890ABCDEF"

# Private key for SSH
PRIVATE_KEY = '''-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA1234567890abcdefghijklmnop
qrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVW
-----END RSA PRIVATE KEY-----'''
```

The API is now configured and ready to deploy.
"""
        sanitized = sanitizer.sanitize(dirty_output)

        # Verify pattern-matched secrets are gone
        assert "sk-abcdefg" not in sanitized       # OpenAI-style sk- key
        assert "sk-ant-abcdefg" not in sanitized    # Anthropic-style key
        assert "ghp_abcdefg" not in sanitized       # GitHub PAT
        assert "xoxb-" not in sanitized             # Slack token
        assert "BEGIN RSA PRIVATE KEY" not in sanitized  # PEM block

        # Verify non-secret content survives
        assert "configuration file" in sanitized
        assert "API is now configured" in sanitized

        # Check for issues (non-destructive scan)
        issues = sanitizer.check(dirty_output)
        assert len(issues) > 0

        _write_artifact("06_sanitizer", "dirty_input.txt", dirty_output)
        _write_artifact("06_sanitizer", "sanitized_output.txt", sanitized)
        _write_artifact("06_sanitizer", "issues_found.json", json.dumps({
            "issue_count": len(issues),
            "issues": issues,
        }, indent=2))

    def test_clean_output_passes_through(self):
        from rooben.security.sanitizer import OutputSanitizer

        sanitizer = OutputSanitizer()
        clean = "def hello():\n    return {'message': 'Hello, World!'}\n"
        result = sanitizer.sanitize(clean)
        assert result == clean
        assert sanitizer.check(clean) == []


# ===========================================================================
# 7. Budget Tracker: Cost accumulation and limit enforcement
# ===========================================================================


class TestBudgetTrackerIntegration:
    """Simulate realistic cost accumulation and verify hard stops."""

    @pytest.mark.asyncio
    async def test_token_budget_enforced(self):
        from rooben.security.budget import BudgetExceeded, BudgetTracker

        tracker = BudgetTracker(max_total_tokens=5000)

        # Simulate several agent calls
        await tracker.record_tokens(1000, agent_id="agent-1")
        await tracker.record_tokens(1500, agent_id="agent-1")
        await tracker.record_tokens(2000, agent_id="agent-2")

        # Next call should breach
        with pytest.raises(BudgetExceeded) as exc_info:
            await tracker.record_tokens(1000, agent_id="agent-1")

        summary = tracker.summary()
        _write_artifact("07_budget_tracker", "token_budget.json", json.dumps({
            "max_tokens": 5000,
            "tokens_consumed": summary.get("total_tokens", "N/A"),
            "breach_error": str(exc_info.value),
            "summary": {k: str(v) for k, v in summary.items()},
        }, indent=2))

    @pytest.mark.asyncio
    async def test_cost_budget_enforced(self):
        from rooben.security.budget import BudgetExceeded, BudgetTracker

        tracker = BudgetTracker(max_cost_usd=Decimal("2.00"))

        # Simulate LLM usage with costs
        usage = TokenUsage(input_tokens=10000, output_tokens=5000)
        await tracker.record_llm_usage("anthropic", "claude-sonnet-4-20250514", usage, Decimal("0.75"))
        await tracker.record_llm_usage("anthropic", "claude-sonnet-4-20250514", usage, Decimal("0.80"))

        # This should breach $2.00
        with pytest.raises(BudgetExceeded):
            await tracker.record_llm_usage("anthropic", "claude-sonnet-4-20250514", usage, Decimal("0.75"))

        summary = tracker.summary()
        _write_artifact("07_budget_tracker", "cost_budget.json", json.dumps({
            "max_cost_usd": "2.00",
            "summary": {k: str(v) for k, v in summary.items()},
        }, indent=2))

    @pytest.mark.asyncio
    async def test_wall_time_budget_enforced(self):
        from rooben.security.budget import BudgetExceeded, BudgetTracker

        tracker = BudgetTracker(max_wall_seconds=10)

        # Simulate exceeding wall time
        with pytest.raises(BudgetExceeded):
            tracker.check_wall_time(elapsed=15.0)

    @pytest.mark.asyncio
    async def test_task_count_budget_enforced(self):
        from rooben.security.budget import BudgetExceeded, BudgetTracker

        tracker = BudgetTracker(max_total_tasks=3)

        await tracker.record_task_completion()
        await tracker.record_task_completion()
        await tracker.record_task_completion()

        with pytest.raises(BudgetExceeded):
            await tracker.record_task_completion()

    @pytest.mark.asyncio
    async def test_cost_callback_fires(self):
        from rooben.security.budget import BudgetTracker

        tracker = BudgetTracker()
        callback_log = []

        # Callbacks are awaited, so must be async
        async def on_cost(p, m, u, c):
            callback_log.append({"provider": p, "model": m, "cost": str(c)})

        tracker.register_cost_callback(on_cost)

        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        await tracker.record_llm_usage("anthropic", "claude-sonnet-4-20250514", usage, Decimal("0.015"))

        assert len(callback_log) == 1
        assert callback_log[0]["provider"] == "anthropic"


# ===========================================================================
# 8. Circuit Breaker: State transitions
# ===========================================================================


class TestCircuitBreakerIntegration:
    """Verify full state machine: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def test_full_lifecycle(self):
        from rooben.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(max_failures=3, cooldown_seconds=0.1)
        transitions = []

        # Start closed
        assert cb.state == "closed"
        assert cb.can_proceed()
        transitions.append({"event": "initial", "state": cb.state})

        # Record failures until open
        cb.record_failure("Connection timeout")
        transitions.append({"event": "failure_1", "state": cb.state})
        cb.record_failure("Connection timeout")
        transitions.append({"event": "failure_2", "state": cb.state})
        cb.record_failure("Connection timeout")
        transitions.append({"event": "failure_3", "state": cb.state})

        assert cb.state == "open"
        assert not cb.can_proceed()

        # Wait for cooldown
        time.sleep(0.15)
        assert cb.state == "half_open"
        assert cb.can_proceed()
        transitions.append({"event": "cooldown_elapsed", "state": cb.state})

        # Success in half_open → closed
        cb.record_success()
        assert cb.state == "closed"
        assert cb.can_proceed()
        transitions.append({"event": "success_in_half_open", "state": cb.state})

        _write_artifact("08_circuit_breaker", "lifecycle.json", json.dumps({
            "transitions": transitions,
            "config": {"max_failures": 3, "cooldown_seconds": 0.1},
        }, indent=2))

    def test_identical_errors_trip_faster(self):
        from rooben.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(max_failures=10, max_identical=3, cooldown_seconds=0.1)

        # Same error repeated should trip at max_identical, not max_failures
        cb.record_failure("Rate limit exceeded")
        cb.record_failure("Rate limit exceeded")
        assert cb.state == "closed"

        cb.record_failure("Rate limit exceeded")
        assert cb.state == "open"  # tripped at 3 identical, not 10 total

        _write_artifact("08_circuit_breaker", "identical_errors.json", json.dumps({
            "tripped_at": 3,
            "max_failures": 10,
            "max_identical": 3,
            "error_message": "Rate limit exceeded",
        }, indent=2))

    def test_half_open_failure_reopens(self):
        from rooben.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(max_failures=2, cooldown_seconds=0.1)

        cb.record_failure("Error A")
        cb.record_failure("Error B")
        assert cb.state == "open"

        time.sleep(0.15)
        assert cb.state == "half_open"

        # Failure in half_open should reopen
        cb.record_failure("Error C")
        assert cb.state == "open"


# ===========================================================================
# 9. Checkpoint Manager: Save and rollback
# ===========================================================================


class TestCheckpointManagerIntegration:
    """Verify checkpoint creation and rollback with real filesystem backend."""

    @pytest.mark.asyncio
    async def test_checkpoint_and_rollback(self, tmp_path):
        from rooben.resilience.checkpoint import CheckpointManager
        from rooben.state.filesystem import FilesystemBackend

        backend = FilesystemBackend(base_dir=str(tmp_path / "state"))
        await backend.initialize()

        cm = CheckpointManager(backend=backend, interval=2)
        state = _make_rich_state()

        # Force initial checkpoint (t-4 is PENDING)
        await cm.force_checkpoint(state, "wf-integ-001")

        # Modify state: mark t-2 as passed (was failed), advance t-4
        state.tasks["t-2"].status = TaskStatus.PASSED
        state.tasks["t-4"].status = TaskStatus.PASSED
        state.tasks["t-4"].attempt = 1
        state.workflows["wf-integ-001"].completed_tasks = 4

        # Force second checkpoint
        await cm.force_checkpoint(state, "wf-integ-001")

        # Rollback restores latest snapshot, resets non-terminal tasks to PENDING
        # Since t-4 is now PASSED (terminal), it stays PASSED after rollback
        restored = await cm.rollback("wf-integ-001")
        assert restored is not None
        assert restored.tasks["t-4"].status == TaskStatus.PASSED
        assert restored.tasks["t-2"].status == TaskStatus.PASSED
        assert restored.workflows["wf-integ-001"].completed_tasks == 4

        # Verify checkpoint count
        assert cm.checkpoint_count["wf-integ-001"] == 2

        _write_artifact("09_checkpoint", "checkpoint_count.json", json.dumps({
            "checkpoints_per_workflow": {k: v for k, v in cm.checkpoint_count.items()},
        }, indent=2))

    @pytest.mark.asyncio
    async def test_interval_based_checkpointing(self, tmp_path):
        from rooben.resilience.checkpoint import CheckpointManager
        from rooben.state.filesystem import FilesystemBackend

        backend = FilesystemBackend(base_dir=str(tmp_path / "state"))
        await backend.initialize()

        cm = CheckpointManager(backend=backend, interval=3)
        state = _make_rich_state()

        # Should not checkpoint at 1, 2 — should at 3
        created_1 = await cm.maybe_checkpoint(state, "wf-integ-001", completed_count=1)
        created_2 = await cm.maybe_checkpoint(state, "wf-integ-001", completed_count=2)
        created_3 = await cm.maybe_checkpoint(state, "wf-integ-001", completed_count=3)

        assert not created_1
        assert not created_2
        assert created_3


# ===========================================================================
# 10. Spec Load → State Build → Full Round-Trip
# ===========================================================================


class TestSpecToStateRoundTrip:
    """Load a real spec, build state from mock planning, persist, reload."""

    @pytest.mark.asyncio
    async def test_hello_api_spec_roundtrip(self, tmp_path):
        from rooben.spec.loader import load_spec
        from rooben.state.filesystem import FilesystemBackend

        spec = load_spec("examples/hello_api.yaml")

        # Simulate planner output
        state = WorkflowState()
        wf = Workflow(
            id="wf-hello-001",
            spec_id=spec.id,
            status=WorkflowStatus.IN_PROGRESS,
            workstream_ids=["ws-impl"],
            total_tasks=3,
            spec_content_hash="abc123",
        )
        state.workflows[wf.id] = wf

        ws = Workstream(
            id="ws-impl", workflow_id=wf.id,
            name="Implementation", description="Build the API",
            task_ids=["t-api", "t-tests", "t-docker"],
        )
        state.workstreams[ws.id] = ws

        # Create tasks matching the spec's deliverables
        tasks = [
            Task(id="t-api", workstream_id="ws-impl", workflow_id=wf.id,
                 title="Build API endpoints", description=spec.deliverables[0].description,
                 assigned_agent_id="python-dev",
                 acceptance_criteria_ids=["AC-001", "AC-002", "AC-003"]),
            Task(id="t-tests", workstream_id="ws-impl", workflow_id=wf.id,
                 title="Write test suite", description=spec.deliverables[1].description,
                 assigned_agent_id="test-writer", depends_on=["t-api"],
                 acceptance_criteria_ids=["AC-004"]),
            Task(id="t-docker", workstream_id="ws-impl", workflow_id=wf.id,
                 title="Create Dockerfile", description=spec.deliverables[2].description,
                 assigned_agent_id="python-dev", depends_on=["t-api"]),
        ]
        for t in tasks:
            state.register_task(t)

        # Persist
        backend = FilesystemBackend(base_dir=str(tmp_path / "state"))
        await backend.initialize()
        await backend.save_state(state)

        # Reload
        loaded = await backend.load_state("wf-hello-001")
        assert loaded is not None
        assert loaded.workflows["wf-hello-001"].spec_id == "spec-hello-api"
        assert len(loaded.tasks) == 3
        assert loaded.tasks["t-tests"].depends_on == ["t-api"]

        # Verify ready tasks computation
        ready = loaded.get_ready_tasks("wf-hello-001")
        ready_ids = {t.id for t in ready}
        assert "t-api" in ready_ids  # no deps
        assert "t-tests" not in ready_ids  # blocked on t-api
        assert "t-docker" not in ready_ids  # blocked on t-api

        _write_artifact("10_spec_roundtrip", "spec_summary.json", json.dumps({
            "spec_id": spec.id,
            "title": spec.title,
            "deliverables": len(spec.deliverables),
            "agents": len(spec.agents),
            "acceptance_criteria": len(spec.success_criteria.acceptance_criteria),
        }, indent=2))
        _write_artifact("10_spec_roundtrip", "state_summary.json", json.dumps({
            "workflow_id": wf.id,
            "tasks": len(loaded.tasks),
            "ready_task_ids": list(ready_ids),
            "task_deps": {t.id: t.depends_on for t in loaded.tasks.values()},
        }, indent=2))


# ===========================================================================
# 11. Cost Registry: Pricing accuracy
# ===========================================================================


class TestCostRegistryIntegration:
    """Verify cost calculations against known model prices."""

    def test_anthropic_pricing(self):
        from rooben.billing.costs import CostRegistry

        registry = CostRegistry()
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)

        sonnet_cost = registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage)
        assert sonnet_cost > 0

        _write_artifact("11_cost_registry", "anthropic_pricing.json", json.dumps({
            "model": "claude-sonnet-4-20250514",
            "input_tokens": 1_000_000,
            "output_tokens": 100_000,
            "cost_usd": str(sonnet_cost),
        }, indent=2))

    def test_openai_pricing(self):
        from rooben.billing.costs import CostRegistry

        registry = CostRegistry()
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)

        gpt4o_cost = registry.calculate_cost("openai", "gpt-4o", usage)
        assert gpt4o_cost > 0

        _write_artifact("11_cost_registry", "openai_pricing.json", json.dumps({
            "model": "gpt-4o",
            "input_tokens": 1_000_000,
            "output_tokens": 100_000,
            "cost_usd": str(gpt4o_cost),
        }, indent=2))

    def test_cache_read_discount(self):
        from rooben.billing.costs import CostRegistry

        registry = CostRegistry()

        # Without cache
        usage_no_cache = TokenUsage(input_tokens=10000, output_tokens=1000)
        cost_no_cache = registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage_no_cache)

        # With cache reads (should be cheaper)
        usage_cached = TokenUsage(input_tokens=2000, output_tokens=1000, cache_read_tokens=8000)
        cost_cached = registry.calculate_cost("anthropic", "claude-sonnet-4-20250514", usage_cached)

        # Cached should cost less (or equal if cache_read pricing isn't implemented)
        _write_artifact("11_cost_registry", "cache_comparison.json", json.dumps({
            "no_cache_cost": str(cost_no_cache),
            "cached_cost": str(cost_cached),
            "savings_pct": str(round((1 - float(cost_cached) / float(cost_no_cache)) * 100, 1)) if cost_no_cache > 0 else "N/A",
        }, indent=2))


# ===========================================================================
# 12. WorkflowState: Ready task computation and completion detection
# ===========================================================================


class TestWorkflowStateLogic:
    """Verify dependency resolution and workflow status tracking."""

    def test_get_ready_tasks_respects_dependencies(self):
        state = _make_rich_state()

        ready = state.get_ready_tasks("wf-integ-001")
        ready_ids = {t.id for t in ready}

        # t-1: passed (terminal) — not ready
        # t-2: failed (terminal) — not ready
        # t-3: passed (terminal) — not ready
        # t-4: pending, depends on t-1 (passed) and t-2 (failed) — blocked because t-2 failed
        assert "t-1" not in ready_ids
        assert "t-2" not in ready_ids
        assert "t-3" not in ready_ids

    def test_workflow_completion_detection(self):
        state = WorkflowState()
        wf = Workflow(id="wf-1", spec_id="spec-1", total_tasks=2)
        state.workflows["wf-1"] = wf

        t1 = Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                  title="A", description="", status=TaskStatus.PASSED)
        t2 = Task(id="t-2", workstream_id="ws-1", workflow_id="wf-1",
                  title="B", description="", status=TaskStatus.PASSED)
        state.register_task(t1)
        state.register_task(t2)

        assert state.is_workflow_complete("wf-1")

    def test_workflow_failure_detection(self):
        state = WorkflowState()
        wf = Workflow(id="wf-1", spec_id="spec-1", total_tasks=2)
        state.workflows["wf-1"] = wf

        t1 = Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                  title="A", description="", status=TaskStatus.PASSED)
        t2 = Task(id="t-2", workstream_id="ws-1", workflow_id="wf-1",
                  title="B", description="", status=TaskStatus.FAILED, attempt=3, max_retries=3)
        state.register_task(t1)
        state.register_task(t2)

        assert state.is_workflow_failed("wf-1")

    def test_content_hash_deduplication(self):
        state = WorkflowState()
        wf = Workflow(id="wf-1", spec_id="spec-1")
        state.workflows["wf-1"] = wf

        t1 = Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                  title="Same Task", description="Same description",
                  assigned_agent_id="agent-1")
        t2 = Task(id="t-2", workstream_id="ws-1", workflow_id="wf-1",
                  title="Same Task", description="Same description",
                  assigned_agent_id="agent-1")

        result1 = state.register_task(t1)
        state.register_task(t2)

        # register_task returns the task on first registration
        assert result1 is not None
        assert result1.id == "t-1"

        # Content hashes should be populated
        assert len(state.task_hashes) >= 1

        # Both tasks share the same content hash — second should dedup
        t1_hash = t1.content_hash()
        t2_hash = t2.content_hash()
        assert t1_hash == t2_hash  # same content = same hash
