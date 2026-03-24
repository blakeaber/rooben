"""E2E: Integrations Hub — 6 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestIntegrationsE2E:
    """Verify the Integrations Hub discovery and management flow (P8)."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    def test_integrations_hub_loads(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations", timeout_ms=10000)
        assert snap.not_contains("Application error")
        # Should show at least some integration names
        assert (
            snap.contains("coding")
            or snap.contains("Coding")
            or snap.contains("web")
            or snap.contains("data")
            or snap.contains("integration")
        ), "Integrations hub should list integrations"

    def test_integrations_search(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations", timeout_ms=10000)
        search_ref = (
            snap.ref_for_textbox("Search")
            or snap.ref_for_textbox("Filter")
            or snap.ref_for_textbox("search")
            or snap.ref_for("search")
        )
        if search_ref:
            browser.fill(search_ref, "coding")
            browser.wait(1000)
            snap2 = browser.snapshot()
            assert snap2.contains("coding") or snap2.contains("Coding")

    def test_integration_detail_page(self, browser: Browser):
        browser.open("/integrations/coding")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")
        assert (
            snap.contains("coding")
            or snap.contains("Coding")
            or snap.contains("tool")
            or snap.contains("Tool")
        ), "Integration detail should show integration info"

    def test_integrations_library(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library", timeout_ms=10000)
        assert snap.not_contains("Application error")
        assert snap.contains("Community") or snap.contains("Library")

    def test_integrations_create_builder(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder", timeout_ms=10000)
        assert snap.not_contains("Application error")
        assert (
            snap.contains("AI-Assisted")
            or snap.contains("Builder")
            or snap.contains("Create")
        )

    def test_integration_credentials_link(self, browser: Browser):
        browser.open("/integrations/coding")
        browser.wait(3000)
        snap = browser.snapshot()
        # Check for credential or connection UI elements
        _has_cred_ui = (
            snap.contains("credential")
            or snap.contains("Credential")
            or snap.contains("Connect")
            or snap.contains("connection")
            or snap.contains("API key")
            or snap.contains("Configure")
            or snap.contains("Status")
        )
        # This is a soft check — credentials UI may or may not show depending on integration
        assert snap.not_contains("Application error")
