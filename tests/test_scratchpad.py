"""Tests for ScratchpadAccumulator."""

from __future__ import annotations

from rooben.agents.scratchpad import ScratchpadAccumulator, ScratchpadEntry


class TestScratchpadEntry:
    def test_basic_entry(self):
        entry = ScratchpadEntry(turn=1, category="file_write", summary="/workspace/app.py")
        assert entry.turn == 1
        assert entry.category == "file_write"
        assert entry.detail == ""


class TestRecording:
    def test_record_file_write(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/workspace/app.py", "Main application")
        assert sp.has_entries
        assert len(sp._entries) == 1
        assert sp._entries[0].category == "file_write"
        assert "/workspace/app.py" in sp._entries[0].summary
        assert "Main application" in sp._entries[0].summary

    def test_record_file_write_no_purpose(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/workspace/app.py")
        assert sp._entries[0].summary == "/workspace/app.py"

    def test_record_file_read(self):
        sp = ScratchpadAccumulator()
        sp.record_file_read(2, "/workspace/config.py")
        assert sp._entries[0].category == "file_read"
        assert sp._entries[0].summary == "/workspace/config.py"

    def test_record_tool_call(self):
        sp = ScratchpadAccumulator()
        sp.record_tool_call(3, "shell", "execute_command", "exit code 0")
        assert sp._entries[0].category == "tool_call"
        assert sp._entries[0].summary == "shell/execute_command"
        assert sp._entries[0].detail == "exit code 0"

    def test_record_error(self):
        sp = ScratchpadAccumulator()
        sp.record_error(4, "ENOENT: no such file", "created parent directory")
        assert sp._entries[0].category == "error"
        assert "ENOENT" in sp._entries[0].summary
        assert sp._entries[0].detail == "created parent directory"

    def test_record_error_truncates(self):
        sp = ScratchpadAccumulator()
        long_error = "x" * 300
        sp.record_error(1, long_error)
        assert len(sp._entries[0].summary) == 200

    def test_record_decision(self):
        sp = ScratchpadAccumulator()
        sp.record_decision(5, "Chose Flask over FastAPI for minimal deps")
        assert sp._entries[0].category == "decision"

    def test_has_entries_empty(self):
        sp = ScratchpadAccumulator()
        assert not sp.has_entries

    def test_multiple_entries_accumulate(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/a.py")
        sp.record_file_write(2, "/b.py")
        sp.record_error(3, "oops")
        assert len(sp._entries) == 3


class TestScratchpadPath:
    def test_with_workspace(self):
        sp = ScratchpadAccumulator(workspace_dir="/workspace")
        assert sp.scratchpad_path == "/workspace/.scratchpad.md"

    def test_without_workspace(self):
        sp = ScratchpadAccumulator()
        assert sp.scratchpad_path is None

    def test_with_trailing_slash(self):
        sp = ScratchpadAccumulator(workspace_dir="/workspace/")
        # os.path.join handles this
        assert ".scratchpad.md" in sp.scratchpad_path


class TestToMarkdown:
    def test_empty(self):
        sp = ScratchpadAccumulator()
        md = sp.to_markdown()
        assert "# Agent Scratchpad" in md

    def test_includes_all_sections(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/app.py", "Main app")
        sp.record_file_read(2, "/config.py")
        sp.record_decision(3, "Chose REST over GraphQL")
        sp.record_error(4, "Import error", "fixed path")
        sp.record_tool_call(5, "shell", "execute_command", "ok")

        md = sp.to_markdown()
        assert "## Files Written" in md
        assert "## Files Read" in md
        assert "## Key Decisions" in md
        assert "## Errors" in md
        assert "## Tool Calls" in md
        assert "/app.py" in md
        assert "fixed path" in md

    def test_turn_numbers_present(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(7, "/app.py")
        md = sp.to_markdown()
        assert "Turn 7" in md


class TestToCompactSummary:
    def test_includes_header(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/app.py")
        summary = sp.to_compact_summary()
        assert "[Conversation compacted" in summary

    def test_includes_progress(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/a.py")
        sp.record_file_write(2, "/b.py")
        sp.record_tool_call(3, "s", "t", "ok")
        summary = sp.to_compact_summary()
        assert "Files created: 2" in summary
        assert "Tool calls: 3" in summary

    def test_includes_files_written(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/workspace/routes.py", "API routes")
        summary = sp.to_compact_summary()
        assert "## Files Written" in summary
        assert "/workspace/routes.py" in summary

    def test_includes_decisions(self):
        sp = ScratchpadAccumulator()
        sp.record_decision(2, "Chose Flask")
        summary = sp.to_compact_summary()
        assert "## Key Decisions" in summary
        assert "Chose Flask" in summary

    def test_includes_errors(self):
        sp = ScratchpadAccumulator()
        sp.record_error(3, "Missing dir", "created it")
        summary = sp.to_compact_summary()
        assert "## Errors Resolved" in summary

    def test_respects_max_chars(self):
        sp = ScratchpadAccumulator()
        # Add many entries to exceed budget
        for i in range(50):
            sp.record_file_write(i, f"/workspace/file_{i}.py", f"Purpose for file {i}")
            sp.record_tool_call(i, "shell", "execute_command", f"Output {i} " * 10)
        summary = sp.to_compact_summary(max_chars=500)
        assert len(summary) <= 503  # Allow for trailing "..."

    def test_priority_order_files_over_tools(self):
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/important.py")
        sp.record_tool_call(2, "shell", "cmd", "output")
        # With a very tight budget, files should appear before tool calls
        summary = sp.to_compact_summary(max_chars=300)
        if "## Files Written" in summary:
            files_pos = summary.index("## Files Written")
            if "## Tool Calls" in summary:
                tools_pos = summary.index("## Tool Calls")
                assert files_pos < tools_pos

    def test_scratchpad_reference_when_flushed(self):
        sp = ScratchpadAccumulator(workspace_dir="/workspace")
        sp.record_file_write(1, "/app.py")
        sp._flushed = True
        summary = sp.to_compact_summary()
        assert "Full scratchpad:" in summary
        assert ".scratchpad.md" in summary

    def test_no_reference_when_not_flushed(self):
        sp = ScratchpadAccumulator(workspace_dir="/workspace")
        sp.record_file_write(1, "/app.py")
        summary = sp.to_compact_summary()
        assert "Full scratchpad:" not in summary

    def test_multiple_compaction_cycles(self):
        """Entries accumulate across multiple cycles — never cleared."""
        sp = ScratchpadAccumulator()
        sp.record_file_write(1, "/a.py")
        summary1 = sp.to_compact_summary()
        sp.record_file_write(5, "/b.py")
        summary2 = sp.to_compact_summary()
        assert "/a.py" in summary2
        assert "/b.py" in summary2
        assert len(summary2) > len(summary1)
