"""TieredVerifier — routes tasks to heuristic or LLM-based verification."""

from __future__ import annotations

import structlog

from rooben.domain import Task, TaskResult
from rooben.verification.heuristic import HeuristicVerifier
from rooben.verification.verifier import Verifier, VerificationResult

log = structlog.get_logger()

# Keywords that signal a task requires deeper (LLM) evaluation
_COMPLEX_KEYWORDS = (
    "analyze", "evaluate", "compare", "synthesize", "review",
    "assess", "critique", "design", "architect", "optimize",
    "recommend", "investigate", "debug", "refactor",
)


class TieredVerifier:
    """Routes verification to heuristic or LLM judge based on task complexity.

    Simple tasks (single criterion, straightforward output) get fast heuristic
    checks. Complex tasks (multiple criteria, analytical work) go to the LLM
    judge. Heuristic failures escalate to LLM judge to avoid false negatives.
    """

    def __init__(self, heuristic: HeuristicVerifier, llm_judge: Verifier):
        self._heuristic = heuristic
        self._llm_judge = llm_judge

    def set_criteria_map(self, criteria_map: dict[str, str]) -> None:
        """Propagate acceptance criteria map to inner LLM judge."""
        if hasattr(self._llm_judge, 'set_criteria_map'):
            self._llm_judge.set_criteria_map(criteria_map)

    async def verify(self, task: Task, result: TaskResult) -> VerificationResult:
        if self._is_complex(task):
            log.info("tiered_verifier.llm_route", task=task.id, reason="complex")
            return await self._llm_judge.verify(task, result)

        # Try heuristic first
        heuristic_result = await self._heuristic.verify(task, result)

        if heuristic_result.passed:
            log.info("tiered_verifier.heuristic_pass", task=task.id, score=heuristic_result.score)
            return heuristic_result

        # Heuristic failed — escalate to LLM judge to avoid false negatives
        log.info(
            "tiered_verifier.escalate",
            task=task.id,
            heuristic_score=heuristic_result.score,
            heuristic_feedback=heuristic_result.feedback[:200],
        )
        return await self._llm_judge.verify(task, result)

    def _is_complex(self, task: Task) -> bool:
        """Determine if a task needs LLM-level verification."""
        # Multiple acceptance criteria → complex
        if task.acceptance_criteria_ids and len(task.acceptance_criteria_ids) > 1:
            return True

        # Analytical keywords in title or description → complex
        text = (task.title + " " + task.description).lower()
        if any(kw in text for kw in _COMPLEX_KEYWORDS):
            return True

        return False
