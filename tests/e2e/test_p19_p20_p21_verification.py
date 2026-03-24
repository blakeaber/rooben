"""P19.5 / P20 / P21 post-implementation verification tests.

Run headed:
    AGENT_BROWSER_HEADED=true pytest tests/e2e/test_p19_p20_p21_verification.py -v -s --timeout=120
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


# ---------------------------------------------------------------------------
# P19.5 — Hotfix checks
# ---------------------------------------------------------------------------

class TestP195Hotfixes:

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    def test_health_endpoint(self, browser: Browser):
        """GET /api/health returns 200."""
        status = browser.fetch_status("http://localhost:8420/api/health")
        assert status == 200

    def test_export_bar_workflow_guard(self, browser: Browser):
        """ExportBar should not crash when no workflow is selected."""
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        # Page should render without error overlay
        assert snap.not_contains("Unhandled Runtime Error")
        assert snap.not_contains("TypeError")

    def test_init_sql_schema(self):
        """init.sql exists and contains expected tables."""
        schema = Path("scripts/init.sql").read_text()
        for table in ("workflows", "workflow_runs", "integrations"):
            assert table in schema.lower(), f"Table '{table}' not in init.sql"


# ---------------------------------------------------------------------------
# P20 — Brand, UX, legal pages
# ---------------------------------------------------------------------------

class TestP20Brand:

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    def test_sidebar_shows_rooben(self, browser: Browser):
        """Sidebar brand should say 'Rooben', not 'Rubin' or 'Autobot'."""
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.contains("Rooben"), "Brand 'Rooben' not found on home page"
        assert snap.not_contains("Autobot"), "'Autobot' should not appear"

    def test_landing_page_brand(self, browser: Browser):
        """Landing page shows Rooben brand and persona sections."""
        browser.open("/landing")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.contains("Rooben"), "'Rooben' missing on landing page"
        # Check persona sections
        for persona in ("Builder", "Operator", "Optimizer"):
            assert snap.contains(persona), f"Persona '{persona}' missing on landing"

    def test_terms_page_loads(self, browser: Browser):
        browser.open("/terms")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.contains("terms") or snap.contains("Terms"), "Terms page failed to load"

    def test_privacy_page_loads(self, browser: Browser):
        browser.open("/privacy")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.contains("privacy") or snap.contains("Privacy"), "Privacy page failed to load"

    def test_docs_page_loads(self, browser: Browser):
        browser.open("/docs")
        browser.wait(2000)
        snap = browser.snapshot()
        # Docs page should have tab-like navigation
        assert snap.contains("docs") or snap.contains("Docs") or snap.contains("documentation"), \
            "Docs page failed to load"

    def test_dark_mode_toggle_exists(self, browser: Browser):
        """Dark mode toggle should be present in sidebar."""
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        # Look for theme toggle element
        has_toggle = (
            snap.contains("dark mode")
            or snap.contains("theme")
            or snap.ref_for("theme") is not None
            or snap.ref_for("dark") is not None
        )
        assert has_toggle, "Dark mode toggle not found"

    def test_no_autobot_localstorage(self, browser: Browser):
        """localStorage should have no autobot_* keys."""
        browser.open("/")
        browser.wait(2000)
        result = browser.eval(
            "JSON.stringify(Object.keys(localStorage).filter(k=>k.startsWith('autobot')))"
        )
        parsed = browser._parse_eval_result(result)
        assert parsed in ("[]", ""), f"Found autobot localStorage keys: {parsed}"

    def test_landing_spec_challenge(self, browser: Browser):
        """Landing page should have a spec challenge section."""
        browser.open("/landing")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.contains("challenge") or snap.contains("spec"), \
            "Spec challenge section missing from landing page"


# ---------------------------------------------------------------------------
# P21 — OSS/Pro readiness
# ---------------------------------------------------------------------------

class TestP21OSSPro:

    def test_no_autobot_on_dashboard_pages(self, browser: Browser):
        """No 'Autobot' text on any dashboard page."""
        bypass_setup(browser)
        pages = ["/", "/integrations", "/schedules", "/agents", "/learnings", "/cost"]
        for page in pages:
            browser.open(page)
            browser.wait(1500)
            snap = browser.snapshot()
            assert snap.not_contains("Autobot"), f"'Autobot' found on {page}"

    def test_cli_importable(self):
        """rooben.cli is importable with a main function."""
        mod = importlib.import_module("rooben.cli")
        assert hasattr(mod, "main"), "rooben.cli.main not found"

    def test_license_exists(self):
        """LICENSE file exists and contains MIT."""
        license_path = Path("LICENSE")
        assert license_path.exists(), "LICENSE file missing"
        content = license_path.read_text()
        assert "MIT" in content, "LICENSE does not contain 'MIT'"

    def test_public_api_version(self):
        """rooben.public_api is importable with API_VERSION."""
        mod = importlib.import_module("rooben.public_api")
        assert hasattr(mod, "API_VERSION"), "rooben.public_api.API_VERSION not found"
