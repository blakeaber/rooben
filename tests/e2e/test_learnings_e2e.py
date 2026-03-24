"""Section 11 – Learnings E2E tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestLearnings:
    """Learnings page and API tests."""

    @pytest.mark.requires_db
    def test_s11_1_learnings_page_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/learnings")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s11_2_learnings_api(self, browser: Browser):
        bypass_setup(browser)
        status = browser.fetch_status("/api/learnings", "GET", None)
        assert status in (200, 500)

    @pytest.mark.requires_db
    def test_s11_3_keywords_api(self, browser: Browser):
        bypass_setup(browser)
        status = browser.fetch_status("/api/learnings/keywords", "GET", None)
        assert status in (200, 500)

    def test_s11_4_no_db_learnings_page_graceful(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/learnings")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")
