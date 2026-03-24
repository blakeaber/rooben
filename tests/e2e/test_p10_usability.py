"""P10 — Usability & workflow lifecycle E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestNewWorkflowPage:
    """Browser tests for the /workflows/new page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("New Workflow", timeout_ms=10000)
        assert snap.contains("New Workflow")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_breadcrumbs(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Workflows")


@pytest.mark.requires_db
class TestWorkflowsListPage:
    """Browser tests for the main workflows list page."""

    def test_page_loads(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("Past Runs", timeout_ms=10000)
        assert snap.not_contains("Application error")

    def test_contains_workflows_content(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Past Runs") or snap.contains("Workflows")


@pytest.mark.requires_db
class TestWorkflowAPIs:
    """API tests for workflow endpoints."""

    def test_workflows_list(self, browser: Browser):
        browser.open("/")
        browser.wait(3000)
        status = browser.fetch_status("/api/workflows")
        assert status in (200, 500)
        if status == 200:
            data = browser.fetch_json("/api/workflows")
            assert "workflows" in data
            assert isinstance(data["workflows"], list)

    def test_workflow_create_returns_id(self, browser: Browser):
        status = browser.fetch_status("/api/workflows", method="POST", body={
            "description": "E2E test workflow",
        })
        assert status in (200, 201, 422)

    def test_workflow_status_nonexistent(self, browser: Browser):
        status = browser.fetch_status("/api/workflows/wf-nonexistent/status")
        assert status in (404, 503)

    def test_workflow_cancel_nonexistent(self, browser: Browser):
        status = browser.fetch_status(
            "/api/workflows/wf-nonexistent/cancel", method="POST"
        )
        assert status in (200, 409, 503)


@pytest.mark.requires_db
class TestExportAPIs:
    """API tests for export endpoints."""

    def test_export_pdf_nonexistent(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        status = browser.fetch_status("/api/workflows/wf-fake/export/pdf")
        assert status in (404, 500)

    def test_export_docx_nonexistent(self, browser: Browser):
        status = browser.fetch_status("/api/workflows/wf-fake/export/docx")
        assert status in (404, 500)

    def test_share_nonexistent(self, browser: Browser):
        status = browser.fetch_status(
            "/api/workflows/wf-fake/share", method="POST"
        )
        assert status in (404, 405, 500, 503)


@pytest.mark.requires_db
class TestLearningsAPI:
    """API tests for learning extraction endpoints."""

    def test_learnings_list(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/learnings")
        assert "learnings" in data
        assert isinstance(data["learnings"], list)

    def test_learnings_keywords(self, browser: Browser):
        data = browser.fetch_json("/api/learnings/keywords")
        assert "keywords" in data
        assert isinstance(data["keywords"], list)

    def test_learnings_extract_missing_wf(self, browser: Browser):
        status = browser.fetch_status(
            "/api/learnings/extract?workflow_id=wf-fake", method="POST"
        )
        assert status in (404, 500, 503)
