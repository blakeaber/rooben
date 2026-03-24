"""Test runner verifier — executes generated tests in a sandbox."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

import structlog

from rooben.domain import Task, TaskResult, TestCaseResult
from rooben.verification.verifier import VerificationResult

log = structlog.get_logger()


class TestRunnerVerifier:
    """
    Runs generated tests (from skeleton_tests and agent-generated tests)
    in an isolated temporary directory.

    Supports pytest for backend tests and can be extended for Playwright.
    """

    def __init__(self, timeout: int = 120):
        self._timeout = timeout

    async def verify(self, task: Task, result: TaskResult) -> VerificationResult:
        if not result.generated_tests and not task.skeleton_tests:
            return VerificationResult(
                passed=True,
                score=1.0,
                feedback="No tests to run — passed by default.",
            )

        with tempfile.TemporaryDirectory(prefix="rooben_test_") as tmpdir:
            tmp = Path(tmpdir)

            # Write artifacts (the code being tested)
            for name, content in result.artifacts.items():
                filepath = tmp / name
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content, encoding="utf-8")

            # Write generated tests
            test_files: list[str] = []
            for gt in result.generated_tests:
                filepath = tmp / gt.filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(gt.content, encoding="utf-8")
                test_files.append(gt.filename)

            # Write skeleton tests
            for i, skeleton in enumerate(task.skeleton_tests):
                filename = f"test_skeleton_{i}.py"
                (tmp / filename).write_text(skeleton, encoding="utf-8")
                test_files.append(filename)

            if not test_files:
                return VerificationResult(passed=True, score=1.0, feedback="No test files.")

            # Run pytest
            return await self._run_pytest(tmp, test_files)

    async def _run_pytest(self, workdir: Path, test_files: list[str]) -> VerificationResult:
        cmd = ["python", "-m", "pytest", "-v", "--tb=short", "--no-header"]
        cmd.extend(test_files)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            return VerificationResult(
                passed=False,
                score=0.0,
                feedback=f"Tests timed out after {self._timeout}s",
            )

        output = stdout.decode()
        passed = proc.returncode == 0
        test_results = self._parse_test_results(output)
        failed_tests = [tr.name for tr in test_results if not tr.passed]

        # Calculate score from structured results
        total = len(test_results) if test_results else 1
        passed_count = sum(1 for tr in test_results if tr.passed)
        score = passed_count / max(total, 1)

        return VerificationResult(
            passed=passed,
            score=score,
            feedback=output[-3000:] if not passed else "All tests passed.",
            failed_tests=failed_tests,
            test_results=test_results,
        )

    def _parse_test_results(self, output: str) -> list[TestCaseResult]:
        """Parse pytest -v output into structured TestCaseResult objects."""
        results: list[TestCaseResult] = []
        # Match lines like: test_file.py::test_name PASSED
        # or: test_file.py::TestClass::test_name FAILED
        pattern = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)", re.MULTILINE)

        for match in pattern.finditer(output):
            test_name = match.group(1).strip()
            status = match.group(2)
            error_msg = ""

            if status == "FAILED":
                # Try to find the error message for this test
                error_msg = self._extract_error_for_test(output, test_name)

            results.append(TestCaseResult(
                name=test_name,
                passed=status == "PASSED",
                error_message=error_msg,
            ))

        return results

    def _extract_error_for_test(self, output: str, test_name: str) -> str:
        """Extract the error message for a specific failed test from pytest output."""
        # Look for the FAILURES section and find the relevant test
        # pytest short tb format: "FAILED test_name - ErrorType: message"
        short_pattern = re.compile(
            rf"FAILED\s+{re.escape(test_name)}\s*-\s*(.+)", re.MULTILINE
        )
        match = short_pattern.search(output)
        if match:
            return match.group(1).strip()[:500]
        return ""
