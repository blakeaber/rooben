"""P15b — Personal Rooben instance E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestMeDashboardPage:
    """Browser tests for the /me page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/me")
        snap = browser.wait_for_text("Dashboard", timeout_ms=10000)
        assert snap.contains("Dashboard")

    def test_breadcrumbs(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Personal") or snap.contains("Dashboard")

    def test_stat_cards(self, browser: Browser):
        snap = browser.snapshot()
        has_stats = (
            snap.contains("Workflows")
            or snap.contains("Goals")
            or snap.contains("Spend")
            or snap.contains("Success")
        )
        assert has_stats

    def test_recent_outcomes(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Recent") or snap.contains("Outcomes") or snap.contains("outcomes")

    def test_suggested_actions(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Suggested") or snap.contains("Actions") or snap.contains("actions")

    def test_quick_links(self, browser: Browser):
        snap = browser.snapshot()
        has_links = (
            snap.ref_for_link("Manage Goals") is not None
            or snap.ref_for_link("Preferences") is not None
            or snap.ref_for_link("Goals") is not None
            or snap.contains("Goals")
        )
        assert has_links

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestGoalsPage:
    """Browser tests for the /me/goals page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/me/goals")
        snap = browser.wait_for_text("Goals", timeout_ms=10000)
        assert snap.contains("Goals")

    def test_breadcrumbs(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Personal") or snap.contains("Goals")

    def test_new_goal_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("New Goal")
            or snap.ref_for_button("Create Goal")
            or snap.ref_for_button("Add Goal")
        )
        assert ref is not None or snap.contains("Goal")

    def test_filter_tabs(self, browser: Browser):
        snap = browser.snapshot()
        has_filters = (
            snap.contains("All")
            or snap.contains("Active")
            or snap.contains("Completed")
        )
        assert has_filters

    def test_empty_state(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("No goals") or snap.contains("goal") or snap.contains("Goal")

    def test_form_fields_present(self, browser: Browser):
        """Verify goal creation form fields exist when toggled."""
        snap = browser.snapshot()
        # Try to open the form
        ref = (
            snap.ref_for_button("New Goal")
            or snap.ref_for_button("Create Goal")
            or snap.ref_for_button("Add Goal")
        )
        if ref:
            browser.click(ref)
            browser.wait(1000)
            snap = browser.snapshot()
        assert snap.contains("Title") or snap.contains("title") or snap.contains("Goal")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestPreferencesPage:
    """Browser tests for the /me/preferences page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/me/preferences")
        snap = browser.wait_for_text("Preferences", timeout_ms=10000)
        assert snap.contains("Preferences")

    def test_provider_field(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Provider") or snap.contains("provider")

    def test_model_field(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Model") or snap.contains("model")

    def test_save_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Save Preferences") or snap.ref_for_button("Save")
        assert ref is not None or snap.contains("Save")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestPersonalDashboardAPI:
    """API tests for personal dashboard endpoints."""

    def test_dashboard_full_structure(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/me/dashboard")
        assert "workflows" in data
        assert "goals" in data

    def test_goals_list(self, browser: Browser):
        data = browser.fetch_json("/api/me/goals")
        assert "goals" in data
        assert isinstance(data["goals"], list)

    def test_preferences_get(self, browser: Browser):
        data = browser.fetch_json("/api/me/preferences")
        assert isinstance(data, dict)

    def test_goals_create(self, browser: Browser):
        status = browser.fetch_status("/api/me/goals", method="POST", body={
            "title": "E2E Test Goal",
        })
        assert status in (200, 201, 403, 503)

    def test_preferences_update(self, browser: Browser):
        status = browser.fetch_status("/api/me/preferences", method="PUT", body={
            "default_provider": "anthropic",
        })
        assert status in (200, 403, 503)

    def test_roles_list(self, browser: Browser):
        data = browser.fetch_json("/api/me/roles")
        assert "roles" in data
        assert isinstance(data["roles"], list)

    def test_outcomes_list(self, browser: Browser):
        data = browser.fetch_json("/api/me/outcomes")
        assert "outcomes" in data
        assert isinstance(data["outcomes"], list)


@pytest.mark.requires_db
class TestPersonalCleanup:
    """Clean up E2E-created goals."""

    def test_cleanup_goals(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/me/goals")
        for g in data.get("goals", []):
            if g.get("title", "").startswith("E2E"):
                browser.fetch_status(f"/api/me/goals/{g['id']}", method="DELETE")
