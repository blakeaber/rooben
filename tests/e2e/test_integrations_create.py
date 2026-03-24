"""E2E: AI-Assisted Builder / Create integration page (P8)."""

from tests.e2e.browser import Browser


class TestAIBuilder:

    def test_wizard_loads(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        assert snap.contains("Describe")
        assert snap.contains("Plan")
        assert snap.contains("Build & Test")
        assert snap.ref_for_textbox("e.g., Connect to Slack"), "Textarea not found"

    def test_domain_tag_toggle(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        ref = snap.ref_for_button("software")
        assert ref, "software domain tag button not found"
        browser.click(ref)
        browser.wait(300)
        # Just verify the tag is still there and clickable
        snap = browser.snapshot()
        assert snap.contains("software")

    def test_textarea_enables_generate_button(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        ref = snap.ref_for_textbox("e.g., Connect to Slack")
        assert ref
        browser.fill(ref, "Connect to Slack for notifications")
        browser.wait(500)
        snap = browser.snapshot()
        assert snap.ref_for_button("Generate Plan"), "Generate Plan button not found"

    def test_generate_plan(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        ref = snap.ref_for_textbox("e.g., Connect to Slack")
        assert ref
        browser.fill(ref, "Connect to Slack for notifications")
        browser.wait(500)
        snap = browser.snapshot()
        gen_ref = snap.ref_for_button("Generate Plan")
        assert gen_ref
        browser.click(gen_ref)
        snap = browser.wait_for_text("Generated Plan", timeout_ms=10000)
        assert snap.contains("servers") or snap.contains("Server"), \
            "Generated plan should show servers"

    def test_back_button_from_plan(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        ref = snap.ref_for_textbox("e.g., Connect to Slack")
        assert ref
        browser.fill(ref, "GitHub integration")
        browser.wait(500)
        snap = browser.snapshot()
        gen_ref = snap.ref_for_button("Generate Plan")
        assert gen_ref
        browser.click(gen_ref)
        snap = browser.wait_for_text("Generated Plan", timeout_ms=10000)
        back_ref = snap.ref_for_button("Back")
        assert back_ref, "Back button not found on plan step"
        browser.click(back_ref)
        browser.wait(1000)
        snap = browser.snapshot()
        assert snap.contains("e.g.") or snap.contains("Describe"), \
            "Did not return to step 1"

    def test_full_install_flow(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        ref = snap.ref_for_textbox("e.g., Connect to Slack")
        assert ref
        browser.fill(ref, "Slack notifications for workflow alerts")
        browser.wait(500)
        snap = browser.snapshot()
        gen_ref = snap.ref_for_button("Generate Plan")
        assert gen_ref
        browser.click(gen_ref)
        snap = browser.wait_for_text("Generated Plan", timeout_ms=10000)
        install_ref = snap.ref_for_button("Install Integration")
        assert install_ref, "Install Integration button not found"
        browser.click(install_ref)
        snap = browser.wait_for_text("Integration Created", timeout_ms=10000)
        assert snap.contains("View All Integrations") or snap.contains("View Detail"), \
            "Success panel buttons missing"

    def test_view_created_integration(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        ref = snap.ref_for_textbox("e.g., Connect to Slack")
        assert ref
        browser.fill(ref, "Postgres query tool")
        browser.wait(500)
        snap = browser.snapshot()
        gen_ref = snap.ref_for_button("Generate Plan")
        assert gen_ref
        browser.click(gen_ref)
        snap = browser.wait_for_text("Generated Plan", timeout_ms=10000)
        install_ref = snap.ref_for_button("Install Integration")
        assert install_ref
        browser.click(install_ref)
        snap = browser.wait_for_text("Integration Created", timeout_ms=10000)
        detail_ref = snap.ref_for_button("View Detail") or snap.ref_for_link("View Detail")
        if detail_ref:
            browser.click(detail_ref)
            browser.wait(3000)
            snap = browser.snapshot()
            assert snap.contains("user"), "Detail page should show 'user' source"
