"""RefinementEngine — adaptive questioning loop for spec discovery."""

from __future__ import annotations

import json

import structlog

from rooben.planning.provider import LLMProvider
from rooben.refinement.agent_generator import AgentRosterGenerator
from rooben.refinement.prompts import ANSWER_INTEGRATION, GAP_ANALYSIS, QUESTION_GENERATION
from rooben.refinement.spec_builder import SpecBuilder
from rooben.refinement.state import ConversationState, SchemaGap, StructuredQuestion, UserProfile
from rooben.spec.models import Specification
from rooben.utils import parse_llm_json

log = structlog.get_logger()


class LLMUnavailableError(Exception):
    """Raised when LLM provider is unreachable (auth, network, etc.)."""


class RefinementEngine:
    """
    Drives an adaptive questioning loop to gather spec information.

    Flow:
    1. start(initial_description) → first questions
    2. process_answer(answer) → next questions or review state
    3. In review: get_draft_yaml(), accept(), or continue_refining()
    """

    def __init__(
        self,
        provider: LLMProvider,
        max_turns: int = 20,
        extension_context: str = "",
        file_context: str = "",
    ):
        self._provider = provider
        self._max_turns = max_turns
        self._extension_context = extension_context
        self._file_context = file_context
        self._agent_generator = AgentRosterGenerator(provider)
        self._spec_builder = SpecBuilder()
        self._state = ConversationState()
        self._template_workflow_hints: list[dict] = []
        self._last_questions: list[str] = []
        # User-facing schema only — exclude Rooben internals (agent transport,
        # MCP servers, verification config, etc.) so the LLM asks about the
        # *project*, not the orchestration engine.
        self._schema_json: str = repr({
            "title": "string — short project title",
            "goal": "string — what the user wants to achieve",
            "context": "string — background, motivation, or prior art (optional)",
            "deliverables": [
                {"name": "string", "description": "string",
                 "deliverable_type": "code|document|dataset|design|workflow|api|application|infrastructure|other",
                 "output_path": "string — where to write the output (optional)"}
            ],
            "constraints": [
                {"category": "budget|time|technology|security|compliance|performance|other",
                 "description": "string", "hard": "bool — hard constraints cause failure, soft are best-effort"}
            ],
            "acceptance_criteria": [
                {"description": "string — how to verify the deliverable is correct",
                 "priority": "critical|high|medium|low"}
            ],
            "budget": {
                "max_total_tokens": "integer — cap on total LLM tokens (optional, power user)",
                "max_wall_seconds": "integer — max wall-clock time in seconds (optional, power user)",
            },
            "input_sources": [
                {"name": "string — unique name", "type": "mcp|file|url",
                 "integration": "string — e.g. slack, salesforce, google-sheets",
                 "description": "what data is needed",
                 "query": {"key": "value — integration-specific params"},
                 "required": "bool", "pre_fetch": "bool — true for small bounded data, false for large/exploratory"}
            ],
        })
        self._consecutive_llm_failures: int = 0

    @property
    def state(self) -> ConversationState:
        return self._state

    async def start(self, initial_description: str) -> list[StructuredQuestion]:
        """Parse initial input, run gap analysis, return first questions."""
        # Seed gathered info with the initial description
        self._state.gathered_info.goal = initial_description
        self._state.turn_count = 0

        # Run gap analysis
        await self._analyze_gaps()

        # Generate first questions
        questions = await self._generate_questions()
        self._last_questions = questions
        return questions

    async def process_answer(self, answer: str) -> list[StructuredQuestion] | ConversationState:
        """
        Integrate answer, update state, return next questions.

        Returns ConversationState instead of questions when entering review phase.
        """
        self._state.turn_count += 1

        if self._state.turn_count >= self._max_turns:
            self._state.phase = "review"
            return self._state

        # Integrate the answer
        question_context = (
            self._last_questions[0].text if self._last_questions else "General input"
        )
        await self._integrate_answer(question_context, answer)

        # Re-analyze gaps
        await self._analyze_gaps()

        # Phase transition
        if self._state.completeness >= 0.70:
            self._state.phase = "review"
            return self._state
        elif self._state.completeness >= 0.5:
            self._state.phase = "refinement"

        # Generate next questions
        questions = await self._generate_questions()
        self._last_questions = questions
        return questions

    async def get_draft_yaml(self) -> str:
        """Generate a draft YAML spec from gathered info."""
        agents = await self._agent_generator.generate(
            self._state.gathered_info,
            self._state.user_profile,
        )
        spec = self._spec_builder.build(
            self._state.gathered_info, agents,
            workflow_hints=self._template_workflow_hints,
        )
        return self._spec_builder.to_yaml(spec)

    async def accept(self) -> Specification:
        """Accept the current state and produce a validated Specification."""
        agents = await self._agent_generator.generate(
            self._state.gathered_info,
            self._state.user_profile,
        )
        return self._spec_builder.build(
            self._state.gathered_info, agents,
            workflow_hints=self._template_workflow_hints,
        )

    async def continue_refining(self) -> list[StructuredQuestion]:
        """Continue refining after review phase."""
        self._state.phase = "refinement"
        questions = await self._generate_questions()
        self._last_questions = questions
        return questions

    async def _analyze_gaps(self) -> None:
        """Run gap analysis via LLM."""
        # Provide turn-aware guidance to encourage convergence
        turn_ratio = self._state.turn_count / max(self._max_turns, 1)
        if turn_ratio >= 0.6:
            turn_guidance = "We are running low on turns. Focus only on critical missing gaps. Be generous with completeness — if core fields are covered, score 0.75+."
        elif turn_ratio >= 0.3:
            turn_guidance = "Good progress. Focus on the most important remaining gaps."
        else:
            turn_guidance = "Early stage — identify all significant gaps."

        prompt = GAP_ANALYSIS.format(
            schema=self._schema_json[:3000],
            gathered_info=json.dumps(
                self._state.gathered_info.model_dump(), indent=2
            ),
            turn_count=self._state.turn_count,
            max_turns=self._max_turns,
            turn_guidance=turn_guidance,
        )
        # Append uploaded file context so the LLM can factor it into gap analysis
        if self._file_context:
            prompt += f"\n\n## Uploaded Context\n{self._file_context}"

        try:
            gen_result = await self._provider.generate(
                system="You are a specification gap analyzer.",
                prompt=prompt,
                max_tokens=2048,
            )
            data = parse_llm_json(gen_result.text)
            if data:
                # Update gaps
                gaps = []
                for g in data.get("gaps", []):
                    gaps.append(SchemaGap(
                        field_path=g.get("field_path", "unknown"),
                        importance=g.get("importance", 0.5),
                        description=g.get("description", ""),
                    ))
                self._state.schema_gaps = gaps

                # Update completeness
                llm_completeness = data.get(
                    "completeness", self._state.completeness
                )

                # Adaptive floor: prevent completeness from stalling when
                # meaningful information has been gathered across multiple turns
                info = self._state.gathered_info
                has_core = bool(info.goal and info.deliverables)
                turn_ratio = self._state.turn_count / max(self._max_turns, 1)
                if has_core and turn_ratio >= 0.3:
                    # Floor: at least proportional to turns used
                    floor = min(0.6, 0.2 + turn_ratio * 0.6)
                    llm_completeness = max(llm_completeness, floor)

                self._state.completeness = llm_completeness

                # Update user profile
                if "user_profile" in data:
                    up = data["user_profile"]
                    self._state.user_profile = UserProfile(
                        technical_level=up.get("technical_level", "unknown"),
                        domain=up.get("domain", "unknown"),
                        communication_style=up.get("communication_style", "unknown"),
                    )
        except Exception as exc:
            log.warning("refinement.gap_analysis_failed", error=str(exc))
            self._consecutive_llm_failures += 1
            if "authentication" in str(exc).lower() or "api_key" in str(exc).lower() or "auth_token" in str(exc).lower():
                raise LLMUnavailableError(
                    "LLM provider authentication failed. Please configure your API key in Settings."
                ) from exc
            if self._consecutive_llm_failures >= 3:
                raise LLMUnavailableError(
                    "LLM provider is not responding after multiple attempts. Check your API key in Settings."
                ) from exc
            return
        self._consecutive_llm_failures = 0

    async def _generate_questions(self) -> list[StructuredQuestion]:
        """Generate questions via LLM targeting top gaps."""
        unresolved = [g for g in self._state.schema_gaps if not g.resolved]
        unresolved.sort(key=lambda g: g.importance, reverse=True)
        top_gaps = unresolved[:3]

        if not top_gaps:
            return [StructuredQuestion(text="Can you tell me more about what you'd like to build?")]

        gaps_text = "\n".join(
            f"- {g.field_path} (importance: {g.importance}): {g.description}"
            for g in top_gaps
        )

        prompt = QUESTION_GENERATION.format(
            technical_level=self._state.user_profile.technical_level,
            domain=self._state.user_profile.domain,
            communication_style=self._state.user_profile.communication_style,
            gaps=gaps_text,
            phase=self._state.phase,
            available_extensions=self._extension_context,
        )
        if self._file_context:
            prompt += f"\n\n## Uploaded Context\nThe user uploaded files/URLs. Use this to inform your questions:\n{self._file_context}"

        try:
            gen_result = await self._provider.generate(
                system="You are an adaptive question generator.",
                prompt=prompt,
                max_tokens=1024,
            )
            data = parse_llm_json(gen_result.text)
            if data and "questions" in data:
                raw = data["questions"][:3]
                result: list[StructuredQuestion] = []
                for item in raw:
                    if isinstance(item, dict):
                        result.append(StructuredQuestion(
                            text=item.get("text", str(item)),
                            choices=item.get("choices", []),
                            allow_freeform=item.get("allow_freeform", True),
                        ))
                    else:
                        # Backward compat: plain string
                        result.append(StructuredQuestion(text=str(item)))
                return result
            self._consecutive_llm_failures = 0
        except Exception as exc:
            log.warning("refinement.question_generation_failed", error=str(exc))
            self._consecutive_llm_failures += 1
            if "authentication" in str(exc).lower() or "api_key" in str(exc).lower() or "auth_token" in str(exc).lower():
                raise LLMUnavailableError(
                    "LLM provider authentication failed. Please configure your API key in Settings."
                ) from exc

        # Fallback question based on top gap
        return [StructuredQuestion(text=f"Could you provide more details about: {top_gaps[0].description}?")]

    async def _integrate_answer(self, question: str, answer: str) -> None:
        """Integrate user answer via LLM."""
        prompt = ANSWER_INTEGRATION.format(
            gathered_info=json.dumps(
                self._state.gathered_info.model_dump(), indent=2
            ),
            question=question,
            answer=answer,
            gaps=json.dumps(
                [g.model_dump() for g in self._state.schema_gaps], indent=2
            ),
            available_extensions=self._extension_context,
        )
        if self._file_context:
            prompt += f"\n\n## Uploaded Context\nThe user uploaded files/URLs for reference:\n{self._file_context}"

        try:
            gen_result = await self._provider.generate(
                system="You are a specification information integrator.",
                prompt=prompt,
                max_tokens=4096,
            )
            data = parse_llm_json(gen_result.text)
            if data:
                # Update gathered info
                if "gathered_info" in data:
                    gi = data["gathered_info"]
                    info = self._state.gathered_info
                    info.title = gi.get("title", info.title) or info.title
                    info.goal = gi.get("goal", info.goal) or info.goal
                    if gi.get("deliverables"):
                        info.deliverables = gi["deliverables"]
                    if gi.get("constraints"):
                        info.constraints = gi["constraints"]
                    if gi.get("acceptance_criteria"):
                        info.acceptance_criteria = gi["acceptance_criteria"]
                    if gi.get("agents"):
                        info.agents = gi["agents"]
                    if gi.get("input_sources"):
                        info.input_sources = gi["input_sources"]

                # Record the raw answer
                self._state.gathered_info.raw_answers.append({
                    "question": question,
                    "answer": answer,
                    "turn": self._state.turn_count,
                })

                # Resolve gaps
                for path in data.get("resolved_gaps", []):
                    for gap in self._state.schema_gaps:
                        if gap.field_path == path:
                            gap.resolved = True

                # Add new gaps
                for g in data.get("new_gaps", []):
                    self._state.schema_gaps.append(SchemaGap(
                        field_path=g.get("field_path", "unknown"),
                        importance=g.get("importance", 0.5),
                        description=g.get("description", ""),
                    ))

                # Update user profile
                if "user_profile" in data:
                    up = data["user_profile"]
                    self._state.user_profile = UserProfile(
                        technical_level=up.get("technical_level", "unknown"),
                        domain=up.get("domain", "unknown"),
                        communication_style=up.get("communication_style", "unknown"),
                    )

        except Exception as exc:
            log.warning("refinement.integration_failed", error=str(exc))
            # Still record the answer even if integration fails
            self._state.gathered_info.raw_answers.append({
                "question": question,
                "answer": answer,
                "turn": self._state.turn_count,
            })
            self._consecutive_llm_failures += 1
            if "authentication" in str(exc).lower() or "api_key" in str(exc).lower() or "auth_token" in str(exc).lower():
                raise LLMUnavailableError(
                    "LLM provider authentication failed. Please configure your API key in Settings."
                ) from exc
            if self._consecutive_llm_failures >= 3:
                raise LLMUnavailableError(
                    "LLM provider is not responding after multiple attempts. Check your API key in Settings."
                ) from exc
