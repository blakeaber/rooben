"""Section 6: Home Page / Dashboard — 6 tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


class TestHomeDashboard:
    """Home page loads, branding, CTA, workflow table, and graceful degradation."""

    def test_home_page_loads_without_crash(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Home page should not crash"

    def test_page_branding_correct(self, browser: Browser):
        browser.open("/")
        snap = browser.snapshot()
        assert snap.contains("Rooben"), "Home page should show Rooben branding"

    def test_create_workflow_cta_visible(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        has_cta = (
            snap.ref_for_link("Add New")
            or snap.ref_for_button("Create")
            or snap.contains("Create")
            or snap.contains("Add New")
        )
        assert has_cta, "Home page should have a create workflow CTA"

    @pytest.mark.requires_db
    def test_workflow_table_renders(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("Workflows", timeout_ms=5000)
        assert snap.contains("Workflows") or snap.contains("Past Runs"), \
            "Workflow table header should be visible"

    @pytest.mark.requires_db
    def test_workflow_list_api(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/workflows")
        assert "workflows" in data, "API should return workflows key"
        assert isinstance(data["workflows"], list), "workflows should be a list"

    def test_no_db_graceful_degradation(self, browser: Browser):
        _status = browser.fetch_status("/api/workflows")
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), \
            "Home page should degrade gracefully without DB"
