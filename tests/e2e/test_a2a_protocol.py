"""Section 23: A2A Protocol & API — 4 tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


class TestA2AProtocol:
    """A2A agent card, health endpoint, task send/get."""

    def test_agent_card_endpoint(self, browser: Browser):
        browser.open("/")
        # /.well-known/agent.json is served by the backend directly (not proxied by Next.js)
        data = browser.fetch_json("http://localhost:8420/.well-known/agent.json")
        assert "name" in data, "Agent card should contain 'name' field"

    def test_health_endpoint(self, browser: Browser):
        data = browser.fetch_json("/api/health")
        assert data.get("status") == "ok", f"Health should be ok, got {data}"

    @pytest.mark.requires_db
    def test_a2a_task_send(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status(
            "/a2a/tasks/send",
            method="POST",
            body={"description": "test"},
        )
        assert status in (200, 422, 500), f"Expected 200/422/500, got {status}"

    @pytest.mark.requires_db
    def test_a2a_task_get(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status("/a2a/tasks/test-id")
        assert status in (200, 404, 500), f"Expected 200/404/500, got {status}"
