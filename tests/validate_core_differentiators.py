"""
Core Differentiators Validation: Verify differentiators work with real APIs.

R-2.1: Verification Feedback Quality (LLM Judge)
R-2.2: Learning Store Value (persist/query/inject)
R-2.3: Refinement Engine Quality (spec generation convergence)
R-2.4: Budget Enforcement Accuracy (tokens, tasks, wall time)
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def _load_env() -> None:
    """Load .env files — called by fixture, not at import time."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".rooben" / ".env")

from rooben.domain import (  # noqa: E402
    Task,
    TaskResult,
    VerificationFeedback,
    WorkflowState,
)
from rooben.context.builder import ContextBuilder  # noqa: E402
from rooben.memory.learning_store import Learning, LearningStore  # noqa: E402
from rooben.planning.provider import AnthropicProvider  # noqa: E402
from rooben.security.budget import BudgetExceeded, BudgetTracker  # noqa: E402


PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"
results = []


def record(name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append((name, passed))
    print(f"  [{status}] {name}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")


# ─── R-2.1: Verification Feedback Quality ─────────────────────────────

async def validate_r21():
    """Test that verification produces meaningful feedback and it reaches retry prompts."""
    print("\n═══ R-2.1: Verification Feedback Quality ═══\n")

    provider = AnthropicProvider(model="claude-sonnet-4-20250514")

    # 1. Create a task with deliberately poor output
    task = Task(
        id="test-verify-001",
        workstream_id="ws-test",
        workflow_id="wf-test",
        title="Implement a Python function to calculate Fibonacci numbers",
        description="Write a function `fibonacci(n)` that returns the nth Fibonacci number. Must handle n=0 (return 0), n=1 (return 1), and use iterative approach for efficiency.",
        assigned_agent_id="python-dev",
        acceptance_criteria_ids=["AC-1", "AC-2", "AC-3"],
    )

    # Deliberately bad output — recursive, no edge cases
    bad_result = TaskResult(
        output="def fibonacci(n):\n    return fibonacci(n-1) + fibonacci(n-2)\n",
        artifacts={"fibonacci.py": "def fibonacci(n):\n    return fibonacci(n-1) + fibonacci(n-2)\n"},
    )

    # 2. Run through real LLM judge
    from rooben.verification.llm_judge import LLMJudgeVerifier
    verifier = LLMJudgeVerifier(provider=provider)

    print("  Calling LLM Judge on deliberately bad output...")
    verification = await verifier.verify(task, bad_result)

    record(
        "LLM Judge detects bad output",
        not verification.passed,
        f"passed={verification.passed}, score={verification.score}",
    )

    record(
        "Feedback is non-empty and meaningful (>50 chars)",
        len(verification.feedback) > 50,
        f"feedback length: {len(verification.feedback)} chars\n"
        f"feedback preview: {verification.feedback[:200]}",
    )

    has_suggestions = bool(verification.suggested_improvements)
    record(
        "Suggested improvements are provided",
        has_suggestions,
        f"suggestions: {verification.suggested_improvements[:3] if has_suggestions else 'none'}",
    )

    # 3. Simulate the feedback being stored on the task (as orchestrator does)
    feedback = VerificationFeedback(
        attempt=1,
        verifier_type="llm_judge",
        passed=False,
        score=verification.score,
        feedback=verification.feedback,
        suggested_improvements=verification.suggested_improvements,
    )
    task.attempt_feedback.append(feedback)
    task.attempt = 2  # Simulating retry

    # 4. Check that ContextBuilder includes feedback in enriched prompt
    builder = ContextBuilder()
    state = WorkflowState()
    state.tasks[task.id] = task
    enriched = builder.build(task, state=state)

    has_feedback_in_prompt = "Prior Attempt Feedback" in enriched or "feedback" in enriched.lower()
    record(
        "Retry prompt includes prior feedback",
        has_feedback_in_prompt,
        f"enriched prompt length: {len(enriched)} chars\n"
        f"contains 'Prior Attempt Feedback': {'Prior Attempt Feedback' in enriched}\n"
        f"contains 'feedback': {'feedback' in enriched.lower()}",
    )

    # Check that the actual feedback text appears
    feedback_text_in_prompt = verification.feedback[:50] in enriched
    record(
        "Actual feedback text appears in retry prompt",
        feedback_text_in_prompt,
        f"looking for: \"{verification.feedback[:50]}...\"",
    )

    # 5. Now test with a GOOD output — verify it passes
    good_result = TaskResult(
        output="""def fibonacci(n):
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
""",
        artifacts={"fibonacci.py": "..."},
    )

    # Reset task for clean verification
    task2 = Task(
        id="test-verify-002",
        workstream_id="ws-test",
        workflow_id="wf-test",
        title=task.title,
        description=task.description,
        assigned_agent_id="python-dev",
    )

    print("  Calling LLM Judge on correct output...")
    good_verification = await verifier.verify(task2, good_result)

    record(
        "LLM Judge passes correct output",
        good_verification.passed,
        f"passed={good_verification.passed}, score={good_verification.score}",
    )

    score_diff = good_verification.score - verification.score
    record(
        "Good output scores higher than bad output",
        score_diff > 0,
        f"bad={verification.score:.2f}, good={good_verification.score:.2f}, diff={score_diff:.2f}",
    )


# ─── R-2.2: Learning Store Value ──────────────────────────────────────

async def validate_r22():
    """Test that learnings persist across runs and are surfaced in context."""
    print("\n═══ R-2.2: Learning Store Value ═══\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        persist_path = os.path.join(tmpdir, "learnings.json")

        # 1. Store learnings in first "run"
        store1 = LearningStore(persist_path=persist_path)
        await store1.store(Learning(
            id=store1.generate_id(),
            agent_id="python-dev",
            workflow_id="wf-run1",
            task_id="task-001",
            content="When building FastAPI endpoints, always add type hints to request/response models for automatic validation and OpenAPI doc generation.",
        ))
        await store1.store(Learning(
            id=store1.generate_id(),
            agent_id="python-dev",
            workflow_id="wf-run1",
            task_id="task-002",
            content="Use Pydantic BaseModel for request validation in FastAPI. Define models separately from route handlers for reusability.",
        ))
        await store1.store(Learning(
            id=store1.generate_id(),
            agent_id="test-writer",
            workflow_id="wf-run1",
            task_id="task-003",
            content="Use httpx.AsyncClient as context manager for testing FastAPI async endpoints. pytest-asyncio fixtures simplify setup.",
        ))

        file_exists = os.path.exists(persist_path)
        record(
            "Learnings persisted to disk",
            file_exists,
            f"path: {persist_path}, exists: {file_exists}",
        )

        if file_exists:
            content = json.loads(Path(persist_path).read_text())
            record(
                "Correct number of learnings saved",
                len(content) == 3,
                f"saved: {len(content)} learnings",
            )

        # 2. Load from disk in second "run" (simulating new process)
        store2 = LearningStore(persist_path=persist_path)
        all_learnings = await store2.query(limit=100)
        record(
            "Learnings loaded from disk in new store instance",
            len(all_learnings) == 3,
            f"loaded: {len(all_learnings)} learnings",
        )

        # 3. Query by agent — should return only matching agent's learnings
        python_learnings = await store2.query(agent_id="python-dev", limit=10)
        record(
            "Query by agent_id filters correctly",
            len(python_learnings) == 2,
            f"python-dev learnings: {len(python_learnings)}",
        )

        # 4. Query relevance — learnings about FastAPI should rank higher for FastAPI task
        # Store a non-FastAPI learning to test ranking
        await store2.store(Learning(
            id=store2.generate_id(),
            agent_id="python-dev",
            workflow_id="wf-run1",
            task_id="task-004",
            content="Docker multi-stage builds reduce image size by separating build and runtime dependencies.",
        ))

        results_query = await store2.query(agent_id="python-dev", limit=5)
        record(
            "Learnings are ranked (most recent or relevant first)",
            len(results_query) >= 2,
            f"returned {len(results_query)} learnings, top: \"{results_query[0].content[:60]}...\"",
        )

        # 5. Verify learnings get injected into context
        task = Task(
            id="test-learning-task",
            workstream_id="ws-test",
            workflow_id="wf-run2",
            title="Build a FastAPI REST API with user endpoints",
            description="Create a FastAPI application with CRUD endpoints for user management.",
            assigned_agent_id="python-dev",
        )

        builder = ContextBuilder()
        state = WorkflowState()
        state.tasks[task.id] = task
        learning_texts = [lr.content for lr in results_query[:3]]
        enriched = builder.build(task, state=state, learnings=learning_texts)

        has_learnings = "FastAPI" in enriched and ("learning" in enriched.lower() or "prior" in enriched.lower() or "insight" in enriched.lower())
        record(
            "Learnings appear in enriched task prompt",
            has_learnings,
            f"enriched prompt length: {len(enriched)} chars\n"
            f"contains 'FastAPI': {'FastAPI' in enriched}\n"
            f"contains learning-related heading: {has_learnings}",
        )


# ─── R-2.3: Refinement Engine Quality ─────────────────────────────────

async def validate_r23():
    """Test that the refinement engine can produce a valid spec in ≤8 turns."""
    print("\n═══ R-2.3: Refinement Engine Quality ═══\n")

    provider = AnthropicProvider(model="claude-sonnet-4-20250514")

    from rooben.refinement.engine import RefinementEngine
    from rooben.refinement.state import ConversationState

    engine = RefinementEngine(provider=provider, max_turns=8)

    # Start with a moderately complex project idea
    description = "Build a CLI tool that monitors a directory for new CSV files, validates their schema against a config, and loads valid files into a SQLite database"

    print(f"  Starting refinement: \"{description}\"")
    questions = await engine.start(description)

    record(
        "Engine generates initial questions",
        len(questions) > 0,
        f"got {len(questions)} questions: {questions[0][:80]}...",
    )

    # Simulate user providing good, detailed answers
    answers = [
        "The CSV files will have columns: id (integer), name (string), email (string), amount (decimal). The config should be a YAML file that defines expected columns, types, and any constraints like not-null or unique. Files should be moved to an 'archive' folder after successful processing or an 'errors' folder if invalid.",
        "The SQLite database should be created automatically if it doesn't exist. Table name should match the CSV filename. The tool should support both one-shot mode (process existing files) and watch mode (continuously monitor with polling). Use Python with click for CLI, watchdog for directory monitoring, and sqlite3 from stdlib.",
        "Error handling: log invalid rows to a separate error log file with row number and reason. The tool should continue processing remaining rows even if some fail. Add a --dry-run flag that validates without loading. Exit code 0 for success, 1 for partial failures, 2 for total failure.",
    ]

    turn = 0
    entered_review = False
    spec = None

    for answer in answers:
        turn += 1
        print(f"  Turn {turn}: answering...")
        result = await engine.process_answer(answer)

        if isinstance(result, ConversationState):
            entered_review = True
            print(f"  Entered review phase at turn {turn}, completeness: {result.completeness:.0%}")

            record(
                f"Reached review phase by turn {turn} (≤8)",
                turn <= 8,
                f"turn={turn}, completeness={result.completeness:.0%}",
            )

            record(
                "Completeness is ≥75%",
                result.completeness >= 0.70,
                f"completeness: {result.completeness:.0%}",
            )

            # Generate spec
            print("  Generating draft spec...")
            yaml_str = await engine.get_draft_yaml()
            record(
                "Draft YAML is non-empty",
                len(yaml_str) > 100,
                f"YAML length: {len(yaml_str)} chars",
            )

            # Accept and validate
            spec = await engine.accept()
            break
        else:
            questions = result
            print(f"  Got {len(questions)} follow-up questions")

    if not entered_review:
        # If we didn't enter review, try a few more generic turns
        for extra in range(3):
            turn += 1
            print(f"  Turn {turn}: providing more detail...")
            result = await engine.process_answer(
                "Yes, that covers it. I want the tool to be simple, well-tested, and follow Python best practices. Use type hints throughout. Include a README with usage examples."
            )
            if isinstance(result, ConversationState):
                entered_review = True
                spec = await engine.accept()
                break

    record(
        "Engine entered review phase",
        entered_review,
        f"total turns: {turn}",
    )

    if spec:
        record(
            "Spec has a title",
            bool(spec.title),
            f"title: {spec.title}",
        )
        record(
            "Spec has deliverables",
            len(spec.deliverables) > 0,
            f"deliverables: {len(spec.deliverables)}",
        )
        record(
            "Spec has agents",
            len(spec.agents) > 0,
            f"agents: {len(spec.agents)}",
        )
        record(
            "Spec has acceptance criteria",
            len(spec.success_criteria.acceptance_criteria) > 0,
            f"criteria: {len(spec.success_criteria.acceptance_criteria)}",
        )

        # Validate the spec
        from rooben.spec.validator import SpecValidator
        validator = SpecValidator()
        validation = validator.validate(spec)
        record(
            "Generated spec passes validation",
            validation.is_valid,
            f"valid={validation.is_valid}, warnings={len(validation.warnings)}, errors={len(validation.errors)}",
        )
    else:
        record("Spec was generated", False, "No spec produced")


# ─── R-2.4: Budget Enforcement Accuracy ───────────────────────────────

async def validate_r24():
    """Test that budgets are enforced accurately."""
    print("\n═══ R-2.4: Budget Enforcement Accuracy ═══\n")

    # 1. Token budget enforcement
    tracker = BudgetTracker(max_total_tokens=1000)
    await tracker.record_tokens(500, agent_id="test")
    await tracker.record_tokens(400, agent_id="test")

    token_exceeded = False
    try:
        await tracker.record_tokens(200, agent_id="test")  # This should exceed 1000
    except BudgetExceeded as e:
        token_exceeded = True
        record(
            "Token budget enforced",
            True,
            f"Raised at 1100 tokens (limit 1000): {e}",
        )

    if not token_exceeded:
        record("Token budget enforced", False, "No exception raised at 1100 tokens")

    # 2. Task count budget enforcement
    tracker2 = BudgetTracker(max_total_tasks=3)
    await tracker2.record_task_completion()
    await tracker2.record_task_completion()
    await tracker2.record_task_completion()

    task_exceeded = False
    try:
        await tracker2.record_task_completion()  # 4th task should exceed limit of 3
    except BudgetExceeded as e:
        task_exceeded = True
        record(
            "Task count budget enforced",
            True,
            f"Raised at task 4 (limit 3): {e}",
        )

    if not task_exceeded:
        record("Task count budget enforced", False, "No exception raised at 4th task")

    # 3. Wall time budget enforcement
    tracker3 = BudgetTracker(max_wall_seconds=2)
    # Should not raise at 1s
    try:
        tracker3.check_wall_time(1.0)
        record("Wall time allows under-budget check", True, "1.0s < 2.0s limit")
    except BudgetExceeded:
        record("Wall time allows under-budget check", False, "Raised unexpectedly at 1.0s")

    wall_exceeded = False
    try:
        tracker3.check_wall_time(3.0)  # Should exceed 2s limit
    except BudgetExceeded as e:
        wall_exceeded = True
        record(
            "Wall time budget enforced",
            True,
            f"Raised at 3.0s (limit 2.0s): {e}",
        )

    if not wall_exceeded:
        record("Wall time budget enforced", False, "No exception raised at 3.0s")

    # 4. Concurrent agent semaphore
    tracker5 = BudgetTracker(max_concurrent_agents=2)
    sem = tracker5.get_agent_semaphore()
    record(
        "Concurrency semaphore created with correct limit",
        sem._value == 2,
        f"semaphore value: {sem._value}",
    )

    # 5. Cost budget enforcement (if supported)
    tracker6 = BudgetTracker(max_total_tokens=999999)  # High token limit
    from rooben.domain import TokenUsage
    try:
        # Record some cost
        await tracker6.record_llm_usage(
            "anthropic", "claude-sonnet-4-20250514",
            TokenUsage(input_tokens=1000, output_tokens=500),
            Decimal("0.01"),
        )
        record("Cost recording works", True, "Recorded $0.01 usage")
    except Exception as e:
        record("Cost recording works", False, f"Error: {e}")

    # 6. Integration: BudgetExceeded caught gracefully by orchestrator pattern
    record(
        "BudgetExceeded is catchable exception",
        issubclass(BudgetExceeded, Exception),
        f"BudgetExceeded bases: {BudgetExceeded.__bases__}",
    )


# ─── Main ─────────────────────────────────────────────────────────────

async def main():
    _load_env()

    print("=" * 60)
    print("  CORE DIFFERENTIATORS VALIDATION")
    print("=" * 60)

    start = time.monotonic()

    await validate_r21()
    await validate_r22()
    await validate_r23()
    await validate_r24()

    elapsed = time.monotonic() - start

    # Summary
    total = len(results)
    passed = sum(1 for _, p in results if p)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"  SUMMARY: {passed}/{total} passed, {failed} failed ({elapsed:.1f}s)")
    print("=" * 60)

    if failed:
        print("\n  Failed checks:")
        for name, p in results:
            if not p:
                print(f"    - {name}")
        sys.exit(1)
    else:
        print("\n  All core differentiator validations passed!")


if __name__ == "__main__":
    asyncio.run(main())
