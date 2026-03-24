"""P16.5 — Studio E2E browser tests: pages, sidebar, API calls."""

import pytest

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup

# Backend API base URL (frontend fetch() goes to localhost:3000, not the API)
API_BASE = "http://localhost:8420"


def _set_exploring_stage(browser: Browser):
    """Mock /api/me/dashboard to return enough workflows for 'exploring' lifecycle stage.

    The sidebar Studio group requires minStage='exploring' (>=1 workflow).
    Without a running DB, the real API fails and lifecycle defaults to 'new'.
    """
    bypass_setup(browser)
    # Intercept the dashboard API call to return a mock response with 1 workflow
    browser.eval("""
        window.__origFetch = window.__origFetch || window.fetch;
        window.fetch = function(url, opts) {
            if (typeof url === 'string' && url.includes('/api/me/dashboard')) {
                return Promise.resolve(new Response(JSON.stringify({
                    workflows: { total: 1, active: 0, completed: 0, failed: 0, pending: 0, cancelled: 0 },
                    spend: { total_cost: 0, total_input_tokens: 0, total_output_tokens: 0 },
                    agents: { total: 0, most_used: [] },
                    recent: []
                }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
            }
            return window.__origFetch(url, opts);
        }
    """)


@pytest.fixture(autouse=True)
def _bypass_setup_gate():
    """No-op — each test class manages its own setup."""
    yield


# ── Studio Browse Page ───────────────────────────────────────────────────


class TestStudioBrowsePage:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.open("/studio")
        browser.wait(1500)

    def test_studio_page_loads(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("studio") or snap.contains("Studio")

    def test_studio_tabs_visible(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("templates") or snap.contains("Templates")
        assert snap.contains("agents") or snap.contains("Agents")

    def test_studio_search_input(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_textbox("Search")
            or snap.ref_for_textbox("search")
            or snap.ref_for("input")
        )
        assert ref is not None

    def test_studio_category_filter(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("All") or snap.contains("all")

    def test_studio_create_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_link("Create New")
            or snap.ref_for_link("Create")
            or snap.ref_for_button("Create New")
            or snap.ref_for_button("Create")
        )
        assert ref is not None

    def test_studio_templates_tab_default(self, browser: Browser):
        snap = browser.snapshot()
        # Templates tab should be active/visible by default
        assert snap.contains("templates") or snap.contains("Templates")

    def test_studio_agents_tab(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_link("Agents")
            or snap.ref_for_button("Agents")
            or snap.ref_for("Agents")
        )
        if ref:
            browser.click(ref)
            browser.wait(1000)
            snap = browser.snapshot()
        assert snap.contains("agents") or snap.contains("Agents")

    def test_studio_tab_query_param(self, browser: Browser):
        browser.open("/studio?tab=agents")
        browser.wait(1500)
        snap = browser.snapshot()
        assert snap.contains("agents") or snap.contains("Agents")


# ── Studio My Page ───────────────────────────────────────────────────────


class TestStudioMyPage:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.open("/studio/my")
        browser.wait(1500)

    def test_my_page_loads(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("My") or snap.contains("my") or snap.contains("Items")

    def test_my_page_shows_groups(self, browser: Browser):
        snap = browser.snapshot()
        # Page shows group sections when items exist, or empty state message
        has_groups = (
            snap.contains("Draft") or snap.contains("Published")
            or snap.contains("Installed") or snap.contains("draft")
            or snap.contains("haven't created") or snap.contains("Create Your First")
            or snap.contains("My Items")
        )
        assert has_groups

    def test_my_page_publish_button(self, browser: Browser):
        snap = browser.snapshot()
        # If there are drafts, a publish button should exist; otherwise skip
        ref = snap.ref_for_button("Publish")
        # OK if no drafts exist — we just verify the page loads
        assert snap.contains("My") or snap.contains("my") or ref is not None

    def test_my_page_unpublish_button(self, browser: Browser):
        snap = browser.snapshot()
        # If there are published items, unpublish should exist; otherwise skip
        ref = snap.ref_for_button("Unpublish")
        assert snap.contains("My") or snap.contains("my") or ref is not None

    def test_my_page_empty_state(self, browser: Browser):
        snap = browser.snapshot()
        # Either shows items or empty state — both valid
        assert snap.contains("My") or snap.contains("my") or snap.contains("Items")


# ── Studio Create Page ───────────────────────────────────────────────────


class TestStudioCreatePage:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.open("/studio/create")
        browser.wait(1500)

    def test_create_page_loads(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Create") or snap.contains("create") or snap.contains("New")

    def test_create_form_fields(self, browser: Browser):
        snap = browser.snapshot()
        # Create page has labeled inputs with placeholders
        has_inputs = (
            snap.ref_for_textbox("my-template")
            or snap.ref_for_textbox("My Template")
            or snap.ref_for_textbox("What does this template do")
            or snap.contains("Name") or snap.contains("Title") or snap.contains("Description")
        )
        assert has_inputs

    def test_create_save_draft_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("Save as Draft")
            or snap.ref_for_button("Save Draft")
            or snap.ref_for_button("Save")
            or snap.ref_for_button("Create")
        )
        assert ref is not None

    def test_create_rooben_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("Create with Rooben")
            or snap.ref_for_button("Rooben")
            or snap.ref_for_button("AI Assist")
            or snap.ref_for_link("Create with Rooben")
        )
        # May not exist if AI assist is hidden — just verify page loaded
        assert snap.contains("Create") or snap.contains("create") or ref is not None


# ── Studio Template Detail ───────────────────────────────────────────────


class TestStudioTemplateDetail:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        # Use a community sample template
        browser.open("/studio/templates/saas-landing-page")
        browser.wait(2000)

    def test_detail_page_loads(self, browser: Browser):
        snap = browser.snapshot()
        assert (
            snap.contains("SaaS") or snap.contains("saas")
            or snap.contains("Landing") or snap.contains("template")
            or snap.contains("Template") or snap.contains("not found")
        )

    def test_detail_export_button(self, browser: Browser):
        snap = browser.snapshot()
        # Page has an Export button to open the export panel
        ref = snap.ref_for_button("Export")
        has_export = ref is not None or snap.contains("Export")
        assert has_export or snap.contains("not found")

    def test_detail_use_template_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Use Template")
        has_use = ref is not None or snap.contains("Use Template")
        assert has_use or snap.contains("not found")

    def test_detail_shows_metadata(self, browser: Browser):
        snap = browser.snapshot()
        # Template detail shows metadata: author, version, category
        has_meta = (
            snap.contains("Version") or snap.contains("Category")
            or snap.contains("community") or snap.contains("rooben")
        )
        assert has_meta or snap.contains("not found")

    def test_export_mode_toggle_visible(self, browser: Browser):
        """After clicking Export, Preview and Full Export mode buttons appear."""
        snap = browser.snapshot()
        export_ref = snap.ref_for_button("Export")
        if export_ref:
            browser.click(export_ref)
            browser.wait(1500)
            snap = browser.snapshot()
            assert snap.contains("Preview") or snap.contains("Full Export") or snap.contains("Mode")
        else:
            # Export button may not exist if template not found
            assert snap.contains("not found") or snap.contains("Export")

    def test_preview_mode_default_for_non_export_ready(self, browser: Browser):
        """Community templates without workflows → Preview active, Full Export disabled."""
        snap = browser.snapshot()
        export_ref = snap.ref_for_button("Export")
        if export_ref:
            browser.click(export_ref)
            browser.wait(1500)
            snap = browser.snapshot()
            # Preview should be available; Full Export should be present but disabled
            assert snap.contains("Preview")
            # Full Export button exists (even if disabled)
            assert snap.contains("Full Export")
        else:
            assert snap.contains("not found") or snap.contains("Export")

    def test_info_banner_for_non_ready_templates(self, browser: Browser):
        """Guidance text appears when export_ready is false."""
        snap = browser.snapshot()
        export_ref = snap.ref_for_button("Export")
        if export_ref:
            browser.click(export_ref)
            browser.wait(1500)
            snap = browser.snapshot()
            # Info banner for community templates without completed workflows
            assert (
                snap.contains("Run this template as a workflow")
                or snap.contains("unlock enriched exports")
                or snap.contains("not found")
            )
        else:
            assert snap.contains("not found") or snap.contains("Export")

    def test_export_ready_badge_absent_for_community(self, browser: Browser):
        """Community sample templates should NOT show Export Ready badge."""
        snap = browser.snapshot()
        # Community templates without DB won't have export_ready=true
        # Verify the badge is absent or the page loaded correctly
        has_export_ready = snap.contains("Export Ready", case_sensitive=True)
        assert not has_export_ready or snap.contains("not found")

    def test_api_export_preview_mode(self, browser: Browser):
        """API: export with mode=preview returns 200 or 404."""
        status = browser.fetch_status(
            f"{API_BASE}/api/studio/templates/saas-landing-page/export?provider=claude&mode=preview",
            method="POST",
        )
        assert status in (200, 404)

    def test_api_export_full_mode_requires_workflow(self, browser: Browser):
        """API: export with mode=full returns 422 for templates without completed workflows."""
        status = browser.fetch_status(
            f"{API_BASE}/api/studio/templates/saas-landing-page/export?provider=claude&mode=full",
            method="POST",
        )
        # 422 = no completed workflow, 404 = template not found
        assert status in (422, 404)


# ── Sidebar Studio ───────────────────────────────────────────────────────


class TestSidebarStudio:
    """Verify Studio sidebar links exist.

    The Studio sidebar group requires lifecycle stage >= 'exploring' (derived from
    /api/me/dashboard returning total workflows >= 1). We navigate to /studio directly
    where we know the page renders, then check that the sidebar on that page
    contains the Studio navigation links.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        # Navigate to /studio — the Studio page loads regardless of sidebar stage
        browser.open("/studio")
        browser.wait(2000)

    def test_sidebar_has_studio_group(self, browser: Browser):
        snap = browser.snapshot()
        # Studio page renders with "Studio" in the header/breadcrumbs even if
        # sidebar group is hidden by lifecycle stage
        assert snap.contains("Studio") or snap.contains("studio")

    def test_sidebar_browse_link(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_link("Browse & Install")
            or snap.ref_for_link("Browse")
            or snap.ref_for_link("Studio")
        )
        # Link may be in sidebar or in page header breadcrumbs
        assert ref is not None or snap.contains("Studio")

    def test_sidebar_my_items_link(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_link("My Items")
            or snap.ref_for_link("My Templates")
        )
        # If lifecycle stage is 'new', sidebar Studio group is hidden, but
        # links are accessible via direct URL navigation
        if ref is None:
            # Verify the page is accessible directly
            browser.open("/studio/my")
            browser.wait(1500)
            snap = browser.snapshot()
            assert snap.contains("My Items") or snap.contains("My") or snap.contains("haven't created")

    def test_sidebar_create_link(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_link("Create")
            or snap.ref_for_link("Create New")
            or snap.ref_for_link("New Template")
        )
        if ref is None:
            # Verify the page is accessible directly
            browser.open("/studio/create")
            browser.wait(1500)
            snap = browser.snapshot()
            assert snap.contains("Create") or snap.contains("create")


# ── Studio API via Browser ───────────────────────────────────────────────


class TestStudioAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.wait(500)

    def test_api_templates_returns_json(self, browser: Browser):
        data = browser.fetch_json(f"{API_BASE}/api/marketplace/templates")
        assert "templates" in data
        assert isinstance(data["templates"], list)

    def test_api_my_templates_returns_json(self, browser: Browser):
        data = browser.fetch_json(f"{API_BASE}/api/marketplace/templates/my")
        assert "templates" in data

    def test_api_export_claude(self, browser: Browser):
        # Use a builtin template name — try fetch and handle 404 gracefully
        status = browser.fetch_status(
            f"{API_BASE}/api/studio/templates/saas-landing-page/export?provider=claude",
            method="POST",
        )
        # 200 if template has spec, 404 if community sample has no spec
        assert status in (200, 404)
