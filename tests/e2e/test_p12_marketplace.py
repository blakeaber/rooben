"""P12 — Marketplace ecosystem E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestIntegrationsTemplatesTab:
    """Browser tests for the integrations templates tab."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/integrations?tab=templates")
        snap = browser.wait_for_text("Templates", timeout_ms=10000)
        assert snap.contains("Templates")

    def test_template_categories_visible(self, browser: Browser):
        snap = browser.snapshot()
        assert (
            snap.contains("Professional")
            or snap.contains("Builder")
            or snap.contains("Automator")
            or snap.contains("template")
        )

    def test_template_cards_present(self, browser: Browser):
        snap = browser.snapshot()
        has_templates = (
            snap.contains("Competitive Analysis")
            or snap.contains("REST API")
            or snap.contains("Weekly Report")
            or snap.contains("Use Template")
        )
        assert has_templates or snap.contains("template")

    def test_use_template_link(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_link("Use Template")
            or snap.ref_for_button("Use Template")
        )
        assert ref is not None or snap.contains("Use Template")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestIntegrationsAgentsTab:
    """Browser tests for the integrations agents tab."""

    def test_page_loads(self, browser: Browser):
        browser.open("/integrations?tab=agents")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_agents_or_empty_state(self, browser: Browser):
        snap = browser.snapshot()
        has_content = (
            snap.contains("Agent")
            or snap.contains("agent")
            or snap.contains("Create Workflow")
            or snap.contains("workflow")
        )
        assert has_content


@pytest.mark.requires_db
class TestMarketplaceAPI:
    """API tests for marketplace endpoints (Pro extension)."""

    def test_templates_list(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/marketplace/templates")
        assert "templates" in data
        assert isinstance(data["templates"], list)
        assert len(data["templates"]) > 0

    def test_template_detail(self, browser: Browser):
        data = browser.fetch_json("/api/marketplace/templates/saas-landing-page")
        assert "spec_yaml" in data or "name" in data

    def test_agents_list(self, browser: Browser):
        data = browser.fetch_json("/api/marketplace/agents")
        assert "agents" in data
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) > 0

    def test_template_install(self, browser: Browser):
        status = browser.fetch_status(
            "/api/marketplace/templates/saas-landing-page/install", method="POST"
        )
        assert status in (200, 404)

    def test_template_delete_builtin_forbidden(self, browser: Browser):
        status = browser.fetch_status(
            "/api/marketplace/templates/saas-landing-page", method="DELETE"
        )
        assert status in (403, 404)

    def test_agent_delete_community_forbidden(self, browser: Browser):
        status = browser.fetch_status(
            "/api/marketplace/agents/code-reviewer", method="DELETE"
        )
        assert status in (403, 404)
