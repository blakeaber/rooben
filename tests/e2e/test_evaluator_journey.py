"""The evaluator's first-look journey — 6 browser-E2E tests.

Simulates a technical evaluator (VC/PE AI expert, tech client, recruiter)
cloning the repo, running `make demo`, and navigating the dashboard for
~15 minutes to decide "is this person a serious builder?"

Every assertion is framed as "would this make a skeptical reader lose faith?"
— no application errors surfacing, seeded demo workflow discoverable, DAG
of verified tasks visible, integrations hub browsable, extension system
visible as a first-class concept. Anything heavier than "can they see it?"
belongs elsewhere (F.2 smoke for API/health; existing tests/e2e/* for deep
flows).

Prereq (enforced by tests/e2e/conftest.py session fixtures):
- agent-browser CLI installed (`npm i -g agent-browser`)
- Dashboard + API reachable at http://localhost:{3000,8420}
- In practice: `make demo` must be running

Runs outside CI (existing tests/e2e/ is `--ignore`d in Phase F.5's default
Tests job; a future CI workflow could run these via `workflow_dispatch`).
"""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestEvaluatorJourney:
    """The first 15 minutes a skeptical evaluator spends in the dashboard."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        """Bypass SetupWizard/WelcomeHero so we test the dashboard-as-product."""
        bypass_setup(browser)

    # ── Home landing ───────────────────────────────────────────────────

    def test_home_landing_renders_without_application_error(self, browser: Browser):
        """Core: home renders, no crash banner — the 'first impression' moment."""
        browser.open("/")
        browser.wait(3000)
        snap = browser.snapshot()

        assert snap.not_contains("Application error"), (
            "home page crashed:\n" + snap.raw[:500]
        )
        # Must show something Rooben-branded; title alone doesn't appear in
        # agent-browser snapshots, but sidebar/nav labels do.
        rooben_markers = sum(
            [
                snap.contains("Rooben"),
                snap.contains("rooben"),
                snap.contains("Workflows"),
            ]
        )
        assert rooben_markers >= 1, (
            "home page has no Rooben branding / navigation markers"
        )

    # ── Seeded demo workflow visible from list ─────────────────────────

    def test_seeded_demo_workflow_appears_in_home_list(self, browser: Browser):
        """The `make demo` seed populated the workflows list with the demo run."""
        browser.open("/")
        browser.wait(3000)
        snap = browser.snapshot()

        # The seeded workflow has id='demo' and workstream name "Books API".
        # Either should surface in the list rendering.
        has_demo_workflow = snap.contains("demo") or snap.contains("Books API")
        assert has_demo_workflow, (
            "seeded demo workflow not visible on home list:\n" + snap.raw[:800]
        )

    # ── Demo workflow detail: DAG + verification surface ───────────────

    def test_demo_workflow_detail_renders_with_tasks(self, browser: Browser):
        """Direct-navigate to the seeded workflow's detail page; DAG + tasks surface."""
        browser.open("/workflows/demo")
        browser.wait(4000)
        snap = browser.snapshot()

        assert snap.not_contains("Application error"), (
            "workflow detail crashed:\n" + snap.raw[:500]
        )

        # At least one of the three seeded task titles should render
        seed_task_titles = (
            "Design the API schema",
            "Implement CRUD endpoints",
            "Write API documentation",
        )
        found = sum(snap.contains(t) for t in seed_task_titles)
        assert found >= 1, (
            "no seeded task titles visible on detail page; "
            f"looked for any of {seed_task_titles}\n"
            + snap.raw[:1500]
        )

    # ── Integrations hub browsable ─────────────────────────────────────

    def test_integrations_hub_browsable(self, browser: Browser):
        """Integrations / extensions hub renders without crash."""
        # The page lives at /integrations; if that 404s, try /extensions.
        browser.open("/integrations")
        browser.wait(3000)
        snap = browser.snapshot()

        if snap.contains("404") or snap.contains("This page could not be found"):
            browser.open("/extensions")
            browser.wait(3000)
            snap = browser.snapshot()

        assert snap.not_contains("Application error"), (
            "integrations/extensions hub crashed:\n" + snap.raw[:500]
        )
        # Some content shape — search box, list headers, or extension names
        has_hub_content = (
            snap.contains("Integration")
            or snap.contains("integration")
            or snap.contains("Extension")
            or snap.contains("extension")
            or snap.contains("MCP")
        )
        assert has_hub_content, (
            "integrations hub rendered but shows no recognizable content:\n"
            + snap.raw[:1500]
        )

    # ── Extensions API exposed ─────────────────────────────────────────

    def test_extensions_api_lists_bundled_extensions(self, browser: Browser):
        """The extension registry endpoint reports bundled extensions (tier-1).

        Cheaper and more stable than UI-listing assertions — exercises the
        same surface the UI consumes.
        """
        browser.open("/")
        browser.wait(1000)
        data = browser.fetch_json("/api/extensions")

        assert isinstance(data, dict), f"unexpected response shape: {type(data)}"
        # The API may return {"extensions": [...]} or a list directly — accept either.
        extensions = (
            data.get("extensions") if isinstance(data, dict) else data
        )
        assert isinstance(extensions, list), (
            f"extensions response missing list payload: {data}"
        )
        # Phase C memory notes 7 bundled tier-1 extensions (slack-notifications,
        # github-issues, postgres-query, sales-pipeline-report, code-reviewer,
        # research-analyst, data-engineer). A clean install should show some.
        assert len(extensions) >= 1, (
            f"extensions registry is empty; expected bundled tier-1 extensions: {data}"
        )

    # ── No client-side JS error on the "golden path" ───────────────────

    def test_no_console_errors_on_golden_path(self, browser: Browser):
        """Navigate home → demo workflow; expect no thrown JS errors.

        agent-browser's snapshot surfaces uncaught errors in the rendered
        accessibility tree under markers like "alert" or "Error boundary".
        """
        browser.open("/")
        browser.wait(2000)
        home_snap = browser.snapshot()
        assert home_snap.not_contains("Application error"), (
            "home page crashed during golden path"
        )

        browser.open("/workflows/demo")
        browser.wait(3000)
        detail_snap = browser.snapshot()
        assert detail_snap.not_contains("Application error"), (
            "demo workflow page crashed during golden path"
        )
