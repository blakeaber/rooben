"""Section 15 – Org Pages E2E tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestOrgPages:
    """Org-level page rendering tests."""

    def test_s15_1_org_dashboard_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/dashboard")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    def test_s15_2_org_setup_page_loads(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/setup")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_3_org_agents_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/agents")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_4_org_learnings_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/learnings")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_5_org_templates_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/templates")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_6_org_policies_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/policies")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_7_org_audit_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/audit")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_8_org_mcp_servers_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/mcp-servers")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_9_org_specs_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/specs")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")

    @pytest.mark.requires_db
    def test_s15_10_org_recommendations_page(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/org/recommendations")
        browser.wait(2000)
        snap = browser.snapshot()
        snap.not_contains("Application error")
