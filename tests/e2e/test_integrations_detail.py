"""E2E: Integration detail page (P8)."""

from tests.e2e.browser import Browser


class TestIntegrationDetailPage:

    def test_detail_page_loads(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        assert snap.contains("builtin"), "BUILTIN badge missing"
        assert snap.contains("Filesystem"), "Description missing"

    def test_information_panel(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        assert snap.contains("1.0.0"), "Version missing"
        assert snap.contains("builtin"), "Source missing"
        assert snap.contains("Medium"), "Cost tier missing"

    def test_domain_tags(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        for tag in ["software", "infrastructure", "devops"]:
            assert snap.contains(tag), f"Missing domain tag: {tag}"

    def test_no_env_vars_required(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        assert snap.contains("No environment variables"), "Missing 'no env vars' message"

    def test_env_vars_for_web_research(self, browser: Browser):
        browser.open("/integrations/web-research")
        snap = browser.wait_for_text("web-research")
        assert snap.contains("BRAVE_API_KEY"), "BRAVE_API_KEY not shown"
        assert snap.contains("Missing"), "'Missing' status not shown"

    def test_test_connection_button(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("Run Test")
        ref = snap.ref_for_button("Run Test")
        assert ref, "Run Test button not found"
        browser.click(ref)
        result_snap = browser.wait_for_text("checks passed", timeout_ms=15000)
        assert result_snap.contains("checks passed"), "Test connection did not show results"

    def test_no_edit_button_for_builtin(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        assert snap.not_contains("Edit Configuration"), "Edit button shown for builtin"

    def test_no_publish_button_for_builtin(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        assert snap.not_contains("Publish to Community"), "Publish button shown for builtin"

    def test_back_navigation(self, browser: Browser):
        browser.open("/integrations/coding")
        snap = browser.wait_for_text("coding")
        # Find the "← Integrations" breadcrumb link
        ref = snap.ref_for("Integrations")
        assert ref
        browser.click(ref)
        browser.wait_for_text("Integrations Hub")
        url = browser.get_url()
        assert "/integrations" in url

    def test_404_for_nonexistent_integration(self, browser: Browser):
        browser.open("/integrations/nonexistent-xyz-404")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.contains("not found") or snap.contains("404"), \
            "Expected 404 or 'not found' for nonexistent integration"
