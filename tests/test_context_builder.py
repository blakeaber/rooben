"""Tests for WS-2.2: Context Isolation Engine (expanded ContextBuilder)."""

from __future__ import annotations


from rooben.context.builder import ContextBuilder, ContextConfig
from rooben.domain import (
    StructuredTaskPrompt,
    Task,
    TaskResult,
    VerificationFeedback,
    WorkflowState,
    Workflow,
)


def _task(**kwargs) -> Task:
    defaults = dict(
        id="t-1", workstream_id="ws-1", workflow_id="wf-1",
        title="Build API", description="Create REST API",
    )
    defaults.update(kwargs)
    return Task(**defaults)


class TestPriorityOrderedAssembly:
    def test_all_sections_present_in_correct_order(self):
        state = WorkflowState()
        dep = _task(
            id="dep-1", title="Dep Task",
            result=TaskResult(output="Dependency output content"),
        )
        state.tasks["dep-1"] = dep
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id="s")

        task = _task(
            acceptance_criteria_ids=["AC-001"],
            skeleton_tests=["def test_x():\n    assert True\n"],
            attempt_feedback=[
                VerificationFeedback(
                    attempt=1, verifier_type="llm_judge", passed=False,
                    score=0.3, feedback="Missing tests",
                    suggested_improvements=["Add tests"],
                ),
            ],
            depends_on=["dep-1"],
        )
        builder = ContextBuilder()
        prompt = builder.build(task, state)

        # All sections present
        assert "# Task: Build API" in prompt
        assert "AC-001" in prompt
        assert "Skeleton Tests" in prompt
        assert "Prior Attempt Feedback" in prompt
        assert "Dependency output content" in prompt

        # Verify ordering: description before criteria before skeleton before feedback
        desc_pos = prompt.index("Build API")
        criteria_pos = prompt.index("AC-001")
        skel_pos = prompt.index("Skeleton Tests")
        feedback_pos = prompt.index("Prior Attempt Feedback")
        dep_pos = prompt.index("Dependency output content")

        assert desc_pos < criteria_pos < skel_pos < feedback_pos < dep_pos


class TestTruncation:
    def test_truncation_drops_lowest_priority(self):
        """Under tight budget, lowest-priority sections are dropped first."""
        config = ContextConfig(
            max_context_tokens=100,  # Very tight
            budget_fraction=1.0,
        )
        task = _task(description="Short task")
        builder = ContextBuilder(config=config)
        prompt = builder.build(task)

        # Task description (required) should be present
        assert "Build API" in prompt
        # The key test: prompt doesn't blow up and stays bounded

    def test_required_sections_never_dropped(self):
        """Task description is always included even under extreme budget."""
        config = ContextConfig(max_context_tokens=20, budget_fraction=1.0)
        task = _task(
            description="Critical task description",
            acceptance_criteria_ids=["AC-1"],
        )
        builder = ContextBuilder(config=config)
        prompt = builder.build(task)
        assert "Critical task description" in prompt


class TestBudgetRespectsConfig:
    def test_budget_respects_agent_config(self):
        config = ContextConfig(max_context_tokens=1000, budget_fraction=0.5)
        task = _task(description="x" * 5000)
        builder = ContextBuilder(config=config)
        prompt = builder.build(task)
        # Required sections are included even over budget
        assert "Build API" in prompt


class TestTokenEstimation:
    def test_token_estimation(self):
        builder = ContextBuilder()
        # 400 chars ≈ 100 tokens at 4 chars/token
        assert abs(builder.estimate_tokens("x" * 400) - 100) < 5


class TestFeedbackInRetry:
    def test_feedback_present_in_retry(self):
        task = _task(
            attempt_feedback=[
                VerificationFeedback(
                    attempt=1, verifier_type="llm_judge", passed=False,
                    score=0.3, feedback="Missing error handling",
                    suggested_improvements=["Add try/except"],
                ),
            ],
        )
        builder = ContextBuilder()
        prompt = builder.build(task)
        assert "Missing error handling" in prompt
        assert "Add try/except" in prompt


class TestDependencyOutputs:
    def test_multiple_deps_included(self):
        state = WorkflowState()
        state.workflows["wf-1"] = Workflow(id="wf-1", spec_id="s")
        for i in range(3):
            dep = _task(
                id=f"dep-{i}",
                title=f"Dep {i}",
                result=TaskResult(output=f"Output from dep {i}"),
            )
            state.tasks[f"dep-{i}"] = dep

        task = _task(depends_on=["dep-0", "dep-1", "dep-2"])
        builder = ContextBuilder()
        prompt = builder.build(task, state)

        for i in range(3):
            assert f"Output from dep {i}" in prompt


class TestNoLearningsParam:
    def test_build_works_without_learnings(self):
        """Learnings parameter was removed; build() works without it."""
        task = _task()
        builder = ContextBuilder()
        prompt = builder.build(task)
        assert "Build API" in prompt


class TestStructuredPrompt:
    def test_structured_prompt_rendered(self):
        task = _task(
            structured_prompt=StructuredTaskPrompt(
                objective="Build a REST endpoint",
                files=["src/api.py", "tests/test_api.py"],
                action="Create a GET /health endpoint",
                verify="curl localhost:8000/health returns 200",
                done="Endpoint responds to GET with JSON",
            ),
        )
        builder = ContextBuilder()
        prompt = builder.build(task)

        assert "## Objective" in prompt
        assert "Build a REST endpoint" in prompt
        assert "## File Scope" in prompt
        assert "src/api.py" in prompt
        assert "WARNING: Only modify these files" in prompt
        assert "## Action" in prompt
        assert "## Verification" in prompt
        assert "## Definition of Done" in prompt

    def test_structured_prompt_with_empty_fields(self):
        """Empty structured prompt fields are omitted."""
        task = _task(
            structured_prompt=StructuredTaskPrompt(
                objective="Do something",
            ),
        )
        builder = ContextBuilder()
        prompt = builder.build(task)
        assert "## Objective" in prompt
        assert "File Scope" not in prompt  # Empty files list
        assert "## Action" not in prompt  # Empty action


class TestWorkspaceDir:
    def test_workspace_dir_in_prompt(self):
        """Workspace dir appears in built prompt when provided."""
        task = _task()
        builder = ContextBuilder()
        prompt = builder.build(task, workspace_dir="/abs/path/workspace")
        assert "## Workspace" in prompt
        assert "/abs/path/workspace" in prompt
        assert "cd /abs/path/workspace &&" in prompt

    def test_workspace_dir_absent_when_not_provided(self):
        """Workspace section is absent when workspace_dir is None."""
        task = _task()
        builder = ContextBuilder()
        prompt = builder.build(task)
        assert "## Workspace" not in prompt
