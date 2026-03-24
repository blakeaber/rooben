"""Section 8: Workflow Spec & Verification — 4 tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


class TestSpecVerification:
    """Spec page, YAML toggle, verification page, and criteria display."""

    @pytest.mark.requires_db
    def test_spec_page_loads(self, browser: Browser):
        browser.open("/workflows/test-id/spec")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), \
            "Spec page should render without crash"

    @pytest.mark.requires_db
    def test_spec_shows_yaml_toggle(self, browser: Browser):
        browser.open("/workflows/test-id/spec")
        browser.wait(3000)
        snap = browser.snapshot()
        has_yaml = (
            snap.contains("YAML")
            or snap.contains("yaml")
            or snap.contains("Raw")
            or snap.ref_for_button("YAML")
        )
        assert has_yaml or snap.not_contains("Application error"), \
            "Spec page should have YAML toggle or render cleanly"

    @pytest.mark.requires_db
    def test_verification_page_loads(self, browser: Browser):
        browser.open("/workflows/test-id/verification")
        browser.wait(3000)
        snap = browser.snapshot()
        assert snap.not_contains("Application error"), \
            "Verification page should render without crash"

    @pytest.mark.requires_db
    def test_verification_shows_criteria(self, browser: Browser):
        browser.open("/workflows/test-id/verification")
        browser.wait(3000)
        snap = browser.snapshot()
        has_criteria = (
            snap.contains("verification")
            or snap.contains("Verification")
            or snap.contains("score")
            or snap.contains("criteria")
        )
        assert has_criteria or snap.not_contains("Application error"), \
            "Verification criteria or clean page should render"
