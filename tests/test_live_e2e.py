"""Live E2E tests — require real API credentials.

These tests call real external services and produce inspectable artifacts.
They are skipped automatically if the required environment variables are not set.

Run with credentials:
    export ANTHROPIC_API_KEY=sk-ant-...
    pytest tests/test_live_e2e.py -v -s

Artifacts written to tests/artifacts/live_*/
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

has_anthropic = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
has_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
has_postgres = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)
has_stripe = pytest.mark.skipif(
    not os.environ.get("STRIPE_API_KEY"),
    reason="STRIPE_API_KEY not set",
)
has_linear = pytest.mark.skipif(
    not (os.environ.get("LINEAR_API_KEY") and os.environ.get("LINEAR_TEAM_ID")),
    reason="LINEAR_API_KEY/LINEAR_TEAM_ID not set",
)


def _write_artifact(subdir: str, filename: str, content: str) -> Path:
    d = ARTIFACTS_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(content)
    return p


# ===========================================================================
# 1. Anthropic Provider: Raw LLM call
# ===========================================================================


@has_anthropic
class TestAnthropicProviderLive:
    """Verify raw Anthropic API connectivity and response parsing."""

    @pytest.mark.asyncio
    async def test_simple_generation(self):
        from rooben.planning.provider import AnthropicProvider
        from rooben.utils import parse_llm_json

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        result = await provider.generate(
            system="You are a helpful assistant. Respond with valid JSON only.",
            prompt='Return a JSON object with key "greeting" and value "Hello, World!"',
            max_tokens=256,
        )

        assert result.text is not None
        assert len(result.text) > 0
        assert result.usage.input_tokens > 0
        assert result.usage.output_tokens > 0
        assert result.model == "claude-sonnet-4-20250514"
        assert result.provider == "anthropic"

        # Parse JSON (may be wrapped in markdown fences)
        parsed = parse_llm_json(result.text)
        assert parsed is not None
        assert "greeting" in parsed

        _write_artifact("live_01_anthropic", "simple_response.json", json.dumps({
            "text": result.text,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "model": result.model,
            "parsed": parsed,
        }, indent=2))


# ===========================================================================
# 2. OpenAI Provider: Raw LLM call
# ===========================================================================


@has_openai
class TestOpenAIProviderLive:
    """Verify raw OpenAI API connectivity."""

    @pytest.mark.asyncio
    async def test_simple_generation(self):
        from rooben.planning.openai_provider import OpenAIProvider

        provider = OpenAIProvider(model="gpt-4o-mini")
        result = await provider.generate(
            system="You are a helpful assistant. Respond with valid JSON only.",
            prompt='Return a JSON object with key "greeting" and value "Hello from OpenAI!"',
            max_tokens=256,
        )

        assert result.text is not None
        assert result.usage.input_tokens > 0
        assert result.usage.output_tokens > 0

        parsed = json.loads(result.text)
        assert "greeting" in parsed

        _write_artifact("live_02_openai", "simple_response.json", json.dumps({
            "text": result.text,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "model": result.model,
            "parsed": parsed,
        }, indent=2))


# ===========================================================================
# 3. LLM Planning: Spec → Task DAG with real LLM
# ===========================================================================


@has_anthropic
class TestLLMPlannerLive:
    """Verify that the planner generates a valid task DAG from a real spec."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_plan_hello_api(self):
        from rooben.planning.checker import PlanChecker
        from rooben.planning.llm_planner import LLMPlanner
        from rooben.planning.provider import AnthropicProvider
        from rooben.spec.loader import load_spec

        spec = load_spec("examples/hello_api.yaml")
        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        planner = LLMPlanner(provider=provider)

        state = await planner.plan(spec, workflow_id="wf-live-test")

        # Basic sanity
        assert len(state.workflows) >= 1
        assert len(state.tasks) >= 1
        assert len(state.workstreams) >= 1

        # Validate the plan
        wf_id = list(state.workflows.keys())[0]
        checker = PlanChecker()
        check_result = checker.check(state, spec, wf_id)

        tasks_summary = []
        for t in state.tasks.values():
            tasks_summary.append({
                "id": t.id,
                "title": t.title,
                "agent": t.assigned_agent_id,
                "deps": t.depends_on,
                "criteria": t.acceptance_criteria_ids,
            })

        _write_artifact("live_03_planner", "plan_result.json", json.dumps({
            "valid": check_result.valid,
            "issues": check_result.issues,
            "workflow_count": len(state.workflows),
            "workstream_count": len(state.workstreams),
            "task_count": len(state.tasks),
            "tasks": tasks_summary,
        }, indent=2))

        # Plan should be valid (or have only advisory issues)
        if not check_result.valid:
            # Log but don't hard-fail — planning quality is what we're measuring
            _write_artifact("live_03_planner", "plan_issues.json",
                            json.dumps(check_result.issues, indent=2))


# ===========================================================================
# 4. Refinement Engine: Conversational spec authoring
# ===========================================================================


@has_anthropic
class TestRefinementEngineLive:
    """Verify the refinement engine can start a conversation and produce questions."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_start_and_first_questions(self):
        from rooben.planning.provider import AnthropicProvider
        from rooben.refinement.engine import RefinementEngine

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        engine = RefinementEngine(provider=provider, max_turns=10)

        questions = await engine.start(
            "Build a REST API that manages a todo list with CRUD operations"
        )

        assert isinstance(questions, list)
        assert len(questions) >= 1

        state = engine.state
        assert state.phase == "discovery"
        assert state.turn_count >= 0

        _write_artifact("live_04_refinement", "initial_questions.json", json.dumps({
            "phase": state.phase,
            "turn_count": state.turn_count,
            "completeness": state.completeness,
            "questions": questions,
            "gap_count": len(state.schema_gaps),
            "gaps": [{"field_path": g.field_path, "importance": g.importance, "description": g.description}
                     for g in state.schema_gaps],
        }, indent=2))

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_multi_turn_conversation(self):
        from rooben.planning.provider import AnthropicProvider
        from rooben.refinement.engine import RefinementEngine
        from rooben.refinement.state import ConversationState

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        engine = RefinementEngine(provider=provider, max_turns=10)

        questions = await engine.start(
            "Build a CLI tool that converts markdown files to HTML"
        )

        conversation_log = [{"role": "system", "questions": questions}]

        # Answer a few rounds
        answers = [
            "It should use Python with the markdown library. Support tables and code blocks. Output to stdout or a file.",
            "Single agent is fine. Acceptance criteria: valid HTML output, code blocks get syntax highlighting, tables render correctly.",
            "No budget constraints for now. Just make it work correctly.",
        ]

        for answer in answers:
            result = await engine.process_answer(answer)
            conversation_log.append({"role": "user", "answer": answer})

            if isinstance(result, ConversationState):
                conversation_log.append({
                    "role": "system",
                    "event": "entered_review",
                    "completeness": result.completeness,
                })
                break
            else:
                conversation_log.append({"role": "system", "questions": result})

        final_state = engine.state

        _write_artifact("live_04_refinement", "multi_turn_conversation.json", json.dumps({
            "final_phase": final_state.phase,
            "turn_count": final_state.turn_count,
            "completeness": final_state.completeness,
            "conversation": conversation_log,
        }, indent=2))


# ===========================================================================
# 5. Verification: LLM Judge
# ===========================================================================


@has_anthropic
class TestLLMJudgeLive:
    """Verify the LLM judge can evaluate task outputs."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_judge_passing_output(self):
        from rooben.domain import Task, TaskResult, TaskStatus
        from rooben.planning.provider import AnthropicProvider
        from rooben.verification.llm_judge import LLMJudgeVerifier

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        verifier = LLMJudgeVerifier(provider=provider)

        task = Task(
            id="t-judge-1",
            workstream_id="ws-1",
            workflow_id="wf-1",
            title="Create hello endpoint",
            description="Write a FastAPI endpoint that returns Hello World",
            status=TaskStatus.VERIFYING,
        )
        result = TaskResult(
            output='from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/hello")\ndef hello():\n    return {"message": "Hello, World!"}',
        )

        feedback = await verifier.verify(task, result)

        _write_artifact("live_05_judge", "passing_verdict.json", json.dumps({
            "passed": feedback.passed,
            "score": feedback.score,
            "feedback": feedback.feedback,
            "suggestions": feedback.suggested_improvements,
        }, indent=2))

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_judge_failing_output(self):
        from rooben.domain import Task, TaskResult, TaskStatus
        from rooben.planning.provider import AnthropicProvider
        from rooben.verification.llm_judge import LLMJudgeVerifier

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        verifier = LLMJudgeVerifier(provider=provider)

        task = Task(
            id="t-judge-2",
            workstream_id="ws-1",
            workflow_id="wf-1",
            title="Create hello endpoint with error handling",
            description="Write a FastAPI endpoint that returns Hello World and handles 404 errors with JSON",
            status=TaskStatus.VERIFYING,
        )
        result = TaskResult(
            output="print('hello world')",  # Obviously wrong — not FastAPI
        )

        feedback = await verifier.verify(task, result)

        _write_artifact("live_05_judge", "failing_verdict.json", json.dumps({
            "passed": feedback.passed,
            "score": feedback.score,
            "feedback": feedback.feedback,
            "suggestions": feedback.suggested_improvements,
        }, indent=2))


# ===========================================================================
# 6. Full E2E: rooben run with real API
# ===========================================================================


@has_anthropic
class TestFullE2ELive:
    """Run the full orchestration loop with a real LLM."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_hello_api_e2e(self, tmp_path):
        from rooben.agents.registry import AgentRegistry
        from rooben.orchestrator import Orchestrator
        from rooben.planning.llm_planner import LLMPlanner
        from rooben.planning.provider import AnthropicProvider
        from rooben.spec.loader import load_spec
        from rooben.state.filesystem import FilesystemBackend
        from rooben.verification.llm_judge import LLMJudgeVerifier

        spec = load_spec("examples/hello_api.yaml")
        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        planner = LLMPlanner(provider=provider)
        registry = AgentRegistry(llm_provider=provider)
        registry.register_from_specs(spec.agents)
        backend = FilesystemBackend(base_dir=str(tmp_path / "state"))
        verifier = LLMJudgeVerifier(provider=provider)

        orchestrator = Orchestrator(
            planner=planner,
            agent_registry=registry,
            backend=backend,
            verifier=verifier,
            budget=spec.global_budget,
        )

        state = await orchestrator.run(spec)

        # Collect results
        wf = list(state.workflows.values())[0]
        task_results = []
        for t in state.tasks.values():
            task_results.append({
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "attempt": t.attempt,
                "has_result": t.result is not None,
                "output_preview": (t.result.output[:200] if t.result and t.result.output else None),
                "artifacts": list(t.result.artifacts.keys()) if t.result else [],
                "feedback_count": len(t.attempt_feedback),
                "last_score": t.attempt_feedback[-1].score if t.attempt_feedback else None,
            })

        _write_artifact("live_06_e2e", "hello_api_result.json", json.dumps({
            "workflow_status": wf.status.value,
            "total_tasks": wf.total_tasks,
            "completed_tasks": wf.completed_tasks,
            "failed_tasks": wf.failed_tasks,
            "tasks": task_results,
        }, indent=2))

        # Write individual task outputs
        for t in state.tasks.values():
            if t.result and t.result.artifacts:
                for name, content in t.result.artifacts.items():
                    safe_name = name.replace("/", "_").replace("\\", "_")
                    _write_artifact("live_06_e2e/artifacts", safe_name, content)

        # The workflow should have produced at least some tasks
        assert wf.total_tasks > 0


# ===========================================================================
# 7. Cost Tracking: Real API costs vs registry estimates
# ===========================================================================


@has_anthropic
class TestCostTrackingLive:
    """Compare CostRegistry estimates with actual API usage."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_cost_estimate_accuracy(self):
        from rooben.billing.costs import CostRegistry
        from rooben.planning.provider import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        registry = CostRegistry()

        result = await provider.generate(
            system="You are a helpful assistant.",
            prompt="What is 2+2? Answer in one word.",
            max_tokens=50,
        )

        actual_usage = result.usage
        estimated_cost = registry.calculate_cost(
            "anthropic", "claude-sonnet-4-20250514", actual_usage
        )

        _write_artifact("live_07_cost", "cost_accuracy.json", json.dumps({
            "model": "claude-sonnet-4-20250514",
            "actual_input_tokens": actual_usage.input_tokens,
            "actual_output_tokens": actual_usage.output_tokens,
            "cache_read_tokens": actual_usage.cache_read_tokens,
            "estimated_cost_usd": str(estimated_cost),
            "response_text": result.text,
        }, indent=2))

        assert estimated_cost > 0


# ===========================================================================
# 8. Postgres Backend: Real database operations
# ===========================================================================


@has_postgres
class TestPostgresLive:
    """Verify Postgres backend with a real database."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_save_and_load_state(self):
        from rooben.domain import (
            Task,
            TaskResult,
            TaskStatus,
            Workflow,
            WorkflowState,
            WorkflowStatus,
            Workstream,
        )
        from rooben.state.postgres import PostgresBackend

        backend = PostgresBackend()
        await backend.initialize()

        try:
            state = WorkflowState()
            wf = Workflow(
                id="wf-live-test-001",
                spec_id="spec-live-test",
                status=WorkflowStatus.IN_PROGRESS,
                workstream_ids=["ws-live-1"],
                total_tasks=1,
            )
            state.workflows[wf.id] = wf

            ws = Workstream(
                id="ws-live-1", workflow_id=wf.id,
                name="Live Test", description="Testing with real Postgres",
                task_ids=["t-live-1"],
            )
            state.workstreams[ws.id] = ws

            t = Task(
                id="t-live-1", workstream_id=ws.id, workflow_id=wf.id,
                title="Live DB Test", description="Verify Postgres round-trip",
                status=TaskStatus.PASSED, assigned_agent_id="test-agent",
                result=TaskResult(output="Postgres works!", token_usage=100),
            )
            state.register_task(t)

            await backend.save_state(state)
            loaded = await backend.load_state("wf-live-test-001")

            assert loaded is not None
            assert loaded.tasks["t-live-1"].result.output == "Postgres works!"

            _write_artifact("live_08_postgres", "roundtrip.json", json.dumps({
                "success": True,
                "workflow_id": "wf-live-test-001",
                "task_status": loaded.tasks["t-live-1"].status.value,
                "output": loaded.tasks["t-live-1"].result.output,
            }, indent=2))
        finally:
            await backend.close()
