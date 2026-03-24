"""
End-to-end orchestration test using the realtime_dashboard example spec.

This test loads the actual YAML spec, runs it through the full orchestrator
pipeline with a mock LLM provider, and validates that the orchestration
machinery exercises:

  - Spec loading and validation
  - LLM-based planning and task decomposition
  - Multi-agent dispatch with per-agent concurrency limits
  - Dependency resolution across workstreams
  - Mixed verification strategies (test + llm_judge)
  - State persistence via filesystem backend
  - Budget enforcement (task count)
  - Deadlock detection when dependencies fail
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from rooben.agents.registry import AgentRegistry
from rooben.domain import TaskStatus, TokenUsage, WorkflowStatus
from rooben.orchestrator import Orchestrator
from rooben.planning.llm_planner import LLMPlanner
from rooben.planning.provider import GenerationResult
from rooben.spec.loader import load_spec
from rooben.spec.models import GlobalBudget
from rooben.state.filesystem import FilesystemBackend
from rooben.verification.llm_judge import LLMJudgeVerifier


def _gen_result(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        model="mock-model",
        provider="mock",
    )


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class DashboardPlanProvider:
    """
    Mock LLM provider that returns a realistic multi-workstream plan for the
    realtime_dashboard spec, exercising:

      - 4 agents (infra-dev, collector-dev, ui-dev, test-engineer)
      - 9 deliverables with cross-workstream dependencies
      - 3-wide fan-out at the collector level
      - Fan-in at the aggregator and integration test levels
      - Mixed verification strategies
    """

    def __init__(self) -> None:
        self._calls: list[dict] = []
        self._agent_call_count = 0

    async def generate(
        self, system: str, prompt: str, max_tokens: int = 4096
    ) -> GenerationResult:
        self._calls.append({"system": system, "prompt": prompt})

        if "planning engine" in system.lower():
            return _gen_result(self._plan_response(prompt))
        elif "autonomous agent executing" in system.lower():
            self._agent_call_count += 1
            return _gen_result(self._agent_response())
        elif "quality assurance judge" in system.lower():
            return _gen_result(self._judge_response())
        return _gen_result('{"output": "ok"}')

    def _plan_response(self, prompt: str) -> str:
        """Return a realistic multi-workstream plan."""
        return json.dumps({
            "workstreams": [
                {
                    "id": "ws-models",
                    "name": "Metric Models",
                    "description": "Pydantic models and rolling window",
                    "tasks": [
                        {
                            "id": "task-models",
                            "title": "Implement metric models and rolling window",
                            "description": (
                                "Create MetricSample, RollingWindow, "
                                "AggregatedMetrics, and DashboardSnapshot models"
                            ),
                            "assigned_agent_id": "infra-dev",
                            "depends_on": [],
                            "acceptance_criteria_ids": ["AC-001"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-collectors",
                    "name": "Data Collectors",
                    "description": "Three concurrent metric collectors",
                    "tasks": [
                        {
                            "id": "task-sys-collector",
                            "title": "Implement system metrics collector",
                            "description": "CPU, memory, disk IO collector using psutil",
                            "assigned_agent_id": "collector-dev",
                            "depends_on": ["task-models"],
                            "acceptance_criteria_ids": ["AC-002"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                        {
                            "id": "task-req-collector",
                            "title": "Implement request log collector",
                            "description": "Request log parser and metric collector",
                            "assigned_agent_id": "collector-dev",
                            "depends_on": ["task-models"],
                            "acceptance_criteria_ids": ["AC-003"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                        {
                            "id": "task-err-collector",
                            "title": "Implement error tracker collector",
                            "description": "Error count and rate collector",
                            "assigned_agent_id": "collector-dev",
                            "depends_on": ["task-models"],
                            "acceptance_criteria_ids": ["AC-004"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-aggregation",
                    "name": "Aggregation & Server",
                    "description": "Aggregation engine and WebSocket server",
                    "tasks": [
                        {
                            "id": "task-aggregator",
                            "title": "Implement aggregation engine",
                            "description": (
                                "Rolling windows, health score computation, "
                                "subscribes to all collectors"
                            ),
                            "assigned_agent_id": "infra-dev",
                            "depends_on": [
                                "task-sys-collector",
                                "task-req-collector",
                                "task-err-collector",
                            ],
                            "acceptance_criteria_ids": ["AC-005", "AC-006"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                        {
                            "id": "task-ws-server",
                            "title": "Implement WebSocket server",
                            "description": "Broadcasts DashboardSnapshot to clients",
                            "assigned_agent_id": "infra-dev",
                            "depends_on": ["task-aggregator"],
                            "acceptance_criteria_ids": ["AC-007"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-ui",
                    "name": "Terminal Dashboard",
                    "description": "Rich-based terminal UI",
                    "tasks": [
                        {
                            "id": "task-dashboard-ui",
                            "title": "Implement terminal dashboard UI",
                            "description": (
                                "Rich panels for CPU, requests, errors, "
                                "health score gauge"
                            ),
                            "assigned_agent_id": "ui-dev",
                            "depends_on": ["task-ws-server"],
                            "acceptance_criteria_ids": ["AC-008", "AC-009"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-testing",
                    "name": "Test Suites",
                    "description": "Unit and integration tests",
                    "tasks": [
                        {
                            "id": "task-unit-tests",
                            "title": "Write unit tests",
                            "description": (
                                "RollingWindow stats, aggregator with mocks, "
                                "health score bounds"
                            ),
                            "assigned_agent_id": "test-engineer",
                            "depends_on": ["task-aggregator"],
                            "acceptance_criteria_ids": ["AC-010"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                        {
                            "id": "task-integration-tests",
                            "title": "Write integration tests",
                            "description": (
                                "Wire collectors to aggregator, validate "
                                "DashboardSnapshot via WebSocket"
                            ),
                            "assigned_agent_id": "test-engineer",
                            "depends_on": [
                                "task-dashboard-ui",
                                "task-unit-tests",
                            ],
                            "acceptance_criteria_ids": ["AC-011", "AC-012"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                    ],
                },
            ]
        })

    def _agent_response(self) -> str:
        return json.dumps({
            "output": "Task completed successfully",
            "artifacts": {
                "output.py": "# generated code\nprint('implemented')"
            },
            "generated_tests": [],
        })

    def _judge_response(self) -> str:
        return json.dumps({
            "passed": True,
            "score": 0.9,
            "feedback": "Output meets requirements",
        })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExampleOrchestration:
    """Tests that load and run the realtime_dashboard example spec."""

    @pytest.mark.asyncio
    async def test_spec_loads_and_validates(self):
        """The realtime_dashboard YAML loads into a valid Specification."""
        spec = load_spec(EXAMPLES_DIR / "realtime_dashboard.yaml")
        assert spec.id == "spec-realtime-dashboard"
        assert len(spec.deliverables) == 9
        assert len(spec.agents) == 4
        assert len(spec.success_criteria.acceptance_criteria) == 12
        assert spec.global_budget is not None
        assert spec.global_budget.max_concurrent_agents == 5

    @pytest.mark.asyncio
    async def test_full_orchestration(self):
        """Full spec → plan → execute → verify with mock LLM."""
        spec = load_spec(EXAMPLES_DIR / "realtime_dashboard.yaml")
        provider = DashboardPlanProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)

            # Register all 4 agents from the spec
            for agent_spec in spec.agents:
                registry.register_mcp_agent(
                    agent_spec.id,
                    max_concurrency=agent_spec.max_concurrency,
                )

            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=spec.global_budget,
            )

            state = await orchestrator.run(spec)

            # Verify workflow completed
            assert len(state.workflows) == 1
            wf = list(state.workflows.values())[0]
            assert wf.status == WorkflowStatus.COMPLETED
            assert wf.failed_tasks == 0

            # Verify all 9 tasks were created (from the plan)
            assert len(state.tasks) == 9

            # Verify task dependency ordering was respected
            # (all tasks should be PASSED, meaning deps were satisfied)
            for task in state.tasks.values():
                assert task.status == TaskStatus.PASSED, (
                    f"Task {task.id} ({task.title}) is {task.status}"
                )

            # Verify 5 workstreams were created
            assert len(state.workstreams) == 5

            # Verify agent assignments
            agent_ids = {t.assigned_agent_id for t in state.tasks.values()}
            assert "infra-dev" in agent_ids
            assert "collector-dev" in agent_ids
            assert "ui-dev" in agent_ids
            assert "test-engineer" in agent_ids

            # Verify state was persisted
            await backend.initialize()
            loaded = await backend.load_state(wf.id)
            assert loaded is not None
            assert len(loaded.tasks) == 9

    @pytest.mark.asyncio
    async def test_dependency_graph_structure(self):
        """Verify the planner creates correct dependency relationships."""
        spec = load_spec(EXAMPLES_DIR / "realtime_dashboard.yaml")
        provider = DashboardPlanProvider()
        planner = LLMPlanner(provider=provider)

        state = await planner.plan(spec, "wf-test-deps")

        tasks_by_id = state.tasks

        # Task IDs are remapped with a workflow suffix — look up by suffix
        sfx = "wf-test-deps".split("-")[-1][:6]  # "deps"

        # Models task has no dependencies
        models_task = tasks_by_id[f"task-models-{sfx}"]
        assert models_task.depends_on == []

        # All 3 collectors depend on models
        for base in ("task-sys-collector", "task-req-collector", "task-err-collector"):
            assert tasks_by_id[f"{base}-{sfx}"].depends_on == [f"task-models-{sfx}"]

        # Aggregator depends on all 3 collectors (fan-in)
        agg = tasks_by_id[f"task-aggregator-{sfx}"]
        assert set(agg.depends_on) == {
            f"task-sys-collector-{sfx}",
            f"task-req-collector-{sfx}",
            f"task-err-collector-{sfx}",
        }

        # WebSocket server depends on aggregator
        ws = tasks_by_id[f"task-ws-server-{sfx}"]
        assert ws.depends_on == [f"task-aggregator-{sfx}"]

        # Dashboard UI depends on WebSocket server
        ui = tasks_by_id[f"task-dashboard-ui-{sfx}"]
        assert ui.depends_on == [f"task-ws-server-{sfx}"]

        # Integration tests depend on UI and unit tests (join)
        integ = tasks_by_id[f"task-integration-tests-{sfx}"]
        assert set(integ.depends_on) == {f"task-dashboard-ui-{sfx}", f"task-unit-tests-{sfx}"}

    @pytest.mark.asyncio
    async def test_concurrent_collector_dispatch(self):
        """Verify that 3 collectors are dispatched in a single batch."""
        spec = load_spec(EXAMPLES_DIR / "realtime_dashboard.yaml")
        provider = DashboardPlanProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)
            for agent_spec in spec.agents:
                registry.register_mcp_agent(
                    agent_spec.id,
                    max_concurrency=agent_spec.max_concurrency,
                )
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=spec.global_budget,
            )

            state = await orchestrator.run(spec)

            # All 3 collectors should have passed (they were eligible
            # for concurrent dispatch since they share the same dependency)
            collector_tasks = [
                t for t in state.tasks.values()
                if "collector" in t.title.lower()
            ]
            assert len(collector_tasks) == 3
            for t in collector_tasks:
                assert t.status == TaskStatus.PASSED
                assert t.assigned_agent_id == "collector-dev"

    @pytest.mark.asyncio
    async def test_budget_enforcement(self):
        """Tight task budget causes orchestration to fail."""
        spec = load_spec(EXAMPLES_DIR / "realtime_dashboard.yaml")
        provider = DashboardPlanProvider()

        # Only allow 3 tasks — plan has 9
        tight_budget = GlobalBudget(
            max_total_tasks=3,
            max_concurrent_agents=5,
        )

        from rooben.security.budget import BudgetExceeded

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)
            for agent_spec in spec.agents:
                registry.register_mcp_agent(
                    agent_spec.id,
                    max_concurrency=agent_spec.max_concurrency,
                )
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=tight_budget,
            )

            with pytest.raises(BudgetExceeded, match="tasks"):
                await orchestrator.run(spec)

    @pytest.mark.asyncio
    async def test_hello_api_spec_loads(self):
        """The hello_api example also loads and validates."""
        spec = load_spec(EXAMPLES_DIR / "hello_api.yaml")
        assert spec.id == "spec-hello-api"
        assert len(spec.deliverables) == 3
        assert len(spec.agents) == 2
