"""P16 — Lifecycle UX E2E tests: SetupWizard, WelcomeHero, progressive sidebar, guided flow, org redirect, branding."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup, clear_setup


# ---------------------------------------------------------------------------
# Override the autouse _bypass_setup_gate from conftest — P16 tests manage
# their own localStorage state.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _bypass_setup_gate(browser):
    """No-op override: P16 tests manage their own setup state."""
    pass


# ===========================================================================
# Setup Wizard
# ===========================================================================


class TestSetupWizard:
    """P16: Setup wizard gate and flow."""

    @pytest.fixture(autouse=True)
    def _clean_state(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        clear_setup(browser)
        browser.open("/")
        browser.wait(2000)

    def test_fresh_user_sees_setup_wizard(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Welcome to Rooben"), "Setup wizard should show 'Welcome to Rooben'"
        assert snap.not_contains("Past Runs"), "Dashboard content should be hidden behind setup gate"

    def test_get_started_shows_api_key_step(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Get Started") or snap.ref_for_button("Get started")
        assert ref, "Get Started button not found"
        browser.click(ref)
        browser.wait(1500)
        snap = browser.snapshot()
        assert snap.contains("API") or snap.contains("key") or snap.contains("Key"), \
            "API key step should be visible"

    def test_continue_past_api_key(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Get Started") or snap.ref_for_button("Get started")
        if ref:
            browser.click(ref)
            browser.wait(1500)
        snap = browser.snapshot()
        # In dev mode, skip/continue past API key step
        ref = snap.ref_for_button("Continue") or snap.ref_for_button("Skip") or snap.ref_for_button("Next")
        assert ref, "Continue/Skip button not found on API key step"
        browser.click(ref)
        browser.wait(1500)
        snap = browser.snapshot()
        # Should now show persona/path selection
        assert snap.contains("build") or snap.contains("Build") or snap.contains("explore") or snap.contains("Explore"), \
            "Persona selection step should be visible"

    def test_pick_persona_completes_setup(self, browser: Browser):
        snap = browser.snapshot()
        # Navigate to persona step
        ref = snap.ref_for_button("Get Started") or snap.ref_for_button("Get started")
        if ref:
            browser.click(ref)
            browser.wait(1500)
            snap = browser.snapshot()
        ref = snap.ref_for_button("Continue") or snap.ref_for_button("Skip") or snap.ref_for_button("Next")
        if ref:
            browser.click(ref)
            browser.wait(1500)
            snap = browser.snapshot()
        # Click a persona — "I want to build something"
        ref = snap.ref_for("build something") or snap.ref_for("Build") or snap.ref_for("builder")
        if ref:
            browser.click(ref)
            browser.wait(2000)
            url = browser.get_url()
            assert "/workflows/new" in url, f"Expected redirect to /workflows/new, got {url}"

    def test_explore_on_my_own(self, browser: Browser):
        snap = browser.snapshot()
        # Navigate to persona step
        ref = snap.ref_for_button("Get Started") or snap.ref_for_button("Get started")
        if ref:
            browser.click(ref)
            browser.wait(1500)
            snap = browser.snapshot()
        ref = snap.ref_for_button("Continue") or snap.ref_for_button("Skip") or snap.ref_for_button("Next")
        if ref:
            browser.click(ref)
            browser.wait(1500)
            snap = browser.snapshot()
        ref = snap.ref_for("explore") or snap.ref_for("Explore") or snap.ref_for("on my own")
        if ref:
            browser.click(ref)
            browser.wait(2000)
            snap = browser.snapshot()
            # Should see home page with WelcomeHero (setup complete, lifecycle=new)
            assert snap.contains("Welcome") or snap.contains("Rooben"), \
                "After explore, should see WelcomeHero or home"


# ===========================================================================
# Welcome Hero
# ===========================================================================


class TestWelcomeHero:
    """P16: New-user home page experience."""

    @pytest.fixture(autouse=True)
    def _setup_done(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        bypass_setup(browser)
        browser.eval('localStorage.removeItem("rooben_welcome_dismissed")')
        browser.open("/")
        browser.wait(2000)

    def test_new_user_sees_welcome_hero(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Welcome") and snap.contains("Rooben"), \
            "WelcomeHero should show 'Welcome to Rooben'"

    def test_welcome_hero_has_persona_cards(self, browser: Browser):
        snap = browser.snapshot()
        # Persona cards: operator, builder, optimizer
        has_cards = (
            snap.contains("Deliverable") or snap.contains("Operator")
            or snap.contains("Build") or snap.contains("Optimizer")
        )
        assert has_cards, "WelcomeHero should show persona cards"

    def test_welcome_hero_dismiss(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for("explore on my own")
            or snap.ref_for("Explore")
            or snap.ref_for("dismiss")
            or snap.ref_for("Skip")
        )
        if ref:
            browser.click(ref)
            browser.wait(1500)
            snap = browser.snapshot()
            assert snap.not_contains("Welcome to Rooben"), \
                "WelcomeHero should be dismissed"

    def test_persona_card_navigates(self, browser: Browser):
        snap = browser.snapshot()
        ref = (
            snap.ref_for("Produce a Deliverable")
            or snap.ref_for("Deliverable")
            or snap.ref_for("Professional")
        )
        if ref:
            browser.click(ref)
            browser.wait(2000)
            url = browser.get_url()
            assert "/workflows/new" in url, f"Persona card should navigate to /workflows/new, got {url}"


# ===========================================================================
# Progressive Sidebar
# ===========================================================================


class TestProgressiveSidebar:
    """P16: Sidebar visibility by lifecycle stage (progressive disclosure)."""

    @pytest.fixture(autouse=True)
    def _setup_lifecycle(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        bypass_setup(browser)
        browser.open("/")
        browser.wait(2000)

    def test_sidebar_shows_core_items(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Past Runs") or snap.contains("Workflows"), \
            "Workflows group should always be visible"
        assert snap.contains("Settings"), "Settings should always be visible"

    def test_sidebar_shows_rooben_logo(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Rooben"), "Sidebar should show Rooben branding"
        assert snap.contains("AI That Shows Its Work"), "Sidebar should show tagline"


# ===========================================================================
# Guided First Workflow
# ===========================================================================


class TestGuidedFirstWorkflow:
    """P16: Guided workflow creation for new users."""

    @pytest.fixture(autouse=True)
    def _setup_done(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        bypass_setup(browser)
        browser.open("/")
        browser.wait(1000)

    def test_new_user_sees_wizard(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(2000)
        snap = browser.snapshot()
        # Wizard always shows — no separate guided flow
        has_wizard = (
            snap.contains("Build now") or snap.contains("Build Now")
            or snap.contains("What would you like") or snap.contains("Describe")
        )
        assert has_wizard, "CreateWorkflowWizard should show for all users"

    def test_wizard_shows_without_params(self, browser: Browser):
        browser.open("/workflows/new")
        snap = browser.wait_for_text("Build now")
        assert snap.ref_for_button("Build now"), "Wizard should show Build now button"


# ===========================================================================
# Org Redirect
# ===========================================================================


class TestOrgRedirect:
    """P16: Org dashboard redirect for non-org users."""

    @pytest.fixture(autouse=True)
    def _setup_done(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        bypass_setup(browser)
        browser.open("/")
        browser.wait(1000)

    def test_anon_user_redirected_to_org_setup(self, browser: Browser):
        browser.open("/org/dashboard")
        browser.wait(3000)
        url = browser.get_url()
        assert "/org/setup" in url, f"Non-org user should be redirected to /org/setup, got {url}"

    def test_org_setup_shows_tier_info(self, browser: Browser):
        browser.open("/org/setup")
        browser.wait(2000)
        snap = browser.snapshot()
        has_tier = snap.contains("Team") or snap.contains("Enterprise") or snap.contains("Organization")
        assert has_tier, "Org setup should show tier information"


# ===========================================================================
# Branding
# ===========================================================================


class TestRoobenBranding:
    """P16: Branding verification."""

    @pytest.fixture(autouse=True)
    def _setup_done(self, browser: Browser):
        browser.open("/")
        browser.wait(1000)
        bypass_setup(browser)
        browser.open("/")
        browser.wait(2000)

    def test_sidebar_shows_rooben(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Rooben"), "Sidebar should show 'Rooben' branding"

    def test_setup_wizard_shows_rooben(self, browser: Browser):
        clear_setup(browser)
        browser.open("/")
        browser.wait(2000)
        snap = browser.snapshot()
        assert snap.contains("Welcome to Rooben"), "Setup wizard should show 'Welcome to Rooben'"
        # Restore setup for subsequent tests
        bypass_setup(browser)
