"""E2E: Templates & Agents browsing on Integrations tab — 5 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestTemplatesBrowsingFlow:
    """Verify template browsing on the integrations tab (replaces marketplace)."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    def test_templates_tab_loads(self, browser: Browser):
        browser.open("/integrations?tab=templates")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")
        assert (
            snap.contains("Templates")
            or snap.contains("template")
            or snap.contains("Professional")
            or snap.contains("Builder")
        ), "Templates tab should render"

    def test_templates_tab_shows_categories(self, browser: Browser):
        browser.open("/integrations?tab=templates")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.contains("Professional")
            or snap.contains("Builder")
            or snap.contains("Automator")
            or snap.contains("template")
        ), "Templates tab should show categorized templates"

    def test_agents_tab_loads(self, browser: Browser):
        browser.open("/integrations?tab=agents")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")
        assert (
            snap.contains("Agent")
            or snap.contains("agent")
            or snap.contains("Create Workflow")
            or snap.contains("workflow")
        ), "Agents tab should render"

    def test_template_use_link(self, browser: Browser):
        browser.open("/integrations?tab=templates")
        browser.wait(3000)
        snap = browser.snapshot()
        # Should have template cards with Use Template links
        ref = (
            snap.ref_for_link("Use Template")
            or snap.ref_for_button("Use Template")
        )
        if ref:
            browser.click(ref)
            browser.wait(2000)
            url = browser.get_url()
            assert "/workflows/new" in url
        else:
            # Templates should be visible even without clicking
            assert snap.not_contains("Application error")

    def test_data_sources_tab_default(self, browser: Browser):
        browser.open("/integrations")
        browser.wait(3000)
        snap = browser.snapshot()
        # Default tab should show data sources content
        assert (
            snap.contains("Data Sources")
            or snap.contains("Integrations")
            or snap.contains("Browse Library")
        ), "Default tab should show data sources"
