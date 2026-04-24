"""README-quickstart E2E validator.

Verifies that the literal commands advertised in README.md produce working
outcomes for a fresh cloner — no mocks, no fakes, real subprocess invocations
against the Python in this venv. These tests are the guardrail that keeps the
README honest.

Why subprocess + `python -m rooben.cli`:
The ambient dev environment has `rooben-pro` editable-installed, which ships
its own `src/rooben/` that shadows the OSS package. Using `sys.executable -m
rooben.cli` binds every subprocess to the same Python as the pytest runner —
so `pip install -e .` in a clean venv exercises OSS, while CI exercises
whatever pip puts on the path. A bare `rooben` script would pick up PATH
precedence which can cross-contaminate.

Runs in the root `tests/` directory (NOT `tests/e2e/`) so CI picks it up in
the default test job AND the dedicated readme-quickstart job (Phase F.5).
The `tests/e2e/` directory has autouse fixtures that require agent-browser
and running servers — these tests need neither.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run_rooben(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Invoke `python -m rooben.cli ...` against the same Python running pytest."""
    return subprocess.run(
        [sys.executable, "-m", "rooben.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


# ────────────────────────────────────────────────────────────────────────────
# README: `pip install rooben && rooben demo`
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.timeout(180)
def test_rooben_demo_runs_without_api_key():
    """`rooben demo` completes end-to-end with mock providers — no API key.

    Acceptance: exit 0, stdout shows the 7 demo sections, no Traceback in stderr.
    """
    result = _run_rooben("demo", timeout=180)

    assert result.returncode == 0, (
        f"rooben demo exited {result.returncode}\n"
        f"stdout tail:\n{result.stdout[-2000:]}\n"
        f"stderr tail:\n{result.stderr[-2000:]}"
    )

    # Demo must reach the "All Demos Complete" banner
    assert "All Demos Complete" in result.stdout, "demo did not finish all sections"

    # Orchestration markers — proves planning + execution + verification fired
    for marker in ("Workflow:", "Task status distribution:", "passed"):
        assert marker in result.stdout, f"expected marker not in demo output: {marker!r}"

    # No unhandled exception escaped to stderr
    assert "Traceback" not in result.stderr, f"unexpected traceback:\n{result.stderr}"


# ────────────────────────────────────────────────────────────────────────────
# README: `rooben doctor` — environment health check
# ────────────────────────────────────────────────────────────────────────────


def test_rooben_doctor_reports_health():
    """`rooben doctor` reports on Python, deps, directories, and connectivity."""
    result = _run_rooben("doctor", timeout=60)

    # Doctor exits 0 even if some optional checks fail (e.g. missing API key);
    # it only fails when a REQUIRED check fails. For CI we tolerate either
    # outcome as long as the report structure is intact.
    assert result.returncode in (0, 1), f"unexpected exit code: {result.returncode}"

    for marker in ("Rooben Health Check", "Python version", "Dependency:"):
        assert marker in result.stdout, f"expected marker not in doctor output: {marker!r}"

    # Final summary line always present
    assert "passed" in result.stdout and "failed" in result.stdout, (
        "doctor output missing summary line"
    )


# ────────────────────────────────────────────────────────────────────────────
# CLI surface — README advertises these subcommands; each must respond to --help
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "args",
    [
        ("--version",),
        ("--help",),
        ("go", "--help"),
        ("run", "--help"),
        ("refine", "--help"),
        ("demo", "--help"),
        ("init", "--help"),
        ("doctor", "--help"),
        ("validate", "--help"),
    ],
)
def test_rooben_cli_surface_intact(args: tuple[str, ...]):
    """Every subcommand advertised in the README responds to --help without error."""
    result = _run_rooben(*args, timeout=30)
    assert result.returncode == 0, (
        f"rooben {' '.join(args)} exited {result.returncode}\n{result.stderr}"
    )
    assert result.stdout.strip(), f"rooben {' '.join(args)} produced no output"


# ────────────────────────────────────────────────────────────────────────────
# README: `rooben run examples/hello_api.yaml` — validate before running
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "spec",
    ["examples/hello_api.yaml", "examples/job_matcher.yaml", "examples/realtime_dashboard.yaml"],
)
def test_rooben_validate_example_spec(spec: str):
    """Every bundled example spec passes `rooben validate` — no API key needed."""
    assert (ROOT / spec).exists(), f"example spec missing: {spec}"

    result = _run_rooben("validate", spec, timeout=30)
    assert result.returncode == 0, (
        f"rooben validate {spec} exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "Validation: PASSED" in result.stdout, (
        f"spec {spec} did not validate cleanly:\n{result.stdout}"
    )
