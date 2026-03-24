"""E2E: Smoke tests — every page loads without errors."""

import pytest

from tests.e2e.browser import Browser


class TestPageSmoke:
    """Verify every page loads without crashing."""

    def test_home_page(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Home page crashed"

    def test_new_workflow_page(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now")
        assert snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_cost_page(self, browser: Browser):
        browser.open("/cost")
        snap = browser.wait_for_text("Total Spend", timeout_ms=10000)
        assert snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_agents_page(self, browser: Browser):
        browser.open("/agents")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_optimization_page(self, browser: Browser):
        browser.open("/optimization")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_learnings_page(self, browser: Browser):
        browser.open("/learnings")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_settings_page(self, browser: Browser):
        browser.open("/settings")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_integrations_page(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        assert snap.not_contains("Application error")

    def test_integrations_detail_page(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        assert snap.not_contains("Application error")

    def test_integrations_library_page(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        assert snap.not_contains("Application error")

    def test_integrations_create_page(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        assert snap.not_contains("Application error")


class TestAPISmoke:
    """Verify key API endpoints respond."""

    def test_health(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        data = browser.fetch_json("/api/health")
        assert data["status"] == "ok"

    def test_integrations_list(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        data = browser.fetch_json("/api/integrations")
        assert "integrations" in data

    def test_integrations_library(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        data = browser.fetch_json("/api/integrations/library")
        assert "library" in data or "items" in data

    @pytest.mark.requires_db
    def test_workflows_list(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        data = browser.fetch_json("/api/workflows")
        assert "workflows" in data

    @pytest.mark.requires_db
    def test_cost_summary(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        data = browser.fetch_json("/api/cost/summary")
        assert "total_cost" in data
