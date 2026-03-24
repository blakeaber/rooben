"""Verifier protocol, result model, and ChainedVerifier."""

from __future__ import annotations

from typing import Protocol

import structlog
from pydantic import BaseModel, Field

from rooben.domain import Task, TaskResult, TestCaseResult, TokenUsage

log = structlog.get_logger()


class VerificationResult(BaseModel):
    """Outcome of verifying a task's output."""
    passed: bool
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    feedback: str = ""
    failed_tests: list[str] = Field(default_factory=list)
    suggested_improvements: list[str] = Field(default_factory=list)
    test_results: list[TestCaseResult] = Field(default_factory=list)
    verification_tokens: int = 0
    token_usage: TokenUsage | None = None
    model: str = ""
    provider: str = ""


class Verifier(Protocol):
    """Verifies that a task's output meets its acceptance criteria."""

    async def verify(self, task: Task, result: TaskResult) -> VerificationResult:
        """Verify a task result. Returns pass/fail with optional feedback."""
        ...


class ChainedVerifier:
    """
    Runs multiple verifiers in sequence. Short-circuits on first failure.
    Merges results from all verifiers that ran.
    """

    def __init__(self, verifiers: list[Verifier]):
        if not verifiers:
            raise ValueError("ChainedVerifier requires at least one verifier")
        self._verifiers = verifiers

    def set_criteria_map(self, criteria_map: dict[str, str]) -> None:
        """Propagate acceptance criteria map to inner verifiers."""
        for v in self._verifiers:
            if hasattr(v, 'set_criteria_map'):
                v.set_criteria_map(criteria_map)

    async def verify(self, task: Task, result: TaskResult) -> VerificationResult:
        all_feedback: list[str] = []
        all_failed_tests: list[str] = []
        all_improvements: list[str] = []
        all_test_results: list[TestCaseResult] = []
        total_tokens = 0
        min_score = 1.0

        for verifier in self._verifiers:
            vr = await verifier.verify(task, result)
            total_tokens += vr.verification_tokens

            if vr.feedback:
                all_feedback.append(vr.feedback)
            all_failed_tests.extend(vr.failed_tests)
            all_improvements.extend(vr.suggested_improvements)
            all_test_results.extend(vr.test_results)
            min_score = min(min_score, vr.score)

            if not vr.passed:
                log.info(
                    "chained_verifier.short_circuit",
                    verifier=type(verifier).__name__,
                    feedback=vr.feedback[:200],
                )
                return VerificationResult(
                    passed=False,
                    score=min_score,
                    feedback="\n---\n".join(all_feedback),
                    failed_tests=all_failed_tests,
                    suggested_improvements=all_improvements,
                    test_results=all_test_results,
                    verification_tokens=total_tokens,
                )

        return VerificationResult(
            passed=True,
            score=min_score,
            feedback="\n---\n".join(all_feedback),
            failed_tests=all_failed_tests,
            suggested_improvements=all_improvements,
            test_results=all_test_results,
            verification_tokens=total_tokens,
        )
