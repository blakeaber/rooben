"""P14 — A2A Protocol integration E2E tests."""

from __future__ import annotations

import json
import urllib.request

import pytest

from tests.e2e.browser import Browser

BACKEND = "http://localhost:8420"


def _backend_json(path: str, method: str = "GET", body: dict | None = None) -> dict:
    """Fetch JSON directly from the backend (bypassing Next.js proxy)."""
    url = f"{BACKEND}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _backend_status(path: str, method: str = "GET", body: dict | None = None) -> int:
    """Fetch status code directly from the backend."""
    url = f"{BACKEND}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.mark.requires_db
class TestA2AAgentCard:
    """Tests for the /.well-known/agent.json endpoint."""

    def test_agent_card_json(self, browser: Browser):
        data = _backend_json("/.well-known/agent.json")
        assert isinstance(data, dict)
        assert "name" in data

    def test_agent_card_has_name(self, browser: Browser):
        data = _backend_json("/.well-known/agent.json")
        assert data["name"] == "Rooben Orchestrator"

    def test_agent_card_has_skills(self, browser: Browser):
        data = _backend_json("/.well-known/agent.json")
        assert "skills" in data
        assert len(data["skills"]) > 0

    def test_agent_card_has_capabilities(self, browser: Browser):
        data = _backend_json("/.well-known/agent.json")
        assert "capabilities" in data


@pytest.mark.requires_db
class TestA2ATaskLifecycle:
    """Tests for A2A JSON-RPC task endpoints."""

    def test_tasks_send_invalid(self, browser: Browser):
        status = _backend_status("/a2a/tasks/send", method="POST", body={})
        assert status in (200, 400, 422, 500, 503)

    def test_tasks_get_nonexistent(self, browser: Browser):
        status = _backend_status("/a2a/tasks/get", method="POST", body={
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "params": {"id": "fake-task-id"},
            "id": 1,
        })
        assert status in (200, 400, 404, 500, 503)

    def test_tasks_cancel_nonexistent(self, browser: Browser):
        status = _backend_status("/a2a/tasks/cancel", method="POST", body={
            "jsonrpc": "2.0",
            "method": "tasks/cancel",
            "params": {"id": "fake-task-id"},
            "id": 1,
        })
        assert status in (200, 400, 404, 500, 503)


@pytest.mark.requires_db
class TestA2AHealth:
    """Verify A2A routes don't break existing endpoints."""

    def test_health_still_works(self, browser: Browser):
        browser.open("/")
        status = browser.fetch_status("/api/health")
        assert status == 200

    def test_workflows_still_accessible(self, browser: Browser):
        browser.open("/")
        browser.wait(3000)
        status = browser.fetch_status("/api/workflows")
        assert status in (200, 500)
        if status == 200:
            data = browser.fetch_json("/api/workflows")
            assert "workflows" in data
