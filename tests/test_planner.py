"""Tests for the LLM planner."""

from __future__ import annotations

import json

import pytest

from rooben.planning.llm_planner import LLMPlanner, PlanningFailed


class TestLLMPlanner:
    @pytest.mark.asyncio
    async def test_plan_produces_state(self, mock_provider, sample_spec):
        planner = LLMPlanner(provider=mock_provider)
        state = await planner.plan(sample_spec, "wf-test-001")

        assert "wf-test-001" in state.workflows
        assert len(state.workstreams) > 0
        assert len(state.tasks) > 0

    @pytest.mark.asyncio
    async def test_plan_assigns_agents(self, mock_provider, sample_spec):
        planner = LLMPlanner(provider=mock_provider)
        state = await planner.plan(sample_spec, "wf-test-002")

        for task in state.tasks.values():
            assert task.assigned_agent_id is not None
            assert task.assigned_agent_id in {a.id for a in sample_spec.agents}

    @pytest.mark.asyncio
    async def test_plan_respects_dependencies(self, mock_provider, sample_spec):
        planner = LLMPlanner(provider=mock_provider)
        state = await planner.plan(sample_spec, "wf-test-003")

        # Task 2 depends on task 1
        task_ids = list(state.tasks.keys())
        if len(task_ids) >= 2:
            task2 = state.tasks[task_ids[1]]
            if task2.depends_on:
                for dep in task2.depends_on:
                    assert dep in state.tasks

    @pytest.mark.asyncio
    async def test_plan_deduplicates_tasks(self, mock_provider, sample_spec):
        """Verify the state builder deduplicates tasks with identical content."""
        planner = LLMPlanner(provider=mock_provider)
        state = await planner.plan(sample_spec, "wf-test-004")

        hashes = [t.content_hash() for t in state.tasks.values()]
        assert len(hashes) == len(set(hashes))

    @pytest.mark.asyncio
    async def test_plan_invalid_json_raises(self, sample_spec):
        from tests.conftest import MockLLMProvider

        provider = MockLLMProvider(responses={"plan": "not valid json at all"})
        planner = LLMPlanner(provider=provider)

        with pytest.raises(ValueError, match="invalid JSON"):
            await planner.plan(sample_spec, "wf-bad")


class _AutoApproveJudge:
    """Mock judge provider that always approves."""
    async def generate(self, system, prompt, max_tokens=4096):
        from rooben.domain import TokenUsage
        from rooben.planning.provider import GenerationResult
        return GenerationResult(
            text=json.dumps({"approved": True, "issues": []}),
            usage=TokenUsage(), model="mock", provider="mock",
        )


class TestPlanCheckerReprompt:
    """Integration tests for PlanChecker → LLMPlanner re-prompt loop."""

    @pytest.mark.asyncio
    async def test_reprompt_on_invalid_plan(self, sample_spec):
        """LLMPlanner re-prompts when PlanChecker finds issues, then succeeds."""
        from rooben.domain import TokenUsage
        from rooben.planning.provider import GenerationResult

        # First response: plan with unassigned agent (invalid)
        bad_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [{
                    "id": "t-1", "title": "Task", "description": "d",
                    "assigned_agent_id": None,  # Invalid: no agent
                    "depends_on": [],
                    "acceptance_criteria_ids": [],
                    "verification_strategy": "llm_judge",
                    "skeleton_tests": [],
                }],
            }],
        })
        # Second response: valid plan
        good_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [{
                    "id": "t-1", "title": "Task", "description": "d",
                    "assigned_agent_id": "agent-1",
                    "depends_on": [],
                    "acceptance_criteria_ids": [],
                    "verification_strategy": "llm_judge",
                    "skeleton_tests": [],
                }],
            }],
        })

        call_count = 0

        class RepromptProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                nonlocal call_count
                call_count += 1
                text = bad_plan if call_count == 1 else good_plan
                return GenerationResult(
                    text=text,
                    usage=TokenUsage(input_tokens=100, output_tokens=50),
                    model="mock", provider="mock",
                )

        planner = LLMPlanner(
            provider=RepromptProvider(),
            judge_provider=_AutoApproveJudge(),
            max_checker_iterations=3,
        )
        state = await planner.plan(sample_spec, "wf-reprompt")

        # Should have taken 2 iterations (checker fail → reprompt → pass)
        assert call_count == 2
        # Plan should be valid (second attempt)
        task = list(state.tasks.values())[0]
        assert task.assigned_agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_checker_exhausted_raises_planning_failed(self, sample_spec):
        """If checker fails all iterations, PlanningFailed is raised."""
        from rooben.domain import TokenUsage
        from rooben.planning.provider import GenerationResult

        # Always returns invalid plan (cycle)
        cyclic_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [
                    {
                        "id": "t-1", "title": "A", "description": "d",
                        "assigned_agent_id": "agent-1",
                        "depends_on": ["t-2"],
                    },
                    {
                        "id": "t-2", "title": "B", "description": "d",
                        "assigned_agent_id": "agent-1",
                        "depends_on": ["t-1"],
                    },
                ],
            }],
        })

        call_count = 0

        class AlwaysBadProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                nonlocal call_count
                call_count += 1
                return GenerationResult(
                    text=cyclic_plan,
                    usage=TokenUsage(input_tokens=100, output_tokens=50),
                    model="mock", provider="mock",
                )

        planner = LLMPlanner(
            provider=AlwaysBadProvider(),
            judge_provider=_AutoApproveJudge(),
            max_checker_iterations=2,
        )
        with pytest.raises(PlanningFailed, match="Plan validation failed"):
            await planner.plan(sample_spec, "wf-exhaust")

        # Should have tried all iterations
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_reprompt_includes_feedback(self, sample_spec):
        """Re-prompt includes checker feedback text for dependency cycle."""
        from rooben.domain import TokenUsage
        from rooben.planning.provider import GenerationResult

        prompts_received: list[str] = []

        # Cycle: t-1 → t-2 → t-1 (checker catches this, _build_state doesn't fix it)
        cyclic_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [
                    {
                        "id": "t-1", "title": "A", "description": "d",
                        "assigned_agent_id": "agent-1",
                        "depends_on": ["t-2"],
                    },
                    {
                        "id": "t-2", "title": "B", "description": "d",
                        "assigned_agent_id": "agent-1",
                        "depends_on": ["t-1"],
                    },
                ],
            }],
        })
        good_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [
                    {
                        "id": "t-1", "title": "A", "description": "d",
                        "assigned_agent_id": "agent-1",
                        "depends_on": [],
                    },
                    {
                        "id": "t-2", "title": "B", "description": "d",
                        "assigned_agent_id": "agent-1",
                        "depends_on": ["t-1"],
                    },
                ],
            }],
        })

        call_count = 0

        class TrackingProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                nonlocal call_count
                prompts_received.append(prompt)
                call_count += 1
                text = cyclic_plan if call_count == 1 else good_plan
                return GenerationResult(
                    text=text,
                    usage=TokenUsage(input_tokens=100, output_tokens=50),
                    model="mock", provider="mock",
                )

        planner = LLMPlanner(
            provider=TrackingProvider(),
            judge_provider=_AutoApproveJudge(),
            max_checker_iterations=3,
        )
        await planner.plan(sample_spec, "wf-feedback")

        # Second prompt should contain checker feedback about cycle
        assert len(prompts_received) == 2
        assert "Plan Checker Feedback" in prompts_received[1]
        assert "cycle" in prompts_received[1].lower()


class TestPlannerEventCallback:
    """Tests for planning progress event emission."""

    @pytest.mark.asyncio
    async def test_events_emitted_in_order(self, sample_spec):
        """Verify planning events are emitted in the correct order on success."""
        from rooben.domain import TokenUsage
        from rooben.planning.provider import GenerationResult

        good_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [{
                    "id": "t-1", "title": "Task", "description": "d",
                    "assigned_agent_id": "agent-1",
                    "depends_on": [],
                    "acceptance_criteria_ids": [],
                    "verification_strategy": "llm_judge",
                    "skeleton_tests": [],
                }],
            }],
        })

        class SimpleProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                return GenerationResult(
                    text=good_plan,
                    usage=TokenUsage(input_tokens=100, output_tokens=50),
                    model="mock", provider="mock",
                )

        events: list[tuple[str, dict]] = []

        def callback(event_type: str, payload: dict):
            events.append((event_type, payload))

        planner = LLMPlanner(
            provider=SimpleProvider(),
            judge_provider=_AutoApproveJudge(),
        )
        await planner.plan(sample_spec, "wf-events", event_callback=callback)

        event_types = [e[0] for e in events]
        assert event_types == [
            "planning.started",
            "planning.generating",
            "planning.checking",
            "planning.judging",
        ]
        # All events should have workflow_id
        for _, payload in events:
            assert payload["workflow_id"] == "wf-events"

    @pytest.mark.asyncio
    async def test_no_callback_works(self, sample_spec):
        """Verify event_callback=None (default) still works."""
        from rooben.domain import TokenUsage
        from rooben.planning.provider import GenerationResult

        good_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [{
                    "id": "t-1", "title": "Task", "description": "d",
                    "assigned_agent_id": "agent-1",
                    "depends_on": [],
                }],
            }],
        })

        class SimpleProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                return GenerationResult(
                    text=good_plan,
                    usage=TokenUsage(input_tokens=100, output_tokens=50),
                    model="mock", provider="mock",
                )

        planner = LLMPlanner(
            provider=SimpleProvider(),
            judge_provider=_AutoApproveJudge(),
        )
        # Should not raise
        state = await planner.plan(sample_spec, "wf-no-cb")
        assert len(state.tasks) == 1

    @pytest.mark.asyncio
    async def test_async_callback_awaited(self, sample_spec):
        """Verify async event callbacks are properly awaited."""
        from rooben.domain import TokenUsage
        from rooben.planning.provider import GenerationResult
        import asyncio

        good_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [{
                    "id": "t-1", "title": "Task", "description": "d",
                    "assigned_agent_id": "agent-1",
                    "depends_on": [],
                }],
            }],
        })

        class SimpleProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                return GenerationResult(
                    text=good_plan,
                    usage=TokenUsage(input_tokens=100, output_tokens=50),
                    model="mock", provider="mock",
                )

        events: list[str] = []

        async def async_callback(event_type: str, payload: dict):
            await asyncio.sleep(0)  # Simulate async work
            events.append(event_type)

        planner = LLMPlanner(
            provider=SimpleProvider(),
            judge_provider=_AutoApproveJudge(),
        )
        await planner.plan(sample_spec, "wf-async-cb", event_callback=async_callback)
        assert "planning.started" in events
