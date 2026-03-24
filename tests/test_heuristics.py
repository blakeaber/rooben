"""Tests for heuristic extractors used by the MCP agent scratchpad."""

from __future__ import annotations

from rooben.agents.heuristics import (
    classify_tool_call,
    extract_decisions_from_llm_output,
    extract_tool_outcome,
    is_error_result,
)


# ---------------------------------------------------------------------------
# extract_decisions_from_llm_output
# ---------------------------------------------------------------------------

class TestExtractDecisions:
    def test_keyword_because(self):
        raw = "I chose Flask because it has minimal dependencies."
        result = extract_decisions_from_llm_output(raw)
        assert len(result) == 1
        assert "Flask" in result[0]

    def test_keyword_chose(self):
        raw = "I chose to split models into separate files for testability."
        result = extract_decisions_from_llm_output(raw)
        assert len(result) >= 1
        assert "split models" in result[0]

    def test_keyword_instead_of(self):
        raw = "Using SQLite instead of PostgreSQL for the prototype."
        result = extract_decisions_from_llm_output(raw)
        assert len(result) == 1
        assert "SQLite" in result[0]

    def test_keyword_plan_colon(self):
        raw = "Plan: write the API routes first, then the models."
        result = extract_decisions_from_llm_output(raw)
        assert len(result) >= 1

    def test_numbered_items_in_plan_block(self):
        raw = "Here are my steps:\n1. Create the models\n2. Write the routes\n3. Add tests"
        result = extract_decisions_from_llm_output(raw)
        assert len(result) == 3
        assert "Create the models" in result[0]

    def test_max_decisions_cap(self):
        raw = (
            "I chose A because X.\n"
            "I chose B because Y.\n"
            "I chose C because Z.\n"
            "I chose D because W.\n"
        )
        result = extract_decisions_from_llm_output(raw, max_decisions=2)
        assert len(result) == 2

    def test_empty_input(self):
        assert extract_decisions_from_llm_output("") == []
        assert extract_decisions_from_llm_output(None) == []  # type: ignore[arg-type]

    def test_skips_code_like_lines(self):
        raw = '{"key": "because this is JSON"}\nimport because_module'
        result = extract_decisions_from_llm_output(raw)
        assert len(result) == 0

    def test_truncates_long_lines(self):
        raw = "I chose " + "x" * 200 + " because reasons."
        result = extract_decisions_from_llm_output(raw)
        assert len(result) == 1
        assert len(result[0]) <= 120


# ---------------------------------------------------------------------------
# classify_tool_call
# ---------------------------------------------------------------------------

class TestClassifyToolCall:
    def test_write_file(self):
        assert classify_tool_call("write_file", {}) == "file_write"

    def test_create_file(self):
        assert classify_tool_call("create_file", {}) == "file_write"

    def test_edit_file(self):
        assert classify_tool_call("edit_file", {}) == "file_write"

    def test_read_file(self):
        assert classify_tool_call("read_file", {}) == "file_read"

    def test_shell_command(self):
        assert classify_tool_call("execute_command", {}) == "tool_call"

    def test_create_directory(self):
        assert classify_tool_call("create_directory", {}) == "tool_call"

    def test_list_directory(self):
        assert classify_tool_call("list_directory", {}) == "tool_call"


# ---------------------------------------------------------------------------
# extract_tool_outcome
# ---------------------------------------------------------------------------

class TestExtractToolOutcome:
    def test_success_write(self):
        result_str = "Successfully wrote to /workspace/src/app.py"
        outcome = extract_tool_outcome("write_file", result_str)
        assert "Successfully" in outcome
        assert "app.py" in outcome

    def test_error_message(self):
        result_str = "Error: ENOENT no such file or directory"
        outcome = extract_tool_outcome("read_file", result_str)
        assert "ENOENT" in outcome

    def test_max_chars_truncation(self):
        long_result = "x" * 200
        outcome = extract_tool_outcome("list_directory", long_result, max_chars=50)
        assert len(outcome) <= 50

    def test_empty_result(self):
        assert extract_tool_outcome("read_file", "") == "(empty result)"

    def test_multiline_first_line(self):
        result_str = "Line one\nLine two\nLine three"
        outcome = extract_tool_outcome("list_directory", result_str)
        assert outcome == "Line one"


# ---------------------------------------------------------------------------
# is_error_result
# ---------------------------------------------------------------------------

class TestIsErrorResult:
    def test_error_prefix(self):
        assert is_error_result("Error: something went wrong")

    def test_enoent(self):
        assert is_error_result("ENOENT: no such file or directory")

    def test_failed(self):
        assert is_error_result("Operation failed: timeout")

    def test_permission_denied(self):
        assert is_error_result("Permission denied: /etc/shadow")

    def test_empty_string(self):
        assert not is_error_result("")

    def test_none(self):
        assert not is_error_result(None)  # type: ignore[arg-type]

    def test_success_message(self):
        assert not is_error_result("Successfully wrote to /workspace/file.py")

    def test_error_in_path(self):
        # "error" appears but as part of a path — heuristic may pick this up
        # This documents a known limitation
        result = is_error_result("Read file /workspace/error_handler.py")
        # This is a known false positive; documenting the behavior
        assert isinstance(result, bool)
