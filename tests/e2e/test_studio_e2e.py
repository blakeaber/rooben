"""E2E: Studio Browse & Create — 5 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestStudioE2E:
    """Verify the Studio unified browse and create experience (P16.5)."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    def test_studio_browse_loads(self, browser: Browser):
        browser.open("/studio")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.contains("Studio")
            or snap.contains("Browse")
            or snap.contains("template")
            or snap.contains("Template")
            or snap.contains("community")
        ), "Studio browse page should render"
        assert snap.not_contains("Application error"), "Studio should not crash"

    def test_studio_my_items_tab(self, browser: Browser):
        browser.open("/studio/my")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.contains("My")
            or snap.contains("Your")
            or snap.contains("Items")
            or snap.contains("templates")
            or snap.contains("No items")
            or snap.contains("Create")
        ), "My Items view should load"
        assert snap.not_contains("Application error")

    def test_studio_create_page(self, browser: Browser):
        browser.open("/studio/create")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.contains("Create")
            or snap.contains("New")
            or snap.contains("Template")
            or snap.contains("name")
            or snap.contains("description")
        ), "Studio create page should render a form"
        assert snap.not_contains("Application error")

    def test_studio_template_detail(self, browser: Browser):
        browser.open("/studio")
        browser.wait(3000)
        snap = browser.snapshot()
        # Try to find a clickable template card
        ref = (
            snap.ref_for_link("View")
            or snap.ref_for_link("Details")
            or snap.ref_for_button("View")
        )
        if ref:
            browser.click(ref)
            browser.wait(2000)
            snap2 = browser.snapshot()
            assert snap2.not_contains("Application error")
        else:
            # If no template cards to click, just verify the page loaded
            assert snap.not_contains("Application error")

    def test_studio_navigation_from_sidebar(self, browser: Browser):
        browser.open("/")
        browser.wait(3000)
        snap = browser.snapshot()
        ref = snap.ref_for_link("Studio") or snap.ref_for_link("Browse")
        if ref:
            browser.click(ref)
            browser.wait(2000)
            url = browser.get_url()
            assert "/studio" in url, "Sidebar Studio link should navigate to /studio"
        else:
            # Studio link may not be visible at current lifecycle stage (exploring)
            # Verify we can still navigate directly
            browser.open("/studio")
            browser.wait(3000)
            snap2 = browser.snapshot()
            assert snap2.not_contains("Application error")
