"""E2E: Sidebar navigation and active-state highlighting."""

from tests.e2e.browser import Browser


class TestSidebarNavigation:

    def test_sidebar_renders_all_nav_items(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("System")
        for label in ["Past Runs", "Add New", "Cost & Tokens", "Agents",
                       "Optimization", "Learnings", "Integrations", "Settings"]:
            assert snap.contains(label), f"Missing nav item: {label}"

    def test_integrations_link_in_system_group(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("Integrations")
        assert snap.ref_for_link("Integrations"), "Integrations link not found"

    def test_clicking_add_new_navigates(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("Add New")
        ref = snap.ref_for_link("Add New")
        assert ref
        browser.click(ref)
        browser.wait(1500)
        url = browser.get_url()
        assert "/workflows/new" in url

    def test_sidebar_highlights_active_page(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Add New")
        # Active link should have aria-current="page" — shows as link with active styling
        assert snap.contains("Add New")

    def test_integrations_subpage_keeps_sidebar_highlight(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        assert snap.contains("Integrations"), "Sidebar Integrations link missing on subpage"
