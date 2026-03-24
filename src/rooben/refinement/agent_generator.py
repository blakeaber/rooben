"""Agent roster generator — LLM-based with fallback templates."""

from __future__ import annotations

import json

import structlog

from rooben.planning.provider import LLMProvider
from rooben.refinement.prompts import AGENT_GENERATION
from rooben.refinement.state import GatheredInfo, UserProfile
from rooben.spec.models import AgentSpec, AgentTransport
from rooben.utils import parse_llm_json

log = structlog.get_logger()

# Fallback templates for common patterns
FALLBACK_AGENTS = [
    AgentSpec(
        id="agent-dev",
        name="Developer",
        transport=AgentTransport.LLM,
        description="General-purpose software development agent",
        endpoint="",
        capabilities=["python", "javascript", "testing"],
        max_concurrency=2,
    ),
]


class AgentRosterGenerator:
    """Generates an optimal agent team from gathered project info."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def generate(
        self,
        gathered_info: GatheredInfo,
        user_profile: UserProfile,
    ) -> list[AgentSpec]:
        """Generate agent roster via LLM, falling back to templates on error."""
        try:
            prompt = AGENT_GENERATION.format(
                gathered_info=json.dumps(gathered_info.model_dump(), indent=2),
            )

            # Check extension agent presets first
            try:
                from rooben.extensions.loader import load_all_extensions
                from rooben.extensions.manifest import ExtensionType

                ext_agents = [m for m in load_all_extensions() if m.type == ExtensionType.AGENT]
                if ext_agents:
                    # Build a hint for the LLM about available agent presets
                    ext_hint = "\n\nAvailable agent presets from extensions:\n"
                    for ea in ext_agents:
                        ext_hint += f"- {ea.name}: {ea.description} (capabilities: {', '.join(ea.capabilities)})\n"
                    # Append to prompt so LLM knows about available presets
                    prompt += ext_hint
            except Exception:
                pass  # Extension system is optional

            gen_result = await self._provider.generate(
                system="You are an agent team architect.",
                prompt=prompt,
                max_tokens=4096,
            )
            data = parse_llm_json(gen_result.text)
            if data and "agents" in data:
                agents = []
                for a in data["agents"]:
                    try:
                        agents.append(AgentSpec.model_validate(a))
                    except Exception:
                        continue
                if agents:
                    return agents
        except Exception as exc:
            log.warning("agent_generator.llm_failed", error=str(exc))

        return list(FALLBACK_AGENTS)
