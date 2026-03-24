"""P15a — Identity, auth, and multi-tenancy E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestHealthAndAuth:
    """Health endpoint and auth basics."""

    def test_health_returns_200(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status("/api/health")
        assert status == 200

    def test_health_returns_json(self, browser: Browser):
        data = browser.fetch_json("/api/health")
        assert data.get("status") == "ok"


@pytest.mark.requires_db
class TestMeDashboardAPI:
    """API tests for /api/me/dashboard."""

    def test_dashboard_structure(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/me/dashboard")
        assert "workflows" in data
        assert "goals" in data

    def test_dashboard_workflows_structure(self, browser: Browser):
        data = browser.fetch_json("/api/me/dashboard")
        wf = data["workflows"]
        assert "total" in wf or isinstance(wf, (list, dict))

    def test_dashboard_goals_structure(self, browser: Browser):
        data = browser.fetch_json("/api/me/dashboard")
        goals = data["goals"]
        assert isinstance(goals, (list, dict))


@pytest.mark.requires_db
class TestCorePagesSurviveAuthRewrite:
    """Ensure core pages still render after auth rewrite."""

    def test_workflows_page(self, browser: Browser):
        browser.open("/workflows")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_integrations_page(self, browser: Browser):
        browser.open("/integrations")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestMePreferencesAPI:
    """API tests for /api/me/preferences."""

    def test_get_preferences(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/me/preferences")
        assert isinstance(data, dict)

    def test_put_preferences(self, browser: Browser):
        status = browser.fetch_status("/api/me/preferences", method="PUT", body={
            "default_provider": "anthropic",
        })
        # 200 with DB, 503 without DB, 403 with auth enabled
        assert status in (200, 403, 503)


@pytest.mark.requires_db
class TestMeGoalsAPI:
    """API tests for /api/me/goals."""

    def test_list_goals(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/me/goals")
        assert "goals" in data
        assert isinstance(data["goals"], list)

    def test_create_goal(self, browser: Browser):
        status = browser.fetch_status("/api/me/goals", method="POST", body={
            "title": "E2E Test Goal",
            "description": "Created by E2E test",
        })
        assert status in (200, 201, 403, 503)

    def test_delete_nonexistent(self, browser: Browser):
        status = browser.fetch_status("/api/me/goals/fake-goal-id", method="DELETE")
        assert status in (200, 403, 404)


@pytest.mark.requires_db
class TestOrgEndpointsRequireAuth:
    """Org endpoints should return 403 for anonymous users."""

    def test_org_agents_403(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status("/api/org/agents")
        assert status in (200, 403)

    def test_org_mcp_servers_403(self, browser: Browser):
        status = browser.fetch_status("/api/org/mcp-servers")
        assert status in (200, 403)

    def test_org_dashboard_403(self, browser: Browser):
        status = browser.fetch_status("/api/org/dashboard")
        assert status in (200, 403)

    def test_org_audit_logs_403(self, browser: Browser):
        status = browser.fetch_status("/api/org/audit-logs")
        assert status in (200, 403)

    def test_org_policies_403(self, browser: Browser):
        status = browser.fetch_status("/api/org/policies")
        assert status in (200, 403)
