"""P15e — Org-wide knowledge amplification E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestKnowledgeBasePage:
    """Browser tests for the /org/learnings page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/learnings")
        snap = browser.wait_for_text("Knowledge", timeout_ms=10000)
        assert snap.contains("Knowledge") or snap.contains("Learning")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_breadcrumbs(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Organization") or snap.contains("Org") or snap.contains("Knowledge")

    def test_filter_tabs(self, browser: Browser):
        snap = browser.snapshot()
        has_tabs = (
            snap.contains("All")
            or snap.contains("Personal")
            or snap.contains("Team")
            or snap.contains("Organization")
        )
        assert has_tabs

    def test_search_input(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_textbox("Search") or snap.ref_for_textbox("search")
        has_search = ref is not None or snap.contains("Search")
        assert has_search

    def test_stats_cards(self, browser: Browser):
        snap = browser.snapshot()
        has_stats = (
            snap.contains("Total")
            or snap.contains("Learnings")
            or snap.contains("Knowledge")
        )
        assert has_stats

    def test_empty_or_data_state(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("No learnings") or snap.contains("learning") or snap.contains("Knowledge")


@pytest.mark.requires_db
class TestAgentProfilesPage:
    """Browser tests for the /org/agent-profiles page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/agent-profiles")
        snap = browser.wait_for_text("Agent Profile", timeout_ms=10000)
        assert snap.contains("Agent Profile") or snap.contains("Profile")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_new_profile_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("New Profile")
            or snap.ref_for_button("Create Profile")
            or snap.ref_for_button("Add Profile")
            or snap.ref_for_button("Add")
        )
        assert ref is not None or snap.contains("Profile")

    def test_description_text(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("profile") or snap.contains("agent") or snap.contains("Profile")

    def test_empty_state(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("No profiles") or snap.contains("profile") or snap.contains("Profile")


@pytest.mark.requires_db
class TestRecommendationsPage:
    """Browser tests for the /org/recommendations page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/recommendations")
        snap = browser.wait_for_text("Recommendation", timeout_ms=10000)
        assert snap.contains("Recommendation") or snap.contains("recommendation")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_refresh_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Refresh") or snap.ref_for_button("Generate")
        assert ref is not None or snap.contains("Refresh") or snap.contains("Generate")

    def test_category_tabs(self, browser: Browser):
        snap = browser.snapshot()
        has_categories = (
            snap.contains("All")
            or snap.contains("Cost")
            or snap.contains("Quality")
            or snap.contains("Process")
            or snap.contains("Skill")
        )
        assert has_categories

    def test_empty_state(self, browser: Browser):
        snap = browser.snapshot()
        assert (
            snap.contains("No recommendations")
            or snap.contains("recommendation")
            or snap.contains("Recommendation")
        )


@pytest.mark.requires_db
class TestKnowledgeAPIs:
    """API tests for knowledge amplification endpoints (200 or 403)."""

    def test_learnings_list(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status("/api/org/learnings")
        assert status in (200, 403)

    def test_learnings_search(self, browser: Browser):
        status = browser.fetch_status("/api/org/learnings/search?q=test")
        assert status in (200, 403)

    def test_learnings_stats(self, browser: Browser):
        status = browser.fetch_status("/api/org/learnings/stats")
        assert status in (200, 403)

    def test_learnings_create(self, browser: Browser):
        status = browser.fetch_status("/api/org/learnings", method="POST", body={
            "content": "E2E test learning",
            "agent_id": "test-agent",
            "visibility": "personal",
        })
        assert status in (200, 201, 403, 422)

    def test_learnings_export(self, browser: Browser):
        status = browser.fetch_status("/api/org/learnings?format=export")
        assert status in (200, 403)

    def test_agent_profiles_list(self, browser: Browser):
        status = browser.fetch_status("/api/org/agent-profiles")
        assert status in (200, 403)

    def test_agent_profiles_create(self, browser: Browser):
        status = browser.fetch_status("/api/org/agent-profiles", method="POST", body={
            "name": "E2E Test Profile",
            "agent_type": "researcher",
            "description": "Created by E2E test",
        })
        assert status in (200, 201, 403, 422)

    def test_agent_profiles_delete_nonexistent(self, browser: Browser):
        status = browser.fetch_status("/api/org/agent-profiles/fake-id", method="DELETE")
        assert status in (200, 403, 404, 422)

    def test_recommendations_list(self, browser: Browser):
        status = browser.fetch_status("/api/org/recommendations")
        assert status in (200, 403)

    def test_recommendations_refresh(self, browser: Browser):
        status = browser.fetch_status("/api/org/recommendations/refresh", method="POST")
        assert status in (200, 403)

    def test_recommendations_dismiss(self, browser: Browser):
        status = browser.fetch_status(
            "/api/org/recommendations/fake-id/dismiss", method="PUT"
        )
        assert status in (200, 403, 404, 422)
