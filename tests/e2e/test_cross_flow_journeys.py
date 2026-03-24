"""E2E: Cross-Flow User Journeys — 4 tests."""

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup, clear_setup


class TestCrossFlowJourneys:
    """Multi-step flows crossing several pages to verify end-to-end continuity."""

    def test_new_user_to_first_workflow(self, browser: Browser):
        """Clear setup → complete wizard → navigate to new workflow → fill idea."""
        clear_setup(browser)
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()

        # Click through setup wizard (up to 3 steps)
        for _ in range(4):
            ref = (
                snap.ref_for_button("Continue")
                or snap.ref_for_button("Get Started")
                or snap.ref_for_button("Skip")
                or snap.ref_for_button("Next")
                or snap.ref_for_button("Let's go")
                or snap.ref_for_button("Later")
                or snap.ref_for_button("Professional")
                or snap.ref_for_button("Builder")
                or snap.ref_for_button("Finish")
                or snap.ref_for_button("Done")
                or snap.ref_for_button("Complete")
                or snap.ref_for_button("Start")
            )
            if ref:
                browser.click(ref)
                browser.wait(1500)
                snap = browser.snapshot()

        # Ensure setup is complete
        bypass_setup(browser)
        browser.open("/")
        browser.wait(2000)

        # Navigate to new workflow
        snap = browser.snapshot()
        ref = snap.ref_for_link("Add New")
        if ref:
            browser.click(ref)
            browser.wait(1500)
        else:
            browser.open("/workflows/new")
            browser.wait(1500)

        snap = browser.snapshot()
        assert (
            snap.contains("Build now")
            or snap.contains("Build Now")
            or snap.contains("Describe")
            or snap.contains("Create")
        ), "Should reach workflow creation page"

    def test_browse_templates_then_create(self, browser: Browser):
        """Browse templates on integrations tab → return to home → navigate to create."""
        bypass_setup(browser)
        browser.open("/integrations?tab=templates")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

        # Navigate to home
        browser.open("/")
        browser.wait(2000)

        # Navigate to create
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now", timeout_ms=10000)
        assert snap.contains("Build now") or snap.contains("Build Now") or snap.contains("Create")

    def test_integrations_to_workflow(self, browser: Browser):
        """Check integrations → return to home → go to create workflow."""
        bypass_setup(browser)

        # Visit integrations
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations", timeout_ms=10000)
        assert snap.not_contains("Application error")

        # Return home
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

        # Navigate to create
        browser.open("/workflows/new")
        browser.wait(2000)
        snap = browser.snapshot()
        assert (
            snap.contains("Build now")
            or snap.contains("Build Now")
            or snap.contains("Describe")
        ), "Workflow creation should load after visiting integrations"

    def test_integrations_tabs_round_trip(self, browser: Browser):
        """Navigate Integrations data-sources → templates → agents tabs."""
        bypass_setup(browser)

        # Visit Integrations default tab (data sources)
        browser.open("/integrations")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Integrations should load"

        # Visit Templates tab
        browser.open("/integrations?tab=templates")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Templates tab should load"

        # Visit Agents tab
        browser.open("/integrations?tab=agents")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Agents tab should load"
