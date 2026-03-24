"""Tests for WS-0.1: Interactive Refinement Engine."""

from __future__ import annotations

import json

import pytest

from rooben.domain import TokenUsage
from rooben.planning.provider import GenerationResult
from rooben.refinement.agent_generator import AgentRosterGenerator
from rooben.refinement.engine import RefinementEngine
from rooben.refinement.spec_builder import SpecBuilder
from rooben.refinement.state import (
    ConversationState,
    GatheredInfo,
    SchemaGap,
    UserProfile,
)
from rooben.spec.models import AgentSpec, AgentTransport


def _gen(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        model="mock", provider="mock",
    )


class TestStateModels:
    def test_schema_gap(self):
        gap = SchemaGap(field_path="deliverables[0].name", importance=0.9, description="Missing name")
        assert gap.importance == 0.9
        assert not gap.resolved

    def test_user_profile_defaults(self):
        profile = UserProfile()
        assert profile.technical_level == "unknown"
        assert profile.domain == "unknown"

    def test_conversation_state_defaults(self):
        state = ConversationState()
        assert state.phase == "discovery"
        assert state.completeness == 0.0
        assert state.turn_count == 0

    def test_gathered_info(self):
        info = GatheredInfo(
            title="My Project",
            goal="Build an API",
            deliverables=[{"name": "API", "description": "REST API", "deliverable_type": "code"}],
        )
        assert info.title == "My Project"
        assert len(info.deliverables) == 1


class TestRefinementEngine:
    @pytest.mark.asyncio
    async def test_start_returns_questions(self):
        """Engine.start() should return a list of questions."""
        call_num = {"n": 0}

        class MockProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                call_num["n"] += 1
                if call_num["n"] == 1:
                    # Gap analysis
                    return _gen(json.dumps({
                        "gaps": [
                            {"field_path": "title", "importance": 0.9, "description": "Need project title"},
                            {"field_path": "deliverables", "importance": 0.8, "description": "Need deliverables"},
                        ],
                        "completeness": 0.1,
                        "user_profile": {"technical_level": "advanced", "domain": "web", "communication_style": "concise"},
                    }))
                else:
                    # Question generation
                    return _gen(json.dumps({
                        "questions": ["What is the name of your project?", "What are the main deliverables?"],
                    }))

        engine = RefinementEngine(provider=MockProvider())
        questions = await engine.start("I want to build a REST API")

        assert len(questions) >= 1
        assert engine.state.completeness == 0.1
        assert engine.state.user_profile.technical_level == "advanced"

    @pytest.mark.asyncio
    async def test_completeness_phase_transitions(self):
        """Engine transitions discovery → refinement → review based on completeness."""
        call_num = {"n": 0}

        class PhaseProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                call_num["n"] += 1
                if "gap analyzer" in system.lower():
                    # Increase completeness with each analysis
                    completeness = min(0.8, 0.3 * call_num["n"])
                    return _gen(json.dumps({
                        "gaps": [{"field_path": "x", "importance": 0.5, "description": "d"}],
                        "completeness": completeness,
                        "user_profile": {"technical_level": "advanced", "domain": "d", "communication_style": "c"},
                    }))
                elif "integrator" in system.lower():
                    return _gen(json.dumps({
                        "gathered_info": {"title": "Test", "goal": "Goal"},
                        "resolved_gaps": [],
                        "new_gaps": [],
                        "user_profile": {"technical_level": "advanced", "domain": "d", "communication_style": "c"},
                    }))
                else:
                    return _gen(json.dumps({"questions": ["Next question?"]}))

        engine = RefinementEngine(provider=PhaseProvider())
        await engine.start("Build something")
        assert engine.state.phase == "discovery"

        # Process answers until we reach review
        for i in range(5):
            result = await engine.process_answer(f"Answer {i}")
            if isinstance(result, ConversationState):
                assert result.phase == "review"
                break
        else:
            pytest.fail("Never reached review phase")

    @pytest.mark.asyncio
    async def test_max_turns_forces_review(self):
        """Engine transitions to review after max_turns."""

        class MinimalProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                if "gap analyzer" in system.lower():
                    return _gen(json.dumps({
                        "gaps": [], "completeness": 0.1,
                        "user_profile": {"technical_level": "u", "domain": "u", "communication_style": "u"},
                    }))
                elif "integrator" in system.lower():
                    return _gen(json.dumps({
                        "gathered_info": {"title": "T"},
                        "resolved_gaps": [], "new_gaps": [],
                    }))
                else:
                    return _gen(json.dumps({"questions": ["Q?"]}))

        engine = RefinementEngine(provider=MinimalProvider(), max_turns=2)
        await engine.start("Build it")
        await engine.process_answer("First answer")
        result = await engine.process_answer("Second answer")
        assert isinstance(result, ConversationState)
        assert result.phase == "review"


class TestAgentRosterGenerator:
    @pytest.mark.asyncio
    async def test_generates_valid_agents(self):
        class AgentProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                return _gen(json.dumps({
                    "agents": [
                        {
                            "id": "agent-1",
                            "name": "Backend Dev",
                            "transport": "subprocess",
                            "description": "Backend development",
                            "capabilities": ["python", "api"],
                            "max_concurrency": 2,
                        },
                    ],
                }))

        gen = AgentRosterGenerator(provider=AgentProvider())
        agents = await gen.generate(GatheredInfo(goal="Build API"), UserProfile())
        assert len(agents) == 1
        assert agents[0].id == "agent-1"
        assert agents[0].transport == AgentTransport.SUBPROCESS

    @pytest.mark.asyncio
    async def test_falls_back_on_error(self):
        class FailProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                raise RuntimeError("LLM down")

        gen = AgentRosterGenerator(provider=FailProvider())
        agents = await gen.generate(GatheredInfo(), UserProfile())
        assert len(agents) >= 1  # Should get fallback agents


class TestSpecBuilder:
    def test_builds_valid_spec(self):
        info = GatheredInfo(
            title="My API",
            goal="Build a REST API",
            deliverables=[
                {"name": "API Server", "description": "REST API", "deliverable_type": "code"},
            ],
            constraints=[
                {"category": "technology", "description": "Must use Python"},
            ],
            acceptance_criteria=[
                {"description": "API responds to GET /health"},
            ],
        )
        agents = [
            AgentSpec(
                id="agent-1", name="Dev", transport=AgentTransport.SUBPROCESS,
                description="Developer", capabilities=["python"],
            ),
        ]
        builder = SpecBuilder()
        spec = builder.build(info, agents)

        assert spec.title == "My API"
        assert spec.goal == "Build a REST API"
        assert len(spec.deliverables) == 1
        assert len(spec.constraints) == 1
        assert len(spec.success_criteria.acceptance_criteria) == 1
        assert len(spec.agents) == 1

    def test_to_yaml(self):
        info = GatheredInfo(title="Test", goal="Test goal")
        agents = [
            AgentSpec(
                id="agent-1", name="Dev", transport=AgentTransport.SUBPROCESS,
                description="Dev",
            ),
        ]
        builder = SpecBuilder()
        spec = builder.build(info, agents)
        yaml_str = builder.to_yaml(spec)
        assert "Test" in yaml_str
        assert "goal" in yaml_str

    def test_empty_deliverables_gets_default(self):
        info = GatheredInfo(title="Test", goal="Build something")
        agents = [
            AgentSpec(
                id="a", name="A", transport=AgentTransport.SUBPROCESS,
                description="d",
            ),
        ]
        builder = SpecBuilder()
        spec = builder.build(info, agents)
        assert len(spec.deliverables) == 1
        assert spec.deliverables[0].name == "Primary Output"


class TestFullConversation:
    @pytest.mark.asyncio
    async def test_full_3_turn_conversation(self):
        """Mock provider through 3 turns, verify valid Specification output."""
        call_num = {"n": 0}

        class FullFlowProvider:
            async def generate(self, system: str, prompt: str, max_tokens: int = 4096) -> GenerationResult:
                call_num["n"] += 1
                if "gap analyzer" in system.lower():
                    return _gen(json.dumps({
                        "gaps": [{"field_path": "title", "importance": 0.9, "description": "need title"}],
                        "completeness": min(0.8, 0.3 * call_num["n"]),
                        "user_profile": {"technical_level": "advanced", "domain": "web", "communication_style": "concise"},
                    }))
                elif "integrator" in system.lower():
                    return _gen(json.dumps({
                        "gathered_info": {
                            "title": "Web API",
                            "goal": "Build a REST API for users",
                            "deliverables": [{"name": "API", "description": "REST API", "deliverable_type": "code"}],
                        },
                        "resolved_gaps": ["title"],
                        "new_gaps": [],
                        "user_profile": {"technical_level": "advanced", "domain": "web", "communication_style": "concise"},
                    }))
                elif "question generator" in system.lower():
                    return _gen(json.dumps({"questions": ["What framework?"]}))
                elif "agent team" in system.lower():
                    return _gen(json.dumps({
                        "agents": [{
                            "id": "agent-1", "name": "Dev",
                            "transport": "subprocess", "description": "Dev",
                            "capabilities": ["python"], "max_concurrency": 2,
                        }],
                    }))
                return _gen(json.dumps({"questions": ["More details?"]}))

        engine = RefinementEngine(provider=FullFlowProvider(), max_turns=5)
        questions = await engine.start("I want to build a REST API for managing users")
        assert len(questions) >= 1

        # Answer enough to reach review
        for i in range(5):
            result = await engine.process_answer("Python with FastAPI")
            if isinstance(result, ConversationState):
                break

        spec = await engine.accept()
        assert spec.title  # Has a title
        assert len(spec.deliverables) >= 1
        assert len(spec.agents) >= 1
