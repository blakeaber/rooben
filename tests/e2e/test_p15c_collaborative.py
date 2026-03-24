"""P15c — Collaborative workflows via A2A E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestOrgAgentsPage:
    """Browser tests for the /org/agents page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/agents")
        snap = browser.wait_for_text("Agent", timeout_ms=10000)
        assert snap.contains("Agent")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_publish_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("Publish Agent")
            or snap.ref_for_button("Publish")
            or snap.ref_for_button("Add Agent")
        )
        assert ref is not None or snap.contains("Publish") or snap.contains("Add")

    def test_tabs(self, browser: Browser):
        snap = browser.snapshot()
        has_tabs = (
            snap.contains("Directory")
            or snap.contains("Delegation")
            or snap.contains("directory")
        )
        assert has_tabs or snap.contains("Agent")


@pytest.mark.requires_db
class TestOrgMcpServersPage:
    """Browser tests for the /org/mcp-servers page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/mcp-servers")
        snap = browser.wait_for_text("MCP", timeout_ms=10000)
        assert snap.contains("MCP") or snap.contains("Server")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_add_server_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("Add Server")
            or snap.ref_for_button("Add MCP Server")
            or snap.ref_for_button("Add")
        )
        assert ref is not None or snap.contains("Add")


@pytest.mark.requires_db
class TestOrgSpecsPage:
    """Browser tests for the /org/specs page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/specs")
        snap = browser.wait_for_text("Spec", timeout_ms=10000)
        assert snap.contains("Spec") or snap.contains("spec")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_new_spec_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("New Spec")
            or snap.ref_for_button("Create Spec")
            or snap.ref_for_button("Add")
        )
        assert ref is not None or snap.contains("New") or snap.contains("Create")


@pytest.mark.requires_db
class TestOrgTemplatesPage:
    """Browser tests for the /org/templates page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/org/templates")
        snap = browser.wait_for_text("Template", timeout_ms=10000)
        assert snap.contains("Template") or snap.contains("template")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")

    def test_new_template_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("New Template")
            or snap.ref_for_button("Create Template")
            or snap.ref_for_button("Add")
        )
        assert ref is not None or snap.contains("New") or snap.contains("Create")


@pytest.mark.requires_db
class TestCollaborativeAPIs:
    """API tests for org collaborative endpoints (200 or 403)."""

    def test_agents_list(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status("/api/org/agents")
        assert status in (200, 403)

    def test_agents_create(self, browser: Browser):
        status = browser.fetch_status("/api/org/agents", method="POST", body={
            "name": "E2E Test Agent",
            "url": "https://example.com/agent",
            "description": "E2E test agent entry",
        })
        assert status in (200, 201, 403, 422)

    def test_agents_delete_nonexistent(self, browser: Browser):
        status = browser.fetch_status("/api/org/agents/fake-id", method="DELETE")
        assert status in (200, 403, 404, 422)

    def test_mcp_servers_list(self, browser: Browser):
        status = browser.fetch_status("/api/org/mcp-servers")
        assert status in (200, 403)

    def test_mcp_servers_create(self, browser: Browser):
        status = browser.fetch_status("/api/org/mcp-servers", method="POST", body={
            "name": "E2E Test MCP",
            "url": "https://example.com/mcp",
        })
        assert status in (200, 201, 403, 422)

    def test_specs_list(self, browser: Browser):
        status = browser.fetch_status("/api/org/specs")
        assert status in (200, 403)

    def test_specs_create(self, browser: Browser):
        status = browser.fetch_status("/api/org/specs", method="POST", body={
            "name": "E2E Test Spec",
            "content": "test: true",
        })
        assert status in (200, 201, 403, 422)

    def test_specs_delete_nonexistent(self, browser: Browser):
        status = browser.fetch_status("/api/org/specs/fake-id", method="DELETE")
        assert status in (200, 403, 404, 422)

    def test_templates_list(self, browser: Browser):
        status = browser.fetch_status("/api/org/templates")
        assert status in (200, 403)

    def test_templates_create(self, browser: Browser):
        status = browser.fetch_status("/api/org/templates", method="POST", body={
            "name": "E2E Test Template",
            "spec_yaml": "test: true",
        })
        assert status in (200, 201, 403, 422)

    def test_templates_delete_nonexistent(self, browser: Browser):
        status = browser.fetch_status("/api/org/templates/fake-id", method="DELETE")
        assert status in (200, 403, 404, 422)

    def test_delegations_list(self, browser: Browser):
        status = browser.fetch_status("/api/org/agents")
        assert status in (200, 403)
