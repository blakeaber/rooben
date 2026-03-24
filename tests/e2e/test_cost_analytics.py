"""Section 9 – Cost Analytics E2E tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestCostAnalytics:
    """Cost analytics page and API tests."""

    @pytest.mark.requires_db
    def test_s9_1_cost_page_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/cost")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s9_2_cost_summary_api(self, browser: Browser):
        bypass_setup(browser)
        data = browser.fetch_json("/api/cost/summary")
        assert "total_cost" in data

    @pytest.mark.requires_db
    def test_s9_3_cost_timeseries_api(self, browser: Browser):
        bypass_setup(browser)
        data = browser.fetch_json("/api/cost/timeseries")
        assert data is not None

    def test_s9_4_no_db_cost_page_graceful(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/cost")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")
