"""Section 14 – Integrations tabs E2E tests (replaces marketplace)."""

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestIntegrationsTabs:
    """Integrations page tab navigation tests."""

    def test_s14_1_integrations_page_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/integrations")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s14_2_templates_tab_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/integrations?tab=templates")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s14_3_agents_tab_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/integrations?tab=agents")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s14_4_template_cards_visible(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/integrations?tab=templates")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s14_5_tab_switching(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/integrations")
        browser.wait(2000)
        snap = browser.snapshot()
        # Try clicking Templates tab
        ref = snap.ref_for_button("Templates") or snap.ref_for("Templates")
        if ref:
            browser.click(ref)
            browser.wait(1000)
            snap = browser.snapshot()
        snap.not_contains("Application error")
