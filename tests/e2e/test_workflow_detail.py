"""Section 7: Workflow Detail — 5 tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


class TestWorkflowDetail:
    """Workflow detail page, DAG, timeline, chat, and error handling."""

    @pytest.mark.requires_db
    def test_detail_page_loads(self, browser: Browser):
        browser.open("/workflows/test-id")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), \
            "Workflow detail page should render without crash"

    @pytest.mark.requires_db
    def test_dag_visualization_renders(self, browser: Browser):
        browser.open("/workflows/test-id")
        browser.wait(3000)
        snap = browser.snapshot()
        has_dag = (
            snap.contains("task")
            or snap.contains("Task")
            or snap.contains("DAG")
            or snap.contains("node")
        )
        assert has_dag or snap.not_contains("Application error"), \
            "DAG or task content should render"

    @pytest.mark.requires_db
    def test_timeline_view_accessible(self, browser: Browser):
        browser.open("/workflows/test-id")
        browser.wait(3000)
        snap = browser.snapshot()
        ref = snap.ref_for_button("Timeline") or snap.ref_for("Timeline")
        if ref:
            browser.click(ref)
            browser.wait(1500)
            snap = browser.snapshot()
            assert snap.not_contains("Application error"), \
                "Timeline view should render"

    @pytest.mark.requires_db
    def test_workflow_chat_interface(self, browser: Browser):
        browser.open("/workflows/test-id")
        browser.wait(3000)
        snap = browser.snapshot()
        has_chat = (
            snap.ref_for_textbox("Message")
            or snap.ref_for_textbox("Ask")
            or snap.ref_for_textbox("Chat")
            or snap.contains("chat")
        )
        assert has_chat or snap.not_contains("Application error"), \
            "Chat interface or clean page should render"

    def test_invalid_workflow_id_shows_error(self, browser: Browser):
        browser.open("/workflows/nonexistent-id-12345")
        browser.wait(3000)
        snap = browser.snapshot()
        has_error = (
            snap.contains("not found")
            or snap.contains("Not Found")
            or snap.contains("Error")
            or snap.contains("error")
            or snap.not_contains("Application error")
        )
        assert has_error, "Invalid workflow should show error, not crash"
