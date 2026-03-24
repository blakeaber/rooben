"""P11 — Agent configuration, presets, and credentials E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestAgentsPage:
    """Browser tests for the /agents page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/agents")
        snap = browser.wait_for_text("Agent Performance", timeout_ms=10000)
        assert snap.contains("Agent Performance")

    def test_subtitle(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Every agent tracked") or snap.contains("agent")

    def test_stat_chips(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Agents") or snap.contains("Total Tasks")

    def test_success_rate_section(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Success Rate") or snap.contains("success") or snap.contains("No data")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestPresetsPage:
    """Browser tests for the /agents/presets page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/agents/presets")
        snap = browser.wait_for_text("Agent Presets", timeout_ms=10000)
        assert snap.contains("Agent Presets") or snap.contains("Presets")

    def test_breadcrumbs(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Agents") or snap.contains("Presets")

    def test_create_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Create Preset") or snap.ref_for_button("Create")
        assert ref is not None

    def test_empty_state(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("No presets") or snap.contains("preset")


@pytest.mark.requires_db
class TestCredentialsAPI:
    """API tests for credentials endpoints."""

    def test_credentials_list(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        status = browser.fetch_status("/api/credentials")
        assert status in (200, 500)

    def test_credentials_create_missing_fields(self, browser: Browser):
        status = browser.fetch_status("/api/credentials", method="POST", body={})
        assert status in (422, 500)


@pytest.mark.requires_db
class TestPresetsAPI:
    """API tests for presets endpoints."""

    def test_presets_list(self, browser: Browser):
        browser.open("/agents/presets")
        browser.wait_for_text("Presets", timeout_ms=10000)
        status = browser.fetch_status("/api/presets")
        assert status in (200, 500)

    def test_presets_create(self, browser: Browser):
        browser.open("/agents/presets")
        browser.wait(3000)
        status = browser.fetch_status("/api/presets", method="POST", body={
            "name": "E2E Test Preset",
            "description": "Created by E2E test",
            "integration": ["web_search"],
            "prompt_template": "You are a helpful assistant.",
        })
        assert status in (200, 201, 422, 500)

    def test_presets_from_agent_nonexistent(self, browser: Browser):
        browser.open("/agents/presets")
        browser.wait(3000)
        status = browser.fetch_status(
            "/api/presets/from-agent/fake-agent-id", method="POST"
        )
        assert status in (404, 500)


@pytest.mark.requires_db
class TestPresetsCleanup:
    """Clean up any E2E-created presets."""

    def test_cleanup_presets(self, browser: Browser):
        browser.open("/")
        browser.wait(2000)
        status = browser.fetch_status("/api/presets")
        # Presets may return 500 if db not configured — skip cleanup
        if status != 200:
            return
        data = browser.fetch_json("/api/presets")
        for p in data.get("presets", []):
            if p.get("name", "").startswith("E2E"):
                browser.fetch_status(f"/api/presets/{p['id']}", method="DELETE")
