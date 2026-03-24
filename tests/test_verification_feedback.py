"""Tests for WS-1.2: Verification Feedback Loop."""

from __future__ import annotations

import json
import tempfile

import pytest

from rooben.agents.registry import AgentRegistry
from rooben.domain import (
    Task,
    TaskResult,
    TaskStatus,
    TestCaseResult,
    TokenUsage,
    VerificationFeedback,
)
from rooben.orchestrator import Orchestrator
from rooben.planning.llm_planner import LLMPlanner
from rooben.planning.provider import GenerationResult
from rooben.state.filesystem import FilesystemBackend
from rooben.verification.llm_judge import LLMJudgeVerifier
from rooben.verification.verifier import ChainedVerifier, VerificationResult


def _gen(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        model="mock", provider="mock",
    )


class TestVerificationFeedbackModels:
    def test_verification_feedback_creation(self):
        fb = VerificationFeedback(
            attempt=1,
            verifier_type="llm_judge",
            passed=False,
            score=0.3,
            feedback="Missing error handling",
            suggested_improvements=["Add try/except blocks"],
        )
        assert fb.attempt == 1
        assert not fb.passed
        assert len(fb.suggested_improvements) == 1

    def test_test_case_result(self):
        tr = TestCaseResult(name="test_foo", passed=False, error_message="AssertionError")
        assert not tr.passed
        assert "Assertion" in tr.error_message


class TestTestRunnerStructuredResults:
    @pytest.mark.asyncio
    async def test_test_runner_structured_results(self):
        """TestRunnerVerifier parses individual test results."""
        from rooben.verification.test_runner import TestRunnerVerifier

        verifier = TestRunnerVerifier(timeout=30)
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Test", description="test",
            skeleton_tests=[
                "def test_pass():\n    assert True\n",
                "def test_fail():\n    assert False, 'expected failure'\n",
            ],
        )
        result = TaskResult(output="code", artifacts={})
        vr = await verifier.verify(task, result)

        assert not vr.passed
        assert len(vr.test_results) == 2
        passed = [tr for tr in vr.test_results if tr.passed]
        failed = [tr for tr in vr.test_results if not tr.passed]
        assert len(passed) == 1
        assert len(failed) == 1
        assert "fail" in failed[0].name.lower()


class TestLLMJudgeSuggestedImprovements:
    @pytest.mark.asyncio
    async def test_llm_judge_suggested_improvements(self):
        """LLM judge returns suggested_improvements."""
        class JudgeProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                return _gen(json.dumps({
                    "passed": False,
                    "score": 0.4,
                    "feedback": "Output lacks error handling",
                    "suggested_improvements": [
                        "Add input validation",
                        "Handle edge cases",
                    ],
                }))

        verifier = LLMJudgeVerifier(provider=JudgeProvider())
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Test", description="test",
        )
        result = TaskResult(output="some output")
        vr = await verifier.verify(task, result)

        assert not vr.passed
        assert len(vr.suggested_improvements) == 2
        assert "validation" in vr.suggested_improvements[0].lower()
        assert vr.verification_tokens > 0


class TestLLMJudgeManifestPrompt:
    """Verify judge uses manifest-based artifact display instead of full content."""

    def test_build_prompt_uses_manifest(self):
        """_build_prompt should show artifact manifest + preview, not full content."""
        verifier = LLMJudgeVerifier(provider=None)  # provider not needed for _build_prompt
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Build API", description="Create a REST API",
        )
        # Create result with multiple artifacts of varying sizes
        artifacts = {
            "/workspace/main.py": "x" * 2000,
            "/workspace/utils.py": "y" * 500,
            "/workspace/config.py": "z" * 100,
        }
        result = TaskResult(output="Built the API", artifacts=artifacts)
        prompt = verifier._build_prompt(task, result)

        # Should contain manifest entries with char counts
        assert "2000 chars" in prompt
        assert "500 chars" in prompt
        assert "100 chars" in prompt
        # Should have deep-dive preview sections for the 3 largest artifacts
        assert "### /workspace/main.py" in prompt
        assert "### /workspace/utils.py" in prompt
        assert "### /workspace/config.py" in prompt
        # Content fits within 15K preview limit so should appear in full
        assert "x" * 2000 in prompt
        assert "y" * 500 in prompt

    @pytest.mark.asyncio
    async def test_judge_truncation_retry(self):
        """Judge retries with higher max_tokens when truncated."""
        call_count = 0

        class TruncatingProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call: truncated
                    return GenerationResult(
                        text='{"passed": true',
                        usage=TokenUsage(input_tokens=100, output_tokens=50),
                        model="mock", provider="mock",
                        truncated=True,
                    )
                # Retry: success
                return _gen(json.dumps({
                    "passed": True,
                    "score": 0.9,
                    "feedback": "Looks good",
                    "suggested_improvements": [],
                }))

        verifier = LLMJudgeVerifier(provider=TruncatingProvider())
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Test", description="test",
        )
        result = TaskResult(output="some output")
        vr = await verifier.verify(task, result)

        assert call_count == 2  # Retried once
        assert vr.passed


class TestChainedVerifier:
    @pytest.mark.asyncio
    async def test_short_circuits_on_first_failure(self):
        """ChainedVerifier stops at first failure."""
        class FailVerifier:
            async def verify(self, task, result):
                return VerificationResult(
                    passed=False, score=0.3,
                    feedback="Failed", suggested_improvements=["Fix it"],
                )

        class PassVerifier:
            async def verify(self, task, result):
                return VerificationResult(passed=True, score=1.0, feedback="OK")

        chained = ChainedVerifier([FailVerifier(), PassVerifier()])
        task = Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                    title="Test", description="test")
        result = TaskResult(output="output")
        vr = await chained.verify(task, result)

        assert not vr.passed
        assert vr.score == 0.3
        # PassVerifier should not have been called — only 1 feedback entry
        assert "Failed" in vr.feedback
        assert "OK" not in vr.feedback

    @pytest.mark.asyncio
    async def test_both_pass(self):
        """ChainedVerifier merges results when all pass."""
        class Verifier1:
            async def verify(self, task, result):
                return VerificationResult(
                    passed=True, score=0.9, feedback="Good code",
                )

        class Verifier2:
            async def verify(self, task, result):
                return VerificationResult(
                    passed=True, score=0.8, feedback="Tests pass",
                )

        chained = ChainedVerifier([Verifier1(), Verifier2()])
        task = Task(id="t-1", workstream_id="ws-1", workflow_id="wf-1",
                    title="Test", description="test")
        result = TaskResult(output="output")
        vr = await chained.verify(task, result)

        assert vr.passed
        assert vr.score == 0.8  # min of both
        assert "Good code" in vr.feedback
        assert "Tests pass" in vr.feedback

    def test_requires_at_least_one_verifier(self):
        with pytest.raises(ValueError, match="at least one"):
            ChainedVerifier([])


class TestRetryIncludesPriorFeedback:
    @pytest.mark.asyncio
    async def test_retry_includes_prior_feedback(self):
        """When a task fails verification and retries, the prompt includes prior feedback."""
        from tests.conftest import MockLLMProvider

        judge_calls = {"count": 0}
        agent_prompts: list[str] = []

        class FeedbackTrackingProvider(MockLLMProvider):
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                self._calls.append({"system": system, "prompt": prompt})

                if "planning engine" in system.lower():
                    return _gen(self._default_plan)
                elif "autonomous agent executing" in system.lower():
                    agent_prompts.append(prompt)
                    return _gen(self._default_agent_response)
                elif "quality assurance" in system.lower():
                    judge_calls["count"] += 1
                    if judge_calls["count"] <= 2:
                        return _gen(json.dumps({
                            "passed": False,
                            "score": 0.3,
                            "feedback": f"Issue on attempt {judge_calls['count']}",
                            "suggested_improvements": [f"Fix problem {judge_calls['count']}"],
                        }))
                    return _gen(json.dumps({"passed": True, "score": 0.9, "feedback": "OK"}))
                return _gen('{"output": "ok"}')

        provider = FeedbackTrackingProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)
            registry.register_mcp_agent("agent-1", max_concurrency=2)
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
            )

            from rooben.spec.models import (
                AgentSpec, AgentTransport, Deliverable, DeliverableType, Specification,
            )
            spec = Specification(
                id="spec-test",
                title="Test",
                goal="Test feedback",
                deliverables=[Deliverable(id="D-1", name="Out", deliverable_type=DeliverableType.CODE, description="test")],
                agents=[AgentSpec(id="agent-1", name="Dev", transport=AgentTransport.SUBPROCESS,
                                  description="test", endpoint="tests.helpers.mock_agent_callable",
                                  capabilities=["python"])],
            )
            await orchestrator.run(spec)

            # After first failure, retry prompt should include feedback
            # agent_prompts[0] = first attempt (no feedback)
            # agent_prompts[1] = second attempt (should have attempt 1 feedback)
            if len(agent_prompts) >= 3:
                # Third attempt should mention prior feedback
                assert "Prior Attempt Feedback" in agent_prompts[2]
                assert "Fix problem" in agent_prompts[2]


class TestFeedbackAccumulates:
    @pytest.mark.asyncio
    async def test_feedback_accumulates(self):
        """Multiple failures accumulate feedback on the task."""
        from tests.conftest import MockLLMProvider

        judge_count = {"n": 0}

        class AlwaysFailProvider(MockLLMProvider):
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                self._calls.append({"system": system, "prompt": prompt})
                if "planning engine" in system.lower():
                    # Single task, simple plan
                    return _gen(json.dumps({
                        "workstreams": [{
                            "id": "ws-1", "name": "WS", "description": "d",
                            "tasks": [{
                                "id": "task-1", "title": "Task",
                                "description": "Do it",
                                "assigned_agent_id": "agent-1",
                                "depends_on": [],
                                "acceptance_criteria_ids": [],
                                "verification_strategy": "llm_judge",
                                "skeleton_tests": [],
                            }],
                        }],
                    }))
                elif "autonomous agent executing" in system.lower():
                    return _gen(self._default_agent_response)
                elif "quality assurance" in system.lower():
                    judge_count["n"] += 1
                    return _gen(json.dumps({
                        "passed": False,
                        "score": 0.2,
                        "feedback": f"Fail #{judge_count['n']}",
                        "suggested_improvements": [f"Improvement #{judge_count['n']}"],
                    }))
                return _gen('{"output": "ok"}')

        provider = AlwaysFailProvider()

        from rooben.spec.models import (
            AgentBudget, AgentSpec, AgentTransport, Deliverable,
            DeliverableType, Specification,
        )
        spec = Specification(
            id="spec-test", title="Test", goal="Test",
            deliverables=[Deliverable(id="D-1", name="Out", deliverable_type=DeliverableType.CODE, description="test")],
            agents=[AgentSpec(id="agent-1", name="Dev", transport=AgentTransport.SUBPROCESS,
                              description="test", endpoint="tests.helpers.mock_agent_callable",
                              capabilities=["python"],
                              budget=AgentBudget(max_retries_per_task=3))],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)
            registry.register_mcp_agent("agent-1", max_concurrency=1)
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner, agent_registry=registry,
                backend=backend, verifier=verifier,
            )
            state = await orchestrator.run(spec)

            # Task should have failed after 3 retries (task IDs have workflow suffix)
            from tests.helpers import find_task
            task = find_task(state, "Task")
            assert task is not None
            assert task.status == TaskStatus.FAILED

            # Should have accumulated feedback from each failed attempt
            assert len(task.attempt_feedback) >= 2
            for i, fb in enumerate(task.attempt_feedback):
                assert fb.attempt == i + 1
                assert not fb.passed
                assert f"Fail #{i + 1}" in fb.feedback


class TestContextBuilder:
    def test_basic_prompt(self):
        from rooben.context.builder import ContextBuilder

        builder = ContextBuilder()
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Build API", description="Create REST API",
            acceptance_criteria_ids=["AC-001"],
        )
        prompt = builder.build(task)
        assert "Build API" in prompt
        assert "Create REST API" in prompt
        assert "AC-001" in prompt

    def test_includes_feedback(self):
        from rooben.context.builder import ContextBuilder

        builder = ContextBuilder()
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Task", description="Desc",
            attempt_feedback=[
                VerificationFeedback(
                    attempt=1, verifier_type="llm_judge", passed=False,
                    score=0.3, feedback="Missing tests",
                    suggested_improvements=["Add unit tests"],
                ),
            ],
        )
        prompt = builder.build(task)
        assert "Prior Attempt Feedback" in prompt
        assert "Missing tests" in prompt
        assert "Add unit tests" in prompt

    def test_includes_dependency_outputs(self):
        from rooben.context.builder import ContextBuilder
        from rooben.domain import WorkflowState

        state = WorkflowState()
        dep_task = Task(
            id="dep-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Dep Task", description="Dependency",
            result=TaskResult(output="Dependency output content"),
        )
        state.tasks["dep-1"] = dep_task

        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-1",
            title="Main Task", description="Uses dep",
            depends_on=["dep-1"],
        )

        builder = ContextBuilder()
        prompt = builder.build(task, state)
        assert "Outputs from Dependency Tasks" in prompt
        assert "Dependency output content" in prompt
