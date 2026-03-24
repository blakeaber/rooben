"""Tests for WS-2.1: Circuit Breaker."""

from __future__ import annotations

import json
import tempfile
import time

import pytest

from rooben.resilience.circuit_breaker import CircuitBreaker


class TestCircuitBreakerStates:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.can_proceed()

    def test_opens_after_consecutive_failures(self):
        cb = CircuitBreaker(max_failures=3)
        cb.record_failure("error 1")
        cb.record_failure("error 2")
        assert cb.state == "closed"
        cb.record_failure("error 3")
        assert cb.state == "open"
        assert not cb.can_proceed()

    def test_opens_on_identical_errors(self):
        cb = CircuitBreaker(max_failures=100, max_identical=3)
        # Mix in a success to break consecutive count
        cb.record_failure("same error")
        cb.record_success()
        cb.record_failure("same error")
        cb.record_success()
        cb.record_failure("same error")
        assert cb.state == "open"

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker(max_failures=1, cooldown_seconds=0.1)
        cb.record_failure("err")
        assert cb.state == "open"
        time.sleep(0.15)
        assert cb.state == "half_open"
        assert cb.can_proceed()

    def test_closes_on_success_in_half_open(self):
        cb = CircuitBreaker(max_failures=1, cooldown_seconds=0.0)
        cb.record_failure("err")
        # Cooldown is 0 so immediately half_open
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.state == "closed"

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(max_failures=1, cooldown_seconds=10.0)
        cb.record_failure("err")
        assert cb.state == "open"
        # Manually force half_open by patching opened_at
        cb._opened_at = time.monotonic() - 11
        assert cb.state == "half_open"
        cb.record_failure("another err")
        assert cb.state == "open"
        assert not cb.can_proceed()

    def test_reset(self):
        cb = CircuitBreaker(max_failures=1)
        cb.record_failure("err")
        assert cb.state == "open"
        cb.reset()
        assert cb.state == "closed"
        assert cb.can_proceed()


class TestCircuitBreakerInOrchestrator:
    @pytest.mark.asyncio
    async def test_orchestrator_stops_on_open_circuit(self):
        """When circuit breaker is open, orchestrator fails remaining tasks."""
        from rooben.agents.registry import AgentRegistry
        from rooben.domain import WorkflowStatus
        from rooben.orchestrator import Orchestrator
        from rooben.planning.llm_planner import LLMPlanner
        from rooben.planning.provider import GenerationResult
        from rooben.domain import TokenUsage
        from rooben.state.filesystem import FilesystemBackend
        from rooben.verification.llm_judge import LLMJudgeVerifier
        from tests.conftest import MockLLMProvider

        class AlwaysFailJudgeProvider(MockLLMProvider):
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                self._calls.append({"system": system, "prompt": prompt})
                if "planning engine" in system.lower():
                    return GenerationResult(
                        text=self._default_plan,
                        usage=TokenUsage(input_tokens=100, output_tokens=50),
                        model="mock", provider="mock",
                    )
                elif "autonomous agent executing" in system.lower():
                    return GenerationResult(
                        text=self._default_agent_response,
                        usage=TokenUsage(input_tokens=100, output_tokens=50),
                        model="mock", provider="mock",
                    )
                elif "quality assurance" in system.lower():
                    return GenerationResult(
                        text=json.dumps({"passed": False, "score": 0.1, "feedback": "Always fails"}),
                        usage=TokenUsage(input_tokens=100, output_tokens=50),
                        model="mock", provider="mock",
                    )
                return GenerationResult(
                    text='{"output": "ok"}',
                    usage=TokenUsage(input_tokens=10, output_tokens=5),
                    model="mock", provider="mock",
                )

        provider = AlwaysFailJudgeProvider()
        # Circuit breaker with max_failures=1 so it trips after first task fails
        cb = CircuitBreaker(max_failures=1)

        from rooben.spec.models import (
            AgentSpec, AgentTransport, Deliverable, DeliverableType, Specification,
        )
        spec = Specification(
            id="spec-cb",
            title="CB Test",
            goal="Test circuit breaker",
            deliverables=[Deliverable(id="D-1", name="Out", deliverable_type=DeliverableType.CODE, description="test")],
            agents=[AgentSpec(id="agent-1", name="Dev", transport=AgentTransport.SUBPROCESS,
                              description="test", endpoint="tests.helpers.mock_agent_callable",
                              capabilities=["python"])],
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
                circuit_breaker=cb,
            )
            state = await orchestrator.run(spec)

            wf = list(state.workflows.values())[0]
            assert wf.status == WorkflowStatus.FAILED
