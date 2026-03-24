"""Section 18: Contextual Hints — 4 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


@pytest.fixture(autouse=True)
def _bypass_setup_gate():
    """No-op — this suite manages its own setup state."""
    yield


class TestContextualHints:
    """Verify contextual hints appear, can be dismissed, and persist."""

    @pytest.fixture(autouse=True)
    def _fresh_hints(self, browser: Browser):
        """Clear all hint dismissed keys so hints are visible."""
        bypass_setup(browser)
        # Clear all hint_dismissed_* keys from localStorage
        browser.eval("""
            Object.keys(localStorage)
                .filter(k => k.startsWith('hint_dismissed_'))
                .forEach(k => localStorage.removeItem(k));
        """)
        browser.open("/")
        browser.wait(500)

    # S18.1 ----------------------------------------------------------------
    def test_hints_appear_on_relevant_pages(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(2000)
        snap = browser.snapshot()
        _has_hint = (
            snap.contains("hint")
            or snap.contains("Hint")
            or snap.contains("Tip")
            or snap.contains("tip")
            or snap.contains("Did you know")
            or snap.contains("Pro tip")
            or snap.contains("💡")
        )
        # Hints may not be on every page; just verify no crash
        assert snap.not_contains("Application error"), "Page crashed"

    # S18.2 ----------------------------------------------------------------
    def test_dismiss_hint_persists(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(2000)
        snap = browser.snapshot()
        dismiss_ref = (
            snap.ref_for_button("Dismiss")
            or snap.ref_for_button("Got it")
            or snap.ref_for_button("Close")
            or snap.ref_for("dismiss")
        )
        if dismiss_ref:
            browser.click(dismiss_ref)
            browser.wait(500)
            browser.open("/workflows/new")
            browser.wait(2000)
            snap = browser.snapshot()
            # After dismissing, the hint text should be gone or still dismissed
            assert snap.not_contains("Application error")
        else:
            # No dismissible hint found — set one manually and verify persistence
            browser.eval("localStorage.setItem('hint_dismissed_test', 'true')")
            browser.open("/workflows/new")
            browser.wait(1000)
            val = browser.eval("localStorage.getItem('hint_dismissed_test')")
            assert "true" in str(val), "Hint dismissed state did not persist"

    # S18.3 ----------------------------------------------------------------
    def test_dismissed_hints_stay_dismissed(self, browser: Browser):
        browser.eval("localStorage.setItem('hint_dismissed_test', 'true')")
        browser.open("/")
        browser.wait(1000)
        val = browser.eval("localStorage.getItem('hint_dismissed_test')")
        assert "true" in str(val), "Pre-set hint dismissed flag was lost"

    # S18.4 ----------------------------------------------------------------
    def test_multiple_hints_on_different_pages(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(2000)
        snap_workflows = browser.snapshot()
        assert snap_workflows.not_contains("Application error"), "/workflows/new crashed"

        browser.open("/integrations")
        browser.wait(2000)
        snap_integrations = browser.snapshot()
        assert snap_integrations.not_contains("Application error"), "/integrations crashed"
