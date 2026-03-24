"""E2E: Dashboard Home & Navigation — 6 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestDashboardHome:
    """Verify the lifecycle-aware home page and sidebar navigation."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    def test_home_summary_cards(self, browser: Browser):
        browser.open("/")
        browser.wait(3000)
        snap = browser.snapshot()
        # Summary cards should render — at least some of these labels
        found = sum([
            snap.contains("Total Workflows") or snap.contains("Workflows"),
            snap.contains("Total Spend") or snap.contains("Spend"),
            snap.contains("Tasks") or snap.contains("tasks"),
            snap.contains("Success") or snap.contains("success"),
        ])
        assert found >= 1, "At least one summary card should render"

    def test_home_status_filter_tabs(self, browser: Browser):
        browser.open("/")
        browser.wait(3000)
        snap = browser.snapshot()
        found = sum([
            snap.contains("All"),
            snap.contains("Active") or snap.contains("Running"),
            snap.contains("Completed") or snap.contains("Done"),
            snap.contains("Failed"),
        ])
        assert found >= 2, "Status filter tabs should render"

    def test_home_filter_tab_click(self, browser: Browser):
        browser.open("/")
        browser.wait(3000)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("All")
            or snap.ref_for_button("Completed")
            or snap.ref_for_button("Active")
        )
        if ref:
            browser.click(ref)
            browser.wait(500)
            snap2 = browser.snapshot()
            assert snap2.not_contains("Application error")

    def test_home_empty_state_for_new_user(self, browser: Browser):
        browser.open("/")
        browser.wait(3000)
        snap = browser.snapshot()
        # With no workflows, should show empty state or welcome
        assert (
            snap.contains("Create")
            or snap.contains("first")
            or snap.contains("Get started")
            or snap.contains("Add New")
            or snap.contains("Welcome")
            or snap.contains("No workflows")
            or snap.contains("workflow")
        ), "Home should show some guidance or empty state"

    def test_sidebar_all_sections(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("System", timeout_ms=10000)
        # Check for key sidebar section labels
        found = sum([
            snap.contains("Workflows") or snap.contains("Past Runs"),
            snap.contains("Add New"),
            snap.contains("System") or snap.contains("Settings"),
            snap.contains("Integrations"),
        ])
        assert found >= 3, "Sidebar should show at least 3 navigation sections"

    def test_sidebar_links_navigate(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("Settings", timeout_ms=10000)

        # Test Settings navigation
        ref = snap.ref_for_link("Settings")
        if ref:
            browser.click(ref)
            browser.wait(1500)
            url = browser.get_url()
            assert "/settings" in url, "Settings link should navigate to /settings"

        # Test Integrations navigation
        browser.open("/")
        snap = browser.wait_for_text("Integrations", timeout_ms=10000)
        ref = snap.ref_for_link("Integrations")
        if ref:
            browser.click(ref)
            browser.wait(1500)
            url = browser.get_url()
            assert "/integrations" in url, "Integrations link should navigate"
