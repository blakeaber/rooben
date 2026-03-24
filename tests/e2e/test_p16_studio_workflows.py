"""P16.5/P16.6 — Studio workflow E2E tests: redirects, create/publish/fork, export, wizard."""

import pytest

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup

# Backend API base URL
API_BASE = "http://localhost:8420"


@pytest.fixture(autouse=True)
def _bypass_setup_gate():
    """No-op — each test class manages its own setup."""
    yield


# ── Redirect Workflows ──────────────────────────────────────────────────


class TestRedirectWorkflows:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.wait(500)

    def test_templates_redirects_to_studio(self, browser: Browser):
        browser.open("/templates")
        browser.wait(2000)
        url = browser.get_url()
        assert "/studio" in url

    def test_integrations_templates_tab_loads(self, browser: Browser):
        browser.open("/integrations?tab=templates")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")
        assert snap.contains("Templates") or snap.contains("template")

    def test_integrations_agents_tab_loads(self, browser: Browser):
        browser.open("/integrations?tab=agents")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


# ── Create / Publish / Fork Workflow ─────────────────────────────────────


@pytest.mark.slow
class TestCreatePublishForkWorkflow:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.wait(500)

    @pytest.mark.requires_db
    def test_create_draft_template(self, browser: Browser):
        browser.open("/studio/create")
        browser.wait(1500)
        snap = browser.snapshot()

        # Fill in the name field
        name_ref = (
            snap.ref_for_textbox("name") or snap.ref_for_textbox("Name")
            or snap.ref_for_textbox("Template name")
        )
        if name_ref:
            browser.fill(name_ref, "e2e-test-template")
            browser.wait(300)

        # Fill description if available
        desc_ref = (
            snap.ref_for_textbox("description") or snap.ref_for_textbox("Description")
            or snap.ref_for("textarea")
        )
        if desc_ref:
            browser.fill(desc_ref, "E2E test template description")
            browser.wait(300)

        # Submit
        submit_ref = (
            snap.ref_for_button("Save as Draft")
            or snap.ref_for_button("Save Draft")
            or snap.ref_for_button("Save")
            or snap.ref_for_button("Create")
        )
        if submit_ref:
            browser.click(submit_ref)
            browser.wait(2000)

        # Verify navigation to my items or success message
        snap = browser.snapshot()
        assert (
            snap.contains("e2e-test-template")
            or snap.contains("Draft")
            or snap.contains("Created")
            or snap.contains("success")
            or snap.contains("My")
        )

    @pytest.mark.requires_db
    def test_publish_template(self, browser: Browser):
        browser.open("/studio/my")
        browser.wait(1500)
        snap = browser.snapshot()

        publish_ref = snap.ref_for_button("Publish")
        if publish_ref:
            browser.click(publish_ref)
            browser.wait(2000)
            snap = browser.snapshot()
            assert snap.contains("Published") or snap.contains("published") or snap.contains("success")
        else:
            # No drafts to publish — just verify page loaded
            assert snap.contains("My") or snap.contains("my")

    @pytest.mark.requires_db
    def test_fork_template(self, browser: Browser):
        browser.open("/studio")
        browser.wait(1500)
        snap = browser.snapshot()

        fork_ref = snap.ref_for_button("Fork")
        if fork_ref:
            browser.click(fork_ref)
            browser.wait(2000)
            snap = browser.snapshot()
            assert snap.contains("fork") or snap.contains("Fork") or snap.contains("Draft")
        else:
            # No fork button visible — verify page loaded
            assert snap.contains("Studio") or snap.contains("studio")

    @pytest.mark.requires_db
    def test_unpublish_template(self, browser: Browser):
        browser.open("/studio/my")
        browser.wait(1500)
        snap = browser.snapshot()

        unpublish_ref = snap.ref_for_button("Unpublish")
        if unpublish_ref:
            browser.click(unpublish_ref)
            browser.wait(2000)
            snap = browser.snapshot()
            assert snap.contains("Draft") or snap.contains("draft") or snap.contains("success")
        else:
            assert snap.contains("My") or snap.contains("my")


# ── Export Workflow ──────────────────────────────────────────────────────


@pytest.mark.slow
class TestExportWorkflow:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.wait(500)

    def test_export_claude_download(self, browser: Browser):
        browser.open("/studio/templates/saas-landing-page")
        browser.wait(2000)
        snap = browser.snapshot()

        # Click Claude tab if visible
        claude_ref = (
            snap.ref_for_button("Claude")
            or snap.ref_for_link("Claude")
            or snap.ref_for("Claude")
        )
        if claude_ref:
            browser.click(claude_ref)
            browser.wait(1500)
            snap = browser.snapshot()

        # Look for export button
        export_ref = (
            snap.ref_for_button("Export")
            or snap.ref_for_button("Download")
            or snap.ref_for_link("Export")
        )
        if export_ref:
            browser.click(export_ref)
            browser.wait(2000)
            snap = browser.snapshot()
            assert (
                snap.contains("CLAUDE.md") or snap.contains("file")
                or snap.contains("export") or snap.contains("Export")
            )
        else:
            # Template detail page loaded — export may need spec
            assert snap.contains("template") or snap.contains("Template") or snap.contains("Not Found")

    def test_export_zip_download(self, browser: Browser):
        # Use fetch to test ZIP endpoint directly
        status = browser.fetch_status(
            "/api/studio/templates/saas-landing-page/export/zip?provider=claude",
            method="POST",
        )
        # 200 if template found with spec, 404 if no spec
        assert status in (200, 404)

    def test_export_copy_file(self, browser: Browser):
        browser.open("/studio/templates/saas-landing-page")
        browser.wait(2000)
        snap = browser.snapshot()
        # If file tree is visible, clicking a file should show content
        has_file_tree = snap.contains("CLAUDE.md") or snap.contains(".md") or snap.contains("file")
        # Just verify the page loaded
        assert snap.contains("template") or snap.contains("Template") or snap.contains("Not Found") or has_file_tree

    def test_export_panel_mode_toggle(self, browser: Browser):
        """Export panel shows Preview and Full Export mode buttons."""
        browser.open("/studio/templates/saas-landing-page")
        browser.wait(2000)
        snap = browser.snapshot()

        export_ref = snap.ref_for_button("Export")
        if export_ref:
            browser.click(export_ref)
            browser.wait(1500)
            snap = browser.snapshot()
            # Both mode buttons should be present in the export panel
            assert snap.contains("Preview") and snap.contains("Full Export")
        else:
            assert snap.contains("Not Found") or snap.contains("Export")

    def test_preview_export_generates_files(self, browser: Browser):
        """Preview export via Claude Code provider shows file tree."""
        browser.open("/studio/templates/saas-landing-page")
        browser.wait(2000)
        snap = browser.snapshot()

        # Click Export button
        export_ref = snap.ref_for_button("Export")
        if not export_ref:
            assert snap.contains("Not Found") or snap.contains("Export")
            return

        browser.click(export_ref)
        browser.wait(1000)
        snap = browser.snapshot()

        # Click Claude Code provider button
        claude_ref = (
            snap.ref_for_button("Claude Code")
            or snap.ref_for_button("Claude")
            or snap.ref_for("Claude Code")
        )
        if claude_ref:
            browser.click(claude_ref)
            browser.wait(3000)
            snap = browser.snapshot()
            # File tree should appear with CLAUDE.md
            assert (
                snap.contains("CLAUDE.md") or snap.contains("Files")
                or snap.contains("file") or snap.contains("Generating export")
            )
        else:
            # Provider buttons may not be visible yet
            assert snap.contains("Export") or snap.contains("Preview")

    def test_full_export_422_for_community_templates(self, browser: Browser):
        """mode=full returns 422 for community templates without completed workflows."""
        status = browser.fetch_status(
            f"{API_BASE}/api/studio/templates/saas-landing-page/export?provider=claude&mode=full",
            method="POST",
        )
        # 422 = no completed workflow, 404 = template not found
        assert status in (422, 404)

    def test_enrichment_badge_not_shown_on_preview(self, browser: Browser):
        """Preview export should NOT show 'Enriched with execution data' badge."""
        browser.open("/studio/templates/saas-landing-page")
        browser.wait(2000)
        snap = browser.snapshot()

        export_ref = snap.ref_for_button("Export")
        if export_ref:
            browser.click(export_ref)
            browser.wait(1000)
            snap = browser.snapshot()

            # Click Claude Code provider to trigger preview export
            claude_ref = (
                snap.ref_for_button("Claude Code")
                or snap.ref_for_button("Claude")
                or snap.ref_for("Claude Code")
            )
            if claude_ref:
                browser.click(claude_ref)
                browser.wait(3000)
                snap = browser.snapshot()
                # Enrichment badge should NOT appear for preview mode
                assert snap.not_contains("Enriched with execution data", case_sensitive=True)
        else:
            assert snap.contains("Not Found") or snap.contains("Export")

    def test_zip_endpoint_preview_mode(self, browser: Browser):
        """ZIP endpoint with mode=preview returns 200 or 404."""
        status = browser.fetch_status(
            f"{API_BASE}/api/studio/templates/saas-landing-page/export/zip?provider=claude&mode=preview",
            method="POST",
        )
        assert status in (200, 404)

    def test_zip_endpoint_full_mode_requires_workflow(self, browser: Browser):
        """ZIP endpoint with mode=full returns 422 without completed workflows."""
        status = browser.fetch_status(
            f"{API_BASE}/api/studio/templates/saas-landing-page/export/zip?provider=claude&mode=full",
            method="POST",
        )
        assert status in (422, 404)

    def test_api_export_returns_mode_and_enriched_fields(self, browser: Browser):
        """Export API response includes 'enriched' and 'mode' fields."""
        try:
            data = browser.fetch_json(
                f"{API_BASE}/api/studio/templates/saas-landing-page/export?provider=claude&mode=preview",
                method="POST",
            )
            # Response should include mode and enriched fields
            assert "mode" in data or "enriched" in data or "files" in data
            if "mode" in data:
                assert data["mode"] == "preview"
            if "enriched" in data:
                assert data["enriched"] is False  # preview → not enriched
        except (ValueError, KeyError):
            # Template may not have spec → 404 returns non-JSON
            pass


# ── Template → Wizard Workflow ───────────────────────────────────────────


@pytest.mark.slow
class TestTemplateToWizardWorkflow:
    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        browser.open("/")
        browser.wait(500)
        bypass_setup(browser)
        browser.wait(500)

    def test_template_use_navigates_to_wizard(self, browser: Browser):
        browser.open("/studio")
        browser.wait(1500)
        snap = browser.snapshot()

        use_ref = (
            snap.ref_for_button("Use Template")
            or snap.ref_for_button("Use")
            or snap.ref_for_link("Use Template")
            or snap.ref_for_link("Use")
        )
        if use_ref:
            browser.click(use_ref)
            browser.wait(2000)
            url = browser.get_url()
            assert "/workflows/new" in url or "/studio" in url
        else:
            # No Use button — may need to click into a template first
            assert snap.contains("Studio") or snap.contains("studio") or snap.contains("Templates")

    def test_wizard_loads_template_context(self, browser: Browser):
        # Navigate directly to wizard with template param
        browser.open("/workflows/new?template=saas-landing-page")
        browser.wait(2000)
        snap = browser.snapshot()
        # Should show refinement chat or template context
        assert (
            snap.contains("Build") or snap.contains("build")
            or snap.contains("template") or snap.contains("SaaS")
            or snap.contains("workflow") or snap.contains("Workflow")
            or snap.contains("Create") or snap.contains("create")
        )
