"""Shared test fixtures."""

from __future__ import annotations

import json
from typing import Any

import pytest

from rooben.domain import TokenUsage
from rooben.planning.provider import GenerationResult
from rooben.spec.models import (
    AcceptanceCriterion,
    AgentBudget,
    AgentSpec,
    AgentTransport,
    Constraint,
    ConstraintCategory,
    Deliverable,
    DeliverableType,
    GlobalBudget,
    Specification,
    SuccessCriteria,
    TestRequirement,
    TestType,
    WorkflowHint,
)


class MockLLMProvider:
    """Deterministic LLM provider for testing."""

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}
        self._calls: list[dict[str, Any]] = []
        self._default_plan = json.dumps({
            "workstreams": [
                {
                    "id": "ws-test-01",
                    "name": "Test Workstream",
                    "description": "A test workstream",
                    "tasks": [
                        {
                            "id": "task-test-01",
                            "title": "Test Task 1",
                            "description": "Do the first thing",
                            "assigned_agent_id": "agent-1",
                            "depends_on": [],
                            "acceptance_criteria_ids": ["AC-001"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                        {
                            "id": "task-test-02",
                            "title": "Test Task 2",
                            "description": "Do the second thing",
                            "assigned_agent_id": "agent-1",
                            "depends_on": ["task-test-01"],
                            "acceptance_criteria_ids": ["AC-002"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                    ],
                }
            ]
        })
        self._default_agent_response = json.dumps({
            "output": "Task completed successfully",
            "artifacts": {"result.txt": "output content"},
            "generated_tests": [],
        })
        self._default_judge_response = json.dumps({
            "passed": True,
            "score": 0.9,
            "feedback": "Looks good",
        })

    async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
        self._calls.append({"system": system, "prompt": prompt, "max_tokens": max_tokens})

        # Route to appropriate response based on system prompt content
        if "planning engine" in system.lower():
            text = self._responses.get("plan", self._default_plan)
        elif "autonomous agent executing" in system.lower():
            text = self._responses.get("agent", self._default_agent_response)
        elif "quality assurance judge" in system.lower():
            text = self._responses.get("judge", self._default_judge_response)
        else:
            text = self._responses.get("default", '{"output": "ok"}')

        return GenerationResult(
            text=text,
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            model="mock-model",
            provider="mock",
        )


@pytest.fixture
def mock_provider():
    return MockLLMProvider()


@pytest.fixture
def sample_spec():
    return Specification(
        id="spec-test-001",
        title="Test Application",
        goal="Build a simple REST API that returns hello world",
        context="This is a test specification for unit testing the orchestrator.",
        deliverables=[
            Deliverable(
                id="D-001",
                name="REST API",
                deliverable_type=DeliverableType.API,
                description="A simple HTTP API with a /hello endpoint",
                output_path="src/api.py",
                acceptance_criteria_ids=["AC-001", "AC-002"],
            ),
        ],
        success_criteria=SuccessCriteria(
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="AC-001",
                    description="GET /hello returns 200 with body 'Hello, World!'",
                    verification="test",
                ),
                AcceptanceCriterion(
                    id="AC-002",
                    description="API handles invalid routes with 404",
                    verification="llm_judge",
                ),
            ],
            test_requirements=[
                TestRequirement(
                    id="TR-001",
                    description="Unit tests for the hello endpoint",
                    test_type=TestType.UNIT,
                    target_deliverable="D-001",
                ),
            ],
        ),
        constraints=[
            Constraint(
                id="C-001",
                category=ConstraintCategory.TECHNOLOGY,
                description="Must use Python 3.11+",
            ),
        ],
        agents=[
            AgentSpec(
                id="agent-1",
                name="Python Developer",
                transport=AgentTransport.LLM,
                description="Writes Python code",
                capabilities=["python", "api", "testing"],
                max_concurrency=2,
                budget=AgentBudget(max_retries_per_task=2),
            ),
        ],
        workflow_hints=[
            WorkflowHint(
                name="API Implementation",
                description="Implement the API first, then write tests",
                suggested_agent_id="agent-1",
            ),
        ],
        global_budget=GlobalBudget(
            max_total_tasks=20,
            max_concurrent_agents=3,
        ),
    )
