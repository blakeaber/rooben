"""Section 17: Settings Page — 3 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestSettings:
    """Verify the settings page loads and allows configuration."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    # S17.1 ----------------------------------------------------------------
    def test_settings_page_loads(self, browser: Browser):
        browser.open("/settings")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), "Settings page crashed"

    # S17.2 ----------------------------------------------------------------
    def test_api_key_form_present(self, browser: Browser):
        browser.open("/settings")
        browser.wait(2000)
        snap = browser.snapshot()
        assert (
            snap.contains("API Key")
            or snap.contains("API")
            or snap.ref_for_textbox("key")
            or snap.ref_for_textbox("Key")
            or snap.ref_for_textbox("API")
        ), "No API key input found on settings page"

    # S17.3 ----------------------------------------------------------------
    def test_save_settings_interaction(self, browser: Browser):
        browser.open("/settings")
        browser.wait(2000)
        snap = browser.snapshot()
        input_ref = (
            snap.ref_for_textbox("key")
            or snap.ref_for_textbox("Key")
            or snap.ref_for_textbox("API")
            or snap.ref_for_textbox("Enter")
        )
        if input_ref:
            browser.fill(input_ref, "test-api-key-value")
            browser.wait(500)
        snap = browser.snapshot()
        save_ref = (
            snap.ref_for_button("Save")
            or snap.ref_for_button("Update")
            or snap.ref_for_button("Apply")
        )
        assert save_ref or input_ref, "Settings page has no interactive form elements"
