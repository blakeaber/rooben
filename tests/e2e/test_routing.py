"""Section 19: Navigation & Routing — 8 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestRouting:
    """Verify client-side routing and URL correctness."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    # S19.1 ----------------------------------------------------------------
    def test_home_route(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        url = browser.get_url()
        assert url.endswith("/") or url.endswith(":3000"), f"Unexpected URL: {url}"

    # S19.2 ----------------------------------------------------------------
    def test_create_route(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(1000)
        url = browser.get_url()
        assert "/workflows/new" in url, f"URL missing /workflows/new: {url}"

    # S19.3 ----------------------------------------------------------------
    def test_cost_route(self, browser: Browser):
        browser.open("/cost")
        browser.wait(2000)
        url = browser.get_url()
        assert "/cost" in url, f"URL missing /cost: {url}"
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Cost page crashed"

    # S19.4 ----------------------------------------------------------------
    def test_agents_route(self, browser: Browser):
        browser.open("/agents")
        browser.wait(2000)
        url = browser.get_url()
        assert "/agents" in url, f"URL missing /agents: {url}"
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Agents page crashed"

    # S19.5 ----------------------------------------------------------------
    def test_settings_route(self, browser: Browser):
        browser.open("/settings")
        browser.wait(2000)
        url = browser.get_url()
        assert "/settings" in url, f"URL missing /settings: {url}"
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Settings page crashed"

    # S19.6 ----------------------------------------------------------------
    def test_deep_link_to_workflow(self, browser: Browser):
        browser.open("/workflows/abc-123")
        browser.wait(2000)
        url = browser.get_url()
        assert "abc-123" in url, f"Deep link URL not preserved: {url}"

    # S19.7 ----------------------------------------------------------------
    def test_unknown_route_shows_404(self, browser: Browser):
        browser.open("/this-does-not-exist")
        browser.wait(2000)
        snap = browser.snapshot()
        url = browser.get_url()
        is_404 = snap.contains("404") or snap.contains("Not Found") or snap.contains("not found")
        is_redirect = "/" == url.split(":3000")[-1] or url.endswith("/")
        assert is_404 or is_redirect, f"Unknown route did not 404 or redirect: {url}"

    # S19.8 ----------------------------------------------------------------
    def test_sidebar_navigation_round_trip(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        snap = browser.snapshot()

        int_ref = (
            snap.ref_for_link("Integrations")
            or snap.ref_for_link("integrations")
            or snap.ref_for_button("Integrations")
        )
        if int_ref:
            browser.click(int_ref)
            browser.wait(1000)
            url = browser.get_url()
            assert "/integrations" in url, f"Did not navigate to integrations: {url}"

        snap = browser.snapshot()
        home_ref = (
            snap.ref_for_link("Home")
            or snap.ref_for_link("Dashboard")
            or snap.ref_for_link("Rooben")
        )
        if home_ref:
            browser.click(home_ref)
            browser.wait(1000)
            url = browser.get_url()
            assert url.endswith("/") or ":3000" in url.split("/")[-1], f"Did not return home: {url}"
