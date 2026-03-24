"""LLM-based verification — uses a language model to judge task output quality."""

from __future__ import annotations

import structlog

from rooben.domain import Task, TaskResult
from rooben.planning.provider import LLMProvider
from rooben.utils import parse_llm_json
from rooben.verification.verifier import VerificationResult

log = structlog.get_logger()

JUDGE_SYSTEM_PROMPT = """\
You are a quality assurance judge for an autonomous agent system.

Given a task description and the agent's output, evaluate whether the output
satisfies the task requirements.

Output strict JSON:
{
  "passed": true/false,
  "score": 0.0-1.0,
  "feedback": "explanation of pass/fail and any issues found",
  "suggested_improvements": ["specific actionable improvement 1", "improvement 2"]
}

Be strict. Only pass if the output genuinely satisfies the task.
The "suggested_improvements" field should contain specific, actionable suggestions
that would help an agent fix its output on a retry attempt.
Output ONLY the JSON object.
"""


class LLMJudgeVerifier:
    """Uses an LLM to evaluate whether task output meets criteria."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._criteria_map: dict[str, str] = {}

    def set_criteria_map(self, criteria_map: dict[str, str]) -> None:
        """Set acceptance criteria ID→description mapping from the spec."""
        self._criteria_map = criteria_map

    async def verify(self, task: Task, result: TaskResult) -> VerificationResult:
        prompt = self._build_prompt(task, result)

        try:
            gen_result = await self._provider.generate(
                system=JUDGE_SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=2048,
            )
        except Exception as exc:
            log.error("llm_judge.generation_failed", error=str(exc))
            return VerificationResult(
                passed=False,
                score=0.0,
                feedback=f"Verification failed: {exc}",
            )

        # If truncated, retry once with higher token budget
        if gen_result.truncated:
            log.warning("llm_judge.truncated_retry", length=len(gen_result.text))
            try:
                gen_result = await self._provider.generate(
                    system=JUDGE_SYSTEM_PROMPT,
                    prompt=prompt,
                    max_tokens=4096,
                )
            except Exception as exc:
                log.error("llm_judge.retry_failed", error=str(exc))

        data = parse_llm_json(gen_result.text)
        if data is None:
            log.error("llm_judge.parse_failed", raw=gen_result.text[:200])
            return VerificationResult(
                passed=False,
                score=0.0,
                feedback=f"Could not parse judge response: {gen_result.text[:500]}",
            )
        return VerificationResult(
            passed=data.get("passed", False),
            score=data.get("score", 0.0),
            feedback=data.get("feedback", ""),
            suggested_improvements=data.get("suggested_improvements", []),
            verification_tokens=gen_result.usage.total,
            token_usage=gen_result.usage,
            model=gen_result.model,
            provider=gen_result.provider,
        )

    def _build_prompt(self, task: Task, result: TaskResult) -> str:
        parts = [
            f"# Task: {task.title}",
            f"\n## Task Description\n{task.description}",
        ]
        if task.acceptance_criteria_ids:
            if self._criteria_map:
                lines = [f"- **{ac_id}**: {self._criteria_map.get(ac_id, '(description not available)')}"
                         for ac_id in task.acceptance_criteria_ids]
                parts.append("\n## Acceptance Criteria\n" + "\n".join(lines))
            else:
                parts.append(f"\n## Acceptance Criteria IDs\n{', '.join(task.acceptance_criteria_ids)}")
        parts.append(f"\n## Agent Output\n{result.output[:5000]}")
        if result.artifacts:
            parts.append("\n## Artifacts Produced")
            parts.append("NOTE: Artifacts below are PREVIEWS of files written to disk. "
                         "Files may be larger than shown. Do NOT penalize for truncated "
                         "previews — judge based on code quality and structure visible.")
            for name, content in result.artifacts.items():
                # Strip backfill truncation markers for clean display
                clean = content.replace("\n... (truncated)", "")
                line_count = clean.count('\n') + 1
                preview = clean[:200].replace('\n', ' ')
                parts.append(f"- **{name}** ({len(clean)} chars, {line_count} lines): {preview}...")
            # Deep-dive: show up to 15K chars of the 3 largest artifacts.
            # 3K was too aggressive — judges consistently penalized truncated
            # previews despite instructions not to, causing false failures on
            # synthesis tasks (reports, summaries, etc.).
            _JUDGE_ARTIFACT_PREVIEW = 15_000
            top_three = sorted(result.artifacts.items(), key=lambda x: len(x[1]), reverse=True)[:3]
            for name, content in top_three:
                clean = content.replace("\n... (truncated)", "")
                preview = clean[:_JUDGE_ARTIFACT_PREVIEW]
                suffix = "" if len(clean) <= _JUDGE_ARTIFACT_PREVIEW else "\n... (continues)"
                parts.append(f"\n### {name}\n```\n{preview}{suffix}\n```")
        if result.error:
            parts.append(f"\n## Error\n{result.error}")
        return "\n".join(parts)
