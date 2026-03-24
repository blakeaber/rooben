"""Shared fixtures for e2e browser tests."""

from __future__ import annotations

import shutil

import pytest

from tests.e2e.browser import Browser

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line("markers", "requires_db: test needs a running database")
    config.addinivalue_line("markers", "slow: marks tests as slow (multi-step workflow)")


# ---------------------------------------------------------------------------
# Session-scoped: verify agent-browser is installed
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _check_agent_browser():
    if not shutil.which("agent-browser"):
        pytest.skip("agent-browser CLI not installed (npm i -g agent-browser)")


# ---------------------------------------------------------------------------
# Session-scoped: verify servers are reachable
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _check_servers():
    """Ensure backend + frontend are reachable before running any test."""
    import urllib.request

    for url in ["http://localhost:8420/api/health", "http://localhost:3000/api/health"]:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status != 200:
                    pytest.skip(f"Server at {url} returned {resp.status}")
        except Exception:
            pytest.skip(f"Server not reachable at {url} — start backend + frontend first")


# ---------------------------------------------------------------------------
# Module-scoped browser: one browser instance per test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def browser():
    b = Browser()
    yield b
    b.close()


# ---------------------------------------------------------------------------
# Module-scoped: bypass P16 SetupGate for all existing tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _bypass_setup_gate(browser):
    """Bypass SetupGate and enable full sidebar for all existing tests."""
    from tests.e2e.helpers import bypass_setup

    browser.open("/")
    browser.wait(1000)
    bypass_setup(browser)
    browser.open("/")
    browser.wait(1000)
