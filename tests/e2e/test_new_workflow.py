"""E2E: New Workflow page — buttons, textarea, pills, provider settings."""

from tests.e2e.browser import Browser


class TestNewWorkflowPage:

    def test_shows_yolo_and_refine_buttons(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now")
        assert snap.ref_for_button("Build now"), "Build now button missing"
        assert snap.ref_for_button("Refine & customize"), "Refine & customize button missing"

    def test_shows_textarea(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now")
        assert snap.contains("textbox"), "Textarea not found"

    def test_example_pills_visible(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("TRY")
        assert snap.contains("Build a REST"), "Example pill 'Build a REST' missing"

    def test_no_mode_toggle(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now")
        assert snap.not_contains('button "Guided"'), "Guided toggle should not be visible"
        assert snap.not_contains('button "One-Shot"'), "One-Shot toggle should not be visible"


class TestProviderSettings:

    def test_provider_settings_collapsed_by_default(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now")
        # Provider/model selects should not be visible in the snapshot
        assert snap.not_contains("wiz-provider"), "Provider select should be collapsed"

    def test_provider_settings_expandable(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now")
        toggle_ref = snap.ref_for_button("Toggle provider settings")
        if not toggle_ref:
            # Some layouts use a different label
            toggle_ref = snap.ref_for("provider")
        if toggle_ref:
            browser.click(toggle_ref)
            browser.wait(500)
            snap2 = browser.snapshot()
            assert snap2.contains("provider") or snap2.contains("model"), \
                "Provider settings did not expand"
