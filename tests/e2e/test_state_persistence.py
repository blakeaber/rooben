"""Section 22: State Persistence — 4 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup, clear_setup


@pytest.fixture(autouse=True)
def _bypass_setup_gate():
    """No-op — this suite manages its own setup state."""
    yield


class TestStatePersistence:
    """Verify localStorage-based state survives page reloads."""

    # S22.1 ----------------------------------------------------------------
    def test_setup_state_persists_across_reload(self, browser: Browser):
        bypass_setup(browser)
        browser.open("/")
        browser.wait(1000)
        # Reload the page
        browser.open("/")
        browser.wait(1000)
        snap = browser.snapshot()
        # Setup wizard should NOT reappear
        has_wizard = snap.contains("Get Started") and snap.contains("persona")
        setup_done = browser.eval("localStorage.getItem('rooben_setup_done')")
        assert setup_done == "true" or not has_wizard, "Setup wizard reappeared after reload"

    # S22.2 ----------------------------------------------------------------
    def test_persona_persists(self, browser: Browser):
        bypass_setup(browser)
        browser.eval("localStorage.setItem('rooben_persona', 'builder')")
        browser.open("/")
        browser.wait(1000)
        val = browser.eval("localStorage.getItem('rooben_persona')")
        assert "builder" in str(val), f"Persona not persisted: {val}"

    # S22.3 ----------------------------------------------------------------
    def test_welcome_dismissed_persists(self, browser: Browser):
        bypass_setup(browser)
        browser.eval("localStorage.setItem('rooben_welcome_dismissed', 'true')")
        browser.open("/")
        browser.wait(1000)
        val = browser.eval("localStorage.getItem('rooben_welcome_dismissed')")
        assert "true" in str(val), f"Welcome dismissed not persisted: {val}"

    # S22.4 ----------------------------------------------------------------
    def test_clear_setup_resets_all_state(self, browser: Browser):
        bypass_setup(browser)
        clear_setup(browser)
        browser.open("/")
        browser.wait(1000)
        setup_done = browser.eval("localStorage.getItem('rooben_setup_done')")
        assert setup_done is None or setup_done == "null" or setup_done == "", \
            f"Setup state not cleared: {setup_done}"
