"""Docker-compose smoke tests — exercises the demo overlay stack end-to-end.

Brings up the full `make demo` stack (postgres + mcp-gateway + api + dashboard
with the seeded demo workflow), asserts all 4 services reach healthy state,
and probes key HTTP endpoints including the dashboard's reverse proxy to the
API (regression guard for the Phase E bake-in-at-build-time issue).

Marked `docker`. Default `pytest tests/` runs should be invoked with
`-m "not docker"` to skip these; a dedicated CI job runs `pytest -m docker`
in an environment that has Docker available.

Uses subprocess + httpx (both already deps) — no additional Python packages.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.docker

ROOT = Path(__file__).resolve().parent.parent

COMPOSE_FILES = ["-f", "docker-compose.yml", "-f", "docker-compose.demo.yml"]
SERVICES = ("postgres", "mcp-gateway", "api", "dashboard")

API_BASE = "http://localhost:8420"
DASH_BASE = "http://localhost:3000"


def _compose(
    *args: str, check: bool = True, timeout: int = 60
) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", *COMPOSE_FILES, *args]
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ────────────────────────────────────────────────────────────────────────────
# Session fixtures — skip when docker isn't available; bring up once per module
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _docker_available():
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available")
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10, text=True
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("docker daemon not responding")
    if r.returncode != 0:
        pytest.skip("docker daemon not reachable")


@pytest.fixture(scope="module")
def docker_stack():
    """Bring up the demo stack with --wait; tear down and remove volumes at end.

    `--wait` blocks until every service with a healthcheck reports healthy
    (or 3 minutes pass); if any service fails to become healthy the command
    returns non-zero and the fixture raises — the test exposes the compose
    logs for debugging.
    """
    _compose("down", "-v", check=False)

    try:
        _compose("up", "-d", "--wait", "--build", timeout=600)
    except subprocess.CalledProcessError as exc:
        logs = _compose("logs", check=False, timeout=60)
        raise AssertionError(
            f"compose up failed (exit {exc.returncode}):\n"
            f"stderr: {exc.stderr}\n\n"
            f"service logs:\n{logs.stdout[-4000:]}"
        ) from exc

    time.sleep(2)  # small settle for routing

    yield

    _compose("down", "-v", check=False, timeout=120)


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────


def test_compose_up_all_services_healthy(docker_stack):
    """All four services reach the `healthy` state within the compose --wait window."""
    result = _compose("ps", "--format", "json")
    rows = [
        json.loads(line)
        for line in result.stdout.strip().splitlines()
        if line.strip()
    ]
    states = {row["Service"]: row.get("Health", "") for row in rows}

    for svc in SERVICES:
        assert svc in states, f"service {svc!r} missing from compose ps; saw {states}"
        assert states[svc] == "healthy", (
            f"service {svc!r} is not healthy (got {states[svc]!r})"
        )


def test_api_health_returns_ok(docker_stack):
    r = httpx.get(f"{API_BASE}/api/health", timeout=10)
    assert r.status_code == 200, f"api /api/health returned {r.status_code}"
    assert r.json() == {"status": "ok"}


def test_api_openapi_schema_available(docker_stack):
    """OpenAPI schema is reachable and advertises a non-trivial route surface."""
    r = httpx.get(f"{API_BASE}/openapi.json", timeout=10)
    assert r.status_code == 200

    schema = r.json()
    assert schema.get("openapi", "").startswith("3."), (
        f"unexpected openapi version: {schema.get('openapi')!r}"
    )
    assert isinstance(schema.get("paths"), dict)
    # Sanity lower bound — if the route count collapses, something is wrong.
    assert len(schema["paths"]) >= 10, (
        f"openapi schema lists only {len(schema['paths'])} paths; expected >= 10"
    )


def test_dashboard_home_renders_with_rooben_title(docker_stack):
    """Dashboard home returns 200 and includes 'Rooben' in the document title."""
    r = httpx.get(f"{DASH_BASE}/", timeout=10)
    assert r.status_code == 200
    assert "<title>" in r.text, "home page HTML missing <title>"
    # Title at Phase E: "Rooben — Your taste is the product"
    assert "Rooben" in r.text, (
        f"'Rooben' not found in dashboard home HTML:\n{r.text[:500]}"
    )


def test_seeded_demo_workflow_visible_via_api(docker_stack):
    """The demo seed ran: /api/workflows/demo returns the expected workflow shape."""
    r = httpx.get(f"{API_BASE}/api/workflows/demo", timeout=10)
    assert r.status_code == 200

    data = r.json()
    wf = data["workflow"]
    assert wf["id"] == "demo"
    assert wf["status"] == "completed"
    assert wf["total_tasks"] == 3
    assert wf["completed_tasks"] == 3
    assert wf["failed_tasks"] == 0

    assert data["workstreams"], "demo workflow has no workstreams"
    assert data["workstreams"][0]["id"] == "demo-ws-main"


def test_dashboard_proxies_api_through_nextjs_rewrites(docker_stack):
    """Regression guard for Phase E Dockerfile ARG fix.

    The dashboard's next.config.ts rewrites `/api/*` to the internal api
    service. If NEXT_INTERNAL_API_URL isn't baked in at build time, the
    proxy defaults to 127.0.0.1:8420 which doesn't resolve inside the
    dashboard container — manifesting as 500s here.
    """
    r = httpx.get(f"{DASH_BASE}/api/workflows/demo", timeout=10)
    assert r.status_code == 200, (
        f"dashboard proxy returned {r.status_code}; "
        f"check NEXT_INTERNAL_API_URL build arg"
    )
    data = r.json()
    assert data["workflow"]["id"] == "demo"
