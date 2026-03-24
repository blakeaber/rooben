"""ContextBuilder — assembles priority-ordered, budget-aware task prompts."""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

from rooben.domain import Task, WorkflowState


@dataclass
class ContextConfig:
    """Configuration for context assembly."""
    max_context_tokens: int = 200000
    budget_fraction: float = 0.5  # Use up to 50% of agent's context window
    chars_per_token: float = 4.0  # Rough estimate for token counting

    @property
    def token_budget(self) -> int:
        return int(self.max_context_tokens * self.budget_fraction)


# Section priorities (lower number = higher priority, kept first under truncation)
PRIORITY_TASK_DESCRIPTION = 1
PRIORITY_ACCEPTANCE_CRITERIA = 2
PRIORITY_INPUT_SOURCES = 3
PRIORITY_SKELETON_TESTS = 4
PRIORITY_ATTEMPT_FEEDBACK = 5
PRIORITY_DEPENDENCY_OUTPUTS = 6
PRIORITY_CODEBASE_CONTEXT = 7


@dataclass
class _Section:
    """A single section of the assembled prompt."""
    priority: int
    label: str
    content: str
    required: bool = False  # Required sections are never truncated

    @property
    def estimated_tokens(self) -> int:
        return max(1, len(self.content) // 4)


class ContextBuilder:
    """
    Assembles a prompt for an agent from a task, its verification feedback,
    and dependency outputs.

    Sections are priority-ordered. Under token budget pressure, lowest-priority
    sections are truncated or dropped first.
    """

    def __init__(self, config: ContextConfig | None = None):
        self._config = config or ContextConfig()

    def build(
        self,
        task: Task,
        state: WorkflowState | None = None,
        codebase_context: str | None = None,
        workspace_dir: str | None = None,
        criteria_map: dict[str, str] | None = None,
    ) -> str:
        """Build a context-rich prompt for the given task."""
        sections = self._collect_sections(task, state, codebase_context, workspace_dir, criteria_map)

        # Sort by priority (lower = higher importance)
        sections.sort(key=lambda s: s.priority)

        # Fit within budget
        budget = self._config.token_budget
        return self._assemble_within_budget(sections, budget)

    def _collect_sections(
        self,
        task: Task,
        state: WorkflowState | None,
        codebase_context: str | None = None,
        workspace_dir: str | None = None,
        criteria_map: dict[str, str] | None = None,
    ) -> list[_Section]:
        sections: list[_Section] = []

        # 1. Task description (required, never truncated)
        desc_parts = [f"# Task: {task.title}", f"\n## Description\n{task.description}"]

        # Render structured prompt if present
        if task.structured_prompt:
            sp = task.structured_prompt
            if sp.objective:
                desc_parts.append(f"\n## Objective\n{sp.objective}")
            if sp.files:
                desc_parts.append(
                    "\n## File Scope\n"
                    "WARNING: Only modify these files.\n"
                    + "\n".join(f"- {f}" for f in sp.files)
                )
            if sp.action:
                desc_parts.append(f"\n## Action\n{sp.action}")
            if sp.verify:
                desc_parts.append(f"\n## Verification\n{sp.verify}")
            if sp.done:
                desc_parts.append(f"\n## Definition of Done\n{sp.done}")

        if workspace_dir:
            desc_parts.append(
                f"\n## Workspace\n"
                f"Your workspace directory is: {workspace_dir}\n"
                f"Run all shell commands prefixed with: cd {workspace_dir} && <command>\n"
                "All file paths must be absolute within this directory."
            )

        desc = "\n".join(desc_parts)
        sections.append(_Section(
            priority=PRIORITY_TASK_DESCRIPTION,
            label="task_description",
            content=desc,
            required=True,
        ))

        # 2. Pre-loaded input data (P17)
        if workspace_dir:
            input_dir = Path(workspace_dir) / "input"
            if input_dir.exists():
                source_files = sorted(input_dir.glob("*.json"))
                if source_files:
                    parts = ["\n## Pre-loaded Input Data"]
                    for sf in source_files[:5]:
                        try:
                            content = sf.read_text()[:10000]
                            parts.append(f"\n### {sf.stem}\n```\n{content}\n```")
                        except Exception:
                            pass
                    if len(parts) > 1:
                        sections.append(_Section(
                            priority=PRIORITY_INPUT_SOURCES,
                            label="input_sources",
                            content="\n".join(parts),
                        ))

        # 3. Acceptance criteria
        if task.acceptance_criteria_ids:
            if criteria_map:
                lines = [f"- **{ac_id}**: {criteria_map.get(ac_id, '(description not available)')}"
                         for ac_id in task.acceptance_criteria_ids]
                criteria = "\n## Acceptance Criteria\n" + "\n".join(lines)
            else:
                criteria = "\n## Acceptance Criteria IDs\n" + ", ".join(task.acceptance_criteria_ids)
            sections.append(_Section(
                priority=PRIORITY_ACCEPTANCE_CRITERIA,
                label="acceptance_criteria",
                content=criteria,
            ))

        # 3. Skeleton tests
        if task.skeleton_tests:
            parts = ["\n## Skeleton Tests (you MUST implement these)"]
            for i, skel in enumerate(task.skeleton_tests, 1):
                parts.append(f"\n### Test {i}\n```python\n{skel}\n```")
            sections.append(_Section(
                priority=PRIORITY_SKELETON_TESTS,
                label="skeleton_tests",
                content="\n".join(parts),
            ))

        # 4. Prior attempt feedback (retry context)
        if task.attempt_feedback:
            parts = [
                "\n## Prior Attempt Feedback",
                "The following feedback is from previous failed attempts. "
                "Use it to improve your output.",
            ]
            for fb in task.attempt_feedback:
                parts.append(f"\n### Attempt {fb.attempt}")
                parts.append(f"**Score**: {fb.score:.2f}")
                parts.append(f"**Feedback**: {fb.feedback}")
                if fb.suggested_improvements:
                    parts.append("**Suggested improvements**:")
                    for imp in fb.suggested_improvements:
                        parts.append(f"- {imp}")
                if fb.test_results:
                    failed = [tr for tr in fb.test_results if not tr.passed]
                    if failed:
                        parts.append("**Failed tests**:")
                        for tr in failed:
                            msg = f"- {tr.name}"
                            if tr.error_message:
                                msg += f": {tr.error_message}"
                            parts.append(msg)
            sections.append(_Section(
                priority=PRIORITY_ATTEMPT_FEEDBACK,
                label="attempt_feedback",
                content="\n".join(parts),
            ))

        # 5. Dependency outputs
        if state and task.depends_on:
            dep_parts: list[str] = []
            for dep_id in task.depends_on:
                dep_task = state.tasks.get(dep_id)
                if dep_task and dep_task.result and dep_task.result.output:
                    dep_content = dep_task.result.output[:2000]
                    # Append file manifest so downstream agents know what files exist
                    if dep_task.result.file_manifest:
                        dep_content += "\n\n**Files produced (in shared workspace):**\n"
                        for entry in dep_task.result.file_manifest[:50]:
                            dep_content += f"- `{entry.path}` ({entry.size_bytes} bytes)\n"
                        dep_content += (
                            "\nUse filesystem tools to read any files you need."
                        )
                    dep_parts.append(
                        f"### {dep_task.title} (task {dep_id})\n"
                        f"{dep_content}"
                    )
            if dep_parts:
                content = "\n## Outputs from Dependency Tasks\n" + "\n".join(dep_parts)
                sections.append(_Section(
                    priority=PRIORITY_DEPENDENCY_OUTPUTS,
                    label="dependency_outputs",
                    content=content,
                ))

        # 6. Codebase context (from CodebaseIndex)
        if codebase_context:
            sections.append(_Section(
                priority=PRIORITY_CODEBASE_CONTEXT,
                label="codebase_context",
                content="\n## Relevant Codebase Files\n" + codebase_context,
            ))

        return sections

    def _assemble_within_budget(
        self, sections: list[_Section], budget: int
    ) -> str:
        """Assemble sections within token budget, truncating from lowest priority."""
        total_tokens = sum(s.estimated_tokens for s in sections)

        if total_tokens <= budget:
            # Everything fits
            return "\n".join(s.content for s in sections)

        # Need to truncate — remove from lowest priority first
        result_sections: list[_Section] = []
        used_tokens = 0

        for section in sections:
            if section.required:
                result_sections.append(section)
                used_tokens += section.estimated_tokens
                continue

            remaining = budget - used_tokens
            if remaining <= 0:
                continue  # Drop this section entirely

            if section.estimated_tokens <= remaining:
                result_sections.append(section)
                used_tokens += section.estimated_tokens
            else:
                # Truncate this section to fit
                char_budget = int(remaining * self._config.chars_per_token)
                if char_budget > 50:  # Only include if meaningfully sized
                    truncated = _Section(
                        priority=section.priority,
                        label=section.label,
                        content=section.content[:char_budget] + "\n\n[truncated]",
                        required=False,
                    )
                    result_sections.append(truncated)
                    used_tokens += truncated.estimated_tokens

        return "\n".join(s.content for s in result_sections)

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate based on character count."""
        return max(1, int(len(text) / self._config.chars_per_token))
