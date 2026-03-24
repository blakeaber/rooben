"""P15d — Enterprise governance & intelligence E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestOrgDashboardPage:
    """Browser tests for the /org/dashboard page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/dashboard")
        browser.wait(3000)
        # Non-org users get redirected to /org/setup
        url = browser.get_url()
        if "/org/setup" in url:
            snap = browser.snapshot()
            assert snap.contains("Team") or snap.contains("Enterprise") or snap.contains("Organization")
        else:
            snap = browser.wait_for_text("Dashboard", timeout_ms=10000)
            assert snap.contains("Dashboard")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_breadcrumbs(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Organization") or snap.contains("Org") or snap.contains("Dashboard")

    def test_tabs(self, browser: Browser):
        snap = browser.snapshot()
        has_tabs = (
            snap.contains("Overview")
            or snap.contains("Cost")
            or snap.contains("Quality")
            or snap.contains("Productivity")
        )
        assert has_tabs

    def test_stat_labels(self, browser: Browser):
        snap = browser.snapshot()
        has_stats = (
            snap.contains("Workflows")
            or snap.contains("Users")
            or snap.contains("Cost")
            or snap.contains("Success")
            or snap.contains("Total")
        )
        assert has_stats


@pytest.mark.requires_db
class TestAuditLogPage:
    """Browser tests for the /org/audit page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/audit")
        snap = browser.wait_for_text("Audit", timeout_ms=10000)
        assert snap.contains("Audit")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_export_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("Export")
            or snap.ref_for_button("Export JSON")
            or snap.ref_for_button("Export CSV")
        )
        assert ref is not None or snap.contains("Export")

    def test_apply_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Apply") or snap.ref_for_button("Filter")
        assert ref is not None or snap.contains("Apply") or snap.contains("Filter")

    def test_table_headers(self, browser: Browser):
        snap = browser.snapshot()
        has_headers = (
            snap.contains("Action")
            or snap.contains("User")
            or snap.contains("Timestamp")
            or snap.contains("Date")
        )
        assert has_headers


@pytest.mark.requires_db
class TestPoliciesPage:
    """Browser tests for the /org/policies page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/policies")
        snap = browser.wait_for_text("Polic", timeout_ms=10000)
        assert snap.contains("Polic")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_form_fields(self, browser: Browser):
        snap = browser.snapshot()
        has_fields = (
            snap.contains("Approved Models") or snap.contains("approved")
            or snap.contains("Budget") or snap.contains("budget")
            or snap.contains("Verification") or snap.contains("verification")
            or snap.contains("Content") or snap.contains("Policy")
        )
        assert has_fields

    def test_save_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Save") or snap.ref_for_button("Update")
        assert ref is not None or snap.contains("Save")


@pytest.mark.requires_db
class TestGovernanceAPIs:
    """API tests for governance endpoints (200 or 403)."""

    def test_dashboard_summary(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status("/api/org/dashboard")
        assert status in (200, 403)

    def test_dashboard_cost(self, browser: Browser):
        status = browser.fetch_status("/api/org/dashboard/cost")
        assert status in (200, 403)

    def test_dashboard_quality(self, browser: Browser):
        status = browser.fetch_status("/api/org/dashboard/quality")
        assert status in (200, 403)

    def test_dashboard_productivity(self, browser: Browser):
        status = browser.fetch_status("/api/org/dashboard/productivity")
        assert status in (200, 403)

    def test_dashboard_bottlenecks(self, browser: Browser):
        status = browser.fetch_status("/api/org/dashboard/bottlenecks")
        assert status in (200, 403)

    def test_audit_logs_list(self, browser: Browser):
        status = browser.fetch_status("/api/org/audit-logs")
        assert status in (200, 403)

    def test_audit_logs_export(self, browser: Browser):
        status = browser.fetch_status("/api/org/audit-logs/export")
        assert status in (200, 403)

    def test_policies_get(self, browser: Browser):
        status = browser.fetch_status("/api/org/policies")
        assert status in (200, 403)

    def test_policies_put(self, browser: Browser):
        status = browser.fetch_status("/api/org/policies", method="PUT", body={
            "approved_models": ["claude-sonnet-4-20250514"],
        })
        assert status in (200, 403, 422)
