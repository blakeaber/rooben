"""Tests for the LLM plan quality judge."""

from __future__ import annotations

import json

import pytest

from rooben.domain import Task, TokenUsage, Workflow, WorkflowState, Workstream
from rooben.planning.plan_judge import PlanJudge
from rooben.planning.provider import GenerationResult


def _make_state(tasks: list[Task], workflow_id: str = "wf-test") -> WorkflowState:
    """Build a minimal WorkflowState from a list of tasks."""
    state = WorkflowState()
    ws = Workstream(id="ws-1", workflow_id=workflow_id, name="WS", description="")
    for task in tasks:
        state.tasks[task.id] = task
        ws.task_ids.append(task.id)
    state.workstreams["ws-1"] = ws
    state.workflows[workflow_id] = Workflow(
        id=workflow_id, spec_id="spec-1", status="planning",
    )
    return state


class MockJudgeProvider:
    """Returns a configurable judge response."""

    def __init__(self, response: dict):
        self._response = response
        self.calls: list[str] = []

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096):
        self.calls.append(prompt)
        return GenerationResult(
            text=json.dumps(self._response),
            usage=TokenUsage(input_tokens=200, output_tokens=100),
            model="mock", provider="mock",
        )


# --- score helpers for test data ---
_APPROVED_RESPONSE = {"approved": True, "score": 0.95, "issues": []}
_REJECTED_RESPONSE = {
    "approved": False,
    "score": 0.3,
    "issues": [
        {
            "task_id": "t-1",
            "severity": "high",
            "reason": "Task contains 5 independent work items",
            "suggestion": "Split into 5 separate tasks",
        },
    ],
}


class TestPlanJudge:
    @pytest.mark.asyncio
    async def test_approved_plan(self, sample_spec):
        provider = MockJudgeProvider(_APPROVED_RESPONSE)
        judge = PlanJudge(provider)

        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Simple task", description="Implement hello endpoint",
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = await judge.judge(state, sample_spec, "wf-test")

        assert result.approved
        assert result.score == 0.95
        assert len(result.issues) == 0
        assert len(provider.calls) == 1

    @pytest.mark.asyncio
    async def test_rejected_plan_with_issues(self, sample_spec):
        provider = MockJudgeProvider(_REJECTED_RESPONSE)
        judge = PlanJudge(provider)

        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Oversized", description="Do everything",
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = await judge.judge(state, sample_spec, "wf-test")

        assert not result.approved
        assert result.score == 0.3
        assert len(result.issues) == 1
        assert result.issues[0].severity == "high"
        assert result.issues[0].task_id == "t-1"

    @pytest.mark.asyncio
    async def test_empty_task_list_auto_approves(self, sample_spec):
        provider = MockJudgeProvider(_REJECTED_RESPONSE)
        judge = PlanJudge(provider)

        state = WorkflowState()
        result = await judge.judge(state, sample_spec, "wf-test")

        assert result.approved
        assert result.score == 1.0
        assert len(provider.calls) == 0  # Should not call LLM

    @pytest.mark.asyncio
    async def test_invalid_json_returns_approved(self, sample_spec):
        """If the judge returns unparseable JSON, default to approved with score 1.0."""

        class BadProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                return GenerationResult(
                    text="not valid json",
                    usage=TokenUsage(input_tokens=50, output_tokens=20),
                    model="mock", provider="mock",
                )

        judge = PlanJudge(BadProvider())
        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Task", description="Do stuff",
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = await judge.judge(state, sample_spec, "wf-test")

        assert result.approved
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_usage_tracked(self, sample_spec):
        provider = MockJudgeProvider(_APPROVED_RESPONSE)
        judge = PlanJudge(provider)

        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Task", description="Do stuff",
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = await judge.judge(state, sample_spec, "wf-test")

        assert result.usage.input_tokens == 200
        assert result.usage.output_tokens == 100

    @pytest.mark.asyncio
    async def test_score_clamped_to_0_1(self, sample_spec):
        """Score from LLM is clamped to [0.0, 1.0] even if out of range."""
        provider = MockJudgeProvider({"approved": True, "score": 1.5, "issues": []})
        judge = PlanJudge(provider)

        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Task", description="Stuff",
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = await judge.judge(state, sample_spec, "wf-test")
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_score_defaults_when_missing(self, sample_spec):
        """If LLM omits score, default based on approved status."""
        provider = MockJudgeProvider({"approved": False, "issues": []})
        judge = PlanJudge(provider)

        task = Task(
            id="t-1", workstream_id="ws-1", workflow_id="wf-test",
            title="Task", description="Stuff",
            assigned_agent_id="agent-1",
        )
        state = _make_state([task])
        result = await judge.judge(state, sample_spec, "wf-test")
        assert result.score == 0.0  # not approved → defaults to 0.0


class TestPlanJudgeIntegration:
    """Tests that LLMPlanner correctly wires the judge into the plan loop."""

    @pytest.mark.asyncio
    async def test_planner_reprompts_on_judge_rejection(self, sample_spec):
        from rooben.planning.llm_planner import LLMPlanner

        # First plan: structurally valid but judge rejects it
        plan_json = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [{
                    "id": "t-1", "title": "Oversized", "description": "Do everything",
                    "assigned_agent_id": "agent-1",
                    "depends_on": [],
                    "acceptance_criteria_ids": [],
                    "verification_strategy": "llm_judge",
                    "skeleton_tests": [],
                }],
            }],
        })
        # Second plan: judge approves
        good_plan = json.dumps({
            "workstreams": [{
                "id": "ws-1", "name": "WS", "description": "d",
                "tasks": [
                    {
                        "id": "t-1a", "title": "Part A", "description": "First part",
                        "assigned_agent_id": "agent-1",
                        "depends_on": [],
                    },
                    {
                        "id": "t-1b", "title": "Part B", "description": "Second part",
                        "assigned_agent_id": "agent-1",
                        "depends_on": ["t-1a"],
                    },
                ],
            }],
        })

        plan_call_count = 0
        judge_call_count = 0

        class PlanProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                nonlocal plan_call_count
                plan_call_count += 1
                text = plan_json if plan_call_count == 1 else good_plan
                return GenerationResult(
                    text=text,
                    usage=TokenUsage(input_tokens=100, output_tokens=50),
                    model="mock", provider="mock",
                )

        class JudgeProvider:
            async def generate(self, system, prompt, max_tokens=4096):
                nonlocal judge_call_count
                judge_call_count += 1
                if judge_call_count == 1:
                    resp = {
                        "approved": False,
                        "score": 0.2,
                        "issues": [{
                            "task_id": "t-1",
                            "severity": "high",
                            "reason": "Too large",
                            "suggestion": "Split it",
                        }],
                    }
                else:
                    resp = {"approved": True, "score": 0.9, "issues": []}
                return GenerationResult(
                    text=json.dumps(resp),
                    usage=TokenUsage(input_tokens=150, output_tokens=75),
                    model="mock", provider="mock",
                )

        planner = LLMPlanner(
            provider=PlanProvider(),
            judge_provider=JudgeProvider(),
            max_checker_iterations=3,
        )
        state = await planner.plan(sample_spec, "wf-judge")

        assert plan_call_count == 2  # Re-prompted after judge rejection
        assert judge_call_count == 2
        assert len(state.tasks) == 2  # Decomposed into 2 tasks
