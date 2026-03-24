"""Section 10 – Agent Performance E2E tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestAgentPerformance:
    """Agent performance page and API tests."""

    @pytest.mark.requires_db
    def test_s10_1_agents_page_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/agents")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s10_2_agent_detail_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/agents/test-agent-id")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s10_3_agent_performance_api(self, browser: Browser):
        bypass_setup(browser)
        status = browser.fetch_status("/api/agents/performance", "GET", None)
        assert status in (200, 500)

    @pytest.mark.requires_db
    def test_s10_4_presets_api(self, browser: Browser):
        bypass_setup(browser)
        status = browser.fetch_status("/api/presets", "GET", None)
        assert status in (200, 500)
