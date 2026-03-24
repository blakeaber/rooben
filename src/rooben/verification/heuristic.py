"""HeuristicVerifier — fast, no-LLM verification for simple tasks."""

from __future__ import annotations

import structlog

from rooben.domain import Task, TaskResult
from rooben.verification.verifier import VerificationResult

log = structlog.get_logger()


class HeuristicVerifier:
    """Fast rule-based verifier that checks basic output quality signals.

    Checks:
    - Output is non-empty
    - No obvious error indicators in output
    - Artifacts were produced (if expected)
    - Output length is reasonable
    """

    def __init__(self, min_output_length: int = 20):
        self._min_output_length = min_output_length

    async def verify(self, task: Task, result: TaskResult) -> VerificationResult:
        issues: list[str] = []
        score = 1.0

        # Check 1: non-empty output
        output = (result.output or "").strip()
        if not output:
            return VerificationResult(
                passed=False,
                score=0.0,
                feedback="No output was produced.",
                suggested_improvements=["Ensure the agent produces output for this task."],
            )

        # Check 2: explicit error in result
        if result.error:
            return VerificationResult(
                passed=False,
                score=0.1,
                feedback=f"Task produced an error: {result.error[:500]}",
                suggested_improvements=["Fix the error before retrying."],
            )

        # Check 3: output too short
        if len(output) < self._min_output_length:
            issues.append(f"Output is very short ({len(output)} chars).")
            score -= 0.3

        # Check 4: error-like patterns in output
        error_indicators = [
            "Traceback (most recent call last)",
            "Error:",
            "FAILED",
            "Exception:",
            "panic:",
        ]
        for indicator in error_indicators:
            if indicator in output:
                issues.append(f"Output contains error indicator: \"{indicator}\"")
                score -= 0.2
                break

        # Check 5: if task mentions file/artifact creation, check artifacts exist
        artifact_keywords = ("create", "write", "generate", "build", "produce")
        expects_artifacts = any(kw in (task.title + " " + task.description).lower() for kw in artifact_keywords)
        if expects_artifacts and not result.artifacts:
            issues.append("Task likely expected file artifacts but none were produced.")
            score -= 0.2

        score = max(0.0, min(1.0, score))
        passed = score >= 0.5 and not issues

        if passed:
            log.info("heuristic_verifier.passed", task=task.id, score=score)
        else:
            log.info("heuristic_verifier.failed", task=task.id, score=score, issues=issues)

        return VerificationResult(
            passed=passed,
            score=score,
            feedback="; ".join(issues) if issues else "Heuristic checks passed.",
            suggested_improvements=[f"Fix: {i}" for i in issues],
        )
