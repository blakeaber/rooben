"""ExtensionBuilderEngine — adaptive questioning loop for creating extensions."""

from __future__ import annotations

import json

import structlog

from rooben.extensions.builder_prompts import (
    EXT_ANSWER_INTEGRATION,
    EXT_GAP_ANALYSIS,
    EXT_QUESTION_GENERATION,
)
from rooben.extensions.builder_state import (
    ExtensionBuilderQuestion,
    ExtensionBuilderState,
    ExtensionGap,
)
from rooben.planning.provider import LLMProvider
from rooben.utils import parse_llm_json

log = structlog.get_logger()

DISPLAY_TYPE_MAP = {
    "integration": "Data Source",
    "template": "Template",
    "agent": "Agent",
}


class ExtensionBuilderEngine:
    """
    Drives an adaptive questioning loop to gather extension information.

    Flow:
    1. start(description, type_hint?) → first questions + detected type
    2. process_answer(answer) → next questions or review state
    3. get_draft() → manifest dict preview
    4. accept() → validated manifest dict for installation
    """

    def __init__(self, provider: LLMProvider, max_turns: int = 10):
        self._provider = provider
        self._max_turns = max_turns
        self._state = ExtensionBuilderState()
        self._last_questions: list[ExtensionBuilderQuestion] = []
        self._consecutive_llm_failures: int = 0

    @property
    def state(self) -> ExtensionBuilderState:
        return self._state

    async def start(
        self, description: str, type_hint: str | None = None
    ) -> list[ExtensionBuilderQuestion]:
        """Parse initial input, detect type, return first questions."""
        self._state.gathered_info.description = description
        if type_hint:
            self._state.gathered_info.type = type_hint
            self._state.detected_type = type_hint
        self._state.turn_count = 0

        await self._analyze_gaps()

        # Use detected type from gap analysis if not provided
        if not self._state.gathered_info.type and self._state.detected_type:
            self._state.gathered_info.type = self._state.detected_type

        questions = await self._generate_questions()
        self._last_questions = questions
        return questions

    async def process_answer(
        self, answer: str
    ) -> list[ExtensionBuilderQuestion] | ExtensionBuilderState:
        """Integrate answer, return next questions or review state."""
        self._state.turn_count += 1

        if self._state.turn_count >= self._max_turns:
            self._state.phase = "review"
            return self._state

        question_context = (
            self._last_questions[0].text if self._last_questions else "General input"
        )
        await self._integrate_answer(question_context, answer)
        await self._analyze_gaps()

        if self._state.completeness >= 0.70:
            self._state.phase = "review"
            return self._state
        elif self._state.completeness >= 0.5:
            self._state.phase = "refinement"

        questions = await self._generate_questions()
        self._last_questions = questions
        return questions

    def get_draft(self) -> dict:
        """Generate a manifest dict from gathered info."""
        info = self._state.gathered_info
        ext_type = info.type or self._state.detected_type or "template"

        manifest = {
            "schema_version": 1,
            "name": info.name or _slugify(info.description),
            "type": ext_type,
            "version": "1.0.0",
            "author": "",
            "license": "MIT",
            "description": info.description,
            "tags": info.tags,
            "domain_tags": info.domain_tags,
            "category": info.category or "professional",
            "use_cases": info.use_cases,
            "min_rooben_version": "0.1.0",
        }

        if ext_type == "integration":
            manifest["cost_tier"] = info.cost_tier
            manifest["required_env"] = info.required_env
            manifest["servers"] = info.servers
        elif ext_type == "template":
            manifest["prefill"] = info.prefill
            manifest["requires"] = info.requires
        elif ext_type == "agent":
            manifest["capabilities"] = info.capabilities
            manifest["prompt_template"] = info.prompt_template
            manifest["model_override"] = info.model_override
            manifest["integration"] = info.integration

        return manifest

    async def _analyze_gaps(self) -> None:
        """Run gap analysis via LLM."""
        turn_ratio = self._state.turn_count / max(self._max_turns, 1)
        if turn_ratio >= 0.6:
            turn_guidance = "Running low on turns. Focus on critical gaps only. Be generous with completeness."
        elif turn_ratio >= 0.3:
            turn_guidance = "Good progress. Focus on the most important remaining gaps."
        else:
            turn_guidance = "Early stage — identify all significant gaps."

        prompt = EXT_GAP_ANALYSIS.format(
            gathered_info=json.dumps(self._state.gathered_info.model_dump(), indent=2),
            turn_count=self._state.turn_count,
            max_turns=self._max_turns,
            turn_guidance=turn_guidance,
        )
        try:
            result = await self._provider.generate(
                system="You are an extension specification gap analyzer.",
                prompt=prompt,
                max_tokens=2048,
            )
            data = parse_llm_json(result.text)
            if data:
                if "detected_type" in data and not self._state.detected_type:
                    self._state.detected_type = data["detected_type"]
                    if not self._state.gathered_info.type:
                        self._state.gathered_info.type = data["detected_type"]

                gaps = []
                for g in data.get("gaps", []):
                    gaps.append(ExtensionGap(
                        field_path=g.get("field_path", "unknown"),
                        importance=g.get("importance", 0.5),
                        description=g.get("description", ""),
                    ))
                self._state.gaps = gaps

                llm_completeness = data.get("completeness", self._state.completeness)
                # Adaptive floor
                info = self._state.gathered_info
                has_core = bool(info.description and info.type)
                if has_core and turn_ratio >= 0.3:
                    floor = min(0.6, 0.2 + turn_ratio * 0.6)
                    llm_completeness = max(llm_completeness, floor)
                self._state.completeness = llm_completeness

        except Exception as exc:
            log.warning("builder.gap_analysis_failed", error=str(exc))
            self._consecutive_llm_failures += 1
            if self._consecutive_llm_failures >= 3:
                # Force review to avoid infinite loop
                self._state.phase = "review"

    async def _generate_questions(self) -> list[ExtensionBuilderQuestion]:
        """Generate questions targeting top gaps."""
        unresolved = [g for g in self._state.gaps if not g.resolved]
        unresolved.sort(key=lambda g: g.importance, reverse=True)
        top_gaps = unresolved[:3]

        if not top_gaps:
            return [ExtensionBuilderQuestion(
                text="Can you tell me more about what you'd like to create?"
            )]

        ext_type = self._state.gathered_info.type or self._state.detected_type or "template"
        display_type = DISPLAY_TYPE_MAP.get(ext_type, "Extension")

        gaps_text = "\n".join(
            f"- {g.field_path} (importance: {g.importance}): {g.description}"
            for g in top_gaps
        )

        prompt = EXT_QUESTION_GENERATION.format(
            extension_type=ext_type,
            display_type=display_type,
            gaps=gaps_text,
            phase=self._state.phase,
        )
        try:
            result = await self._provider.generate(
                system="You are an adaptive question generator for extension creation.",
                prompt=prompt,
                max_tokens=1024,
            )
            data = parse_llm_json(result.text)
            if data and "questions" in data:
                questions: list[ExtensionBuilderQuestion] = []
                for item in data["questions"][:3]:
                    if isinstance(item, dict):
                        questions.append(ExtensionBuilderQuestion(
                            text=item.get("text", str(item)),
                            choices=item.get("choices", []),
                            allow_freeform=item.get("allow_freeform", True),
                        ))
                    else:
                        questions.append(ExtensionBuilderQuestion(text=str(item)))
                return questions
        except Exception as exc:
            log.warning("builder.question_generation_failed", error=str(exc))
            self._consecutive_llm_failures += 1

        return [ExtensionBuilderQuestion(
            text=f"Could you provide more details about: {top_gaps[0].description}?"
        )]

    async def _integrate_answer(self, question: str, answer: str) -> None:
        """Integrate user answer into gathered info."""
        ext_type = self._state.gathered_info.type or self._state.detected_type or "template"

        prompt = EXT_ANSWER_INTEGRATION.format(
            extension_type=ext_type,
            gathered_info=json.dumps(self._state.gathered_info.model_dump(), indent=2),
            question=question,
            answer=answer,
            gaps=json.dumps([g.model_dump() for g in self._state.gaps], indent=2),
        )
        try:
            result = await self._provider.generate(
                system="You are an extension specification information integrator.",
                prompt=prompt,
                max_tokens=4096,
            )
            data = parse_llm_json(result.text)
            if data and "gathered_info" in data:
                gi = data["gathered_info"]
                info = self._state.gathered_info
                info.name = gi.get("name", info.name) or info.name
                info.type = gi.get("type", info.type) or info.type
                info.description = gi.get("description", info.description) or info.description
                if gi.get("tags"):
                    info.tags = gi["tags"]
                if gi.get("domain_tags"):
                    info.domain_tags = gi["domain_tags"]
                info.category = gi.get("category", info.category) or info.category
                if gi.get("use_cases"):
                    info.use_cases = gi["use_cases"]
                # Type-specific
                if gi.get("servers"):
                    info.servers = gi["servers"]
                if gi.get("required_env"):
                    info.required_env = gi["required_env"]
                if gi.get("cost_tier") is not None:
                    info.cost_tier = gi["cost_tier"]
                if gi.get("prefill"):
                    info.prefill = gi["prefill"]
                if gi.get("requires"):
                    info.requires = gi["requires"]
                if gi.get("capabilities"):
                    info.capabilities = gi["capabilities"]
                if gi.get("prompt_template"):
                    info.prompt_template = gi["prompt_template"]
                if gi.get("model_override"):
                    info.model_override = gi["model_override"]
                if gi.get("integration"):
                    info.integration = gi["integration"]

                # Resolve/add gaps
                for path in data.get("resolved_gaps", []):
                    for gap in self._state.gaps:
                        if gap.field_path == path:
                            gap.resolved = True
                for g in data.get("new_gaps", []):
                    self._state.gaps.append(ExtensionGap(
                        field_path=g.get("field_path", "unknown"),
                        importance=g.get("importance", 0.5),
                        description=g.get("description", ""),
                    ))

        except Exception as exc:
            log.warning("builder.integration_failed", error=str(exc))
            self._consecutive_llm_failures += 1

        # Always record the raw answer
        self._state.gathered_info.raw_answers.append({
            "question": question,
            "answer": answer,
            "turn": self._state.turn_count,
        })


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:40].strip("-") or "custom-extension"
