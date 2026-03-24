"""Section 20: Branding — 3 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestBranding:
    """Verify Rooben branding, light theme, and consistency."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    # S20.1 ----------------------------------------------------------------
    def test_app_name_is_rubin(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.contains("Rooben"), "App name 'Rooben' not found on home page"
        assert snap.not_contains("Autobot"), "'Autobot' should not appear in user-facing text"

    # S20.2 ----------------------------------------------------------------
    def test_light_theme_no_dark_mode(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        bg_color = browser.eval(
            "getComputedStyle(document.body).backgroundColor"
        )
        # Light backgrounds: white, off-white, light gray
        # rgb values where all channels are > 200 indicate a light background
        assert bg_color is not None, "Could not read background color"
        # browser.eval returns JSON-encoded strings — strip quotes
        color_str = str(bg_color).strip('"').strip("'")
        # Parse rgb(r, g, b) — all channels should be >= 200 for light theme
        if "rgb" in color_str:
            inner = color_str.split("(", 1)[1].rstrip(")")
            nums = [int(x.strip()) for x in inner.split(",")[:3]]
            assert all(n >= 200 for n in nums), f"Background too dark: {color_str}"

    # S20.3 ----------------------------------------------------------------
    def test_consistent_branding_across_pages(self, browser: Browser):
        pages = ["/", "/settings", "/integrations"]
        for page in pages:
            browser.open(page)
            browser.wait(1500)
            snap = browser.snapshot()
            assert snap.contains("Rooben"), f"'Rooben' missing on {page}"
