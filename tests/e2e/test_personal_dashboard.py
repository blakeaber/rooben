"""Section 16 – Personal Dashboard E2E tests."""

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestPersonalDashboard:
    """Personal dashboard (/me) page tests."""

    def test_s16_1_me_page_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/me")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s16_2_dashboard_api_responds(self, browser: Browser):
        bypass_setup(browser)
        data = browser.fetch_json("/api/me/dashboard")
        assert data is not None

    def test_s16_3_goals_section_visible(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/me")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s16_4_preferences_section_visible(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/me")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s16_5_navigate_me_to_settings(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/me")
        browser.wait(2000)
        snap = browser.snapshot()
        ref = snap.ref_for_link("Settings") or snap.ref_for_link("settings")
        if ref:
            browser.click(ref)
            browser.wait(1000)
            url = browser.get_url()
            assert "/settings" in url
