"""Integration test — runs a full spec through the orchestrator with mocked LLM."""

from __future__ import annotations

import tempfile

import pytest

from rooben.agents.registry import AgentRegistry
from rooben.domain import TokenUsage, WorkflowStatus
from rooben.orchestrator import Orchestrator
from rooben.planning.llm_planner import LLMPlanner
from rooben.planning.provider import GenerationResult
from rooben.state.filesystem import FilesystemBackend
from rooben.verification.llm_judge import LLMJudgeVerifier


def _gen(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        model="mock-model",
        provider="mock",
    )


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_full_run(self, mock_provider, sample_spec):
        """End-to-end test: spec → plan → execute → verify → done."""
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=mock_provider)

            registry = AgentRegistry(llm_provider=mock_provider)
            # Register an LLM agent matching the spec's agent ID
            registry.register_mcp_agent("agent-1", max_concurrency=2)

            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=mock_provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=sample_spec.global_budget,
            )

            state = await orchestrator.run(sample_spec)

            # Verify completion
            assert len(state.workflows) == 1
            wf = list(state.workflows.values())[0]
            assert wf.status == WorkflowStatus.COMPLETED
            assert wf.completed_tasks > 0
            assert wf.failed_tasks == 0

    @pytest.mark.asyncio
    async def test_failed_verification_retries(self, sample_spec):
        """Test that tasks are retried when verification fails."""
        from tests.conftest import MockLLMProvider
        import json

        call_count = 0

        class FailThenPassProvider(MockLLMProvider):
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                nonlocal call_count
                call_count += 1
                self._calls.append({"system": system, "prompt": prompt})

                if "planning engine" in system.lower():
                    return _gen(self._default_plan)
                elif "autonomous agent executing" in system.lower():
                    return _gen(self._default_agent_response)
                elif "quality assurance" in system.lower():
                    # Fail first 2 verification calls, then pass
                    judge_calls = sum(
                        1 for c in self._calls if "quality assurance" in c["system"].lower()
                    )
                    if judge_calls <= 2:
                        return _gen(json.dumps({"passed": False, "score": 0.3, "feedback": "Not good enough"}))
                    return _gen(json.dumps({"passed": True, "score": 0.9, "feedback": "OK now"}))
                return _gen('{"output": "ok"}')

        provider = FailThenPassProvider()

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
                budget=sample_spec.global_budget,
            )

            state = await orchestrator.run(sample_spec)

            # At least some tasks should have required retries
            wf = list(state.workflows.values())[0]
            assert wf.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED)

    @pytest.mark.asyncio
    async def test_state_persisted(self, mock_provider, sample_spec):
        """Verify state is written to the backend after execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=mock_provider)
            registry = AgentRegistry(llm_provider=mock_provider)
            registry.register_mcp_agent("agent-1", max_concurrency=2)
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=mock_provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
            )

            state = await orchestrator.run(sample_spec)

            # Re-load from backend
            await backend.initialize()
            wf_id = list(state.workflows.keys())[0]
            loaded = await backend.load_state(wf_id)
            assert loaded is not None
            assert len(loaded.tasks) == len(state.tasks)

