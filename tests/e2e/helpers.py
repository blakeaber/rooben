"""Shared helpers for Rooben e2e tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.e2e.browser import Browser


def bypass_setup(browser: Browser) -> None:
    """Set localStorage to skip SetupWizard. Call after browser.open()."""
    browser.eval('localStorage.setItem("rooben_setup_complete", "true")')
    browser.eval('localStorage.setItem("rooben_welcome_dismissed", "true")')


def clear_setup(browser: Browser) -> None:
    """Clear all localStorage flags so SetupWizard/WelcomeHero show."""
    browser.eval('localStorage.removeItem("rooben_setup_complete")')
    browser.eval('localStorage.removeItem("rooben_persona")')
    browser.eval('localStorage.removeItem("rooben_welcome_dismissed")')
    browser.eval('localStorage.removeItem("rooben_api_key")')
    browser.eval(
        'Object.keys(localStorage).filter(k=>k.startsWith("hint_dismissed_")).forEach(k=>localStorage.removeItem(k))'
    )
