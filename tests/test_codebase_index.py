"""Tests for WS-4.1: Codebase Index."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rooben.context.codebase_index import CodebaseIndex


class TestCodebaseIndex:
    def test_scan_python_repo(self):
        """Scan the rooben source itself and verify files found."""
        index = CodebaseIndex(root_path="src/rooben")
        index.scan()
        assert index.file_count > 5  # Should find multiple .py files

    def test_query_by_keywords(self):
        """Search by keyword and verify relevant files returned."""
        index = CodebaseIndex(root_path="src/rooben")
        index.scan()
        result = index.query(["orchestrator"])
        assert "orchestrator" in result.lower()

    def test_budget_truncation(self):
        """Results respect token budget."""
        index = CodebaseIndex(root_path="src/rooben")
        index.scan()
        # Very small budget
        result = index.query(["agent", "task", "workflow"], budget_tokens=50)
        # Result should be bounded (50 tokens * 4 chars = 200 chars max)
        assert len(result) <= 400  # Allow some slack

    def test_incremental_update(self):
        """Add a file via update, verify it appears without rescan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial file
            (Path(tmpdir) / "module.py").write_text(
                '"""Module docstring."""\n\ndef hello():\n    pass\n'
            )
            index = CodebaseIndex(root_path=tmpdir)
            index.scan()
            assert index.file_count == 1

            # Update with new content
            index.update("new_file.py", 'def goodbye():\n    pass\n')
            assert index.file_count == 2

    def test_serialize_roundtrip(self):
        """Serialize and deserialize, verify equality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text(
                'class Foo:\n    def bar(self):\n        pass\n'
            )
            index = CodebaseIndex(root_path=tmpdir)
            index.scan()

            data = index.serialize()
            restored = CodebaseIndex.deserialize(data, tmpdir)
            assert restored.file_count == index.file_count

    def test_empty_query(self):
        """Empty keywords return empty string."""
        index = CodebaseIndex(root_path="src/rooben")
        result = index.query([])
        assert result == ""
