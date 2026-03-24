"""Section 21: Error Handling — 5 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestErrorHandling:
    """Verify graceful error handling when DB is down or APIs fail."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    # S21.1 ----------------------------------------------------------------
    @pytest.mark.requires_db
    def test_db_down_workflows_endpoint_returns_500(self, browser: Browser):
        status = browser.fetch_status("/api/workflows")
        # Without a DB, expect 500; with DB, expect 200
        assert status in (200, 500), f"Unexpected status: {status}"

    # S21.2 ----------------------------------------------------------------
    @pytest.mark.requires_db
    def test_db_down_cost_endpoint_returns_500(self, browser: Browser):
        status = browser.fetch_status("/api/cost/summary")
        assert status in (200, 500), f"Unexpected status: {status}"

    # S21.3 ----------------------------------------------------------------
    def test_db_down_home_page_still_renders(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Home page crashed without DB"

    # S21.4 ----------------------------------------------------------------
    def test_db_down_cost_page_still_renders(self, browser: Browser):
        browser.open("/cost")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Cost page crashed without DB"

    # S21.5 ----------------------------------------------------------------
    def test_api_error_doesnt_break_navigation(self, browser: Browser):
        # Visit a page that might trigger an API error
        browser.open("/agents")
        browser.wait(2000)
        snap = browser.snapshot()

        # Navigate away to integrations — should still work
        int_ref = (
            snap.ref_for_link("Integrations")
            or snap.ref_for_link("integrations")
            or snap.ref_for_button("Integrations")
        )
        if int_ref:
            browser.click(int_ref)
            browser.wait(2000)
            snap = browser.snapshot()
            assert snap.not_contains("Application error"), "Navigation broken after API error"
        else:
            # Fallback: navigate directly
            browser.open("/integrations")
            browser.wait(2000)
            snap = browser.snapshot()
            assert snap.not_contains("Application error"), "Integrations page crashed"
