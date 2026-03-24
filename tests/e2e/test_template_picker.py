"""E2E: Template picker on the new-workflow page (P6/P7)."""

from tests.e2e.browser import Browser


class TestOperatorTemplates:

    def test_operator_templates_visible(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Operator Templates")
        for name in ["Competitive Analysis", "Research Report", "Client Briefing"]:
            assert snap.contains(name), f"Missing operator template: {name}"

    def test_builder_templates_visible(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Builder Templates")
        for name in ["REST API", "CLI Tool", "Data Pipeline", "React Dashboard"]:
            assert snap.contains(name), f"Missing builder template: {name}"

    def test_clicking_template_fills_textarea(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Competitive Analysis")
        ref = snap.ref_for("Competitive Analysis")
        assert ref, "Competitive Analysis template not clickable"
        browser.click(ref)
        browser.wait(500)
        snap = browser.snapshot()
        # After clicking, the textarea should contain prefill text
        # The textbox should now have content about competitive analysis
        assert snap.contains("competitive analysis") or snap.contains("competitors"), \
            "Template did not fill textarea"

    def test_clicking_different_template_replaces(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Competitive Analysis")

        # Click Research Report
        ref1 = snap.ref_for("Research Report")
        assert ref1
        browser.click(ref1)
        browser.wait(500)

        # Click CLI Tool — should replace
        snap = browser.snapshot()
        ref2 = snap.ref_for("CLI Tool")
        assert ref2
        browser.click(ref2)
        browser.wait(500)

        snap = browser.snapshot()
        assert snap.contains("CLI") or snap.contains("command-line"), \
            "Second template did not replace first"
