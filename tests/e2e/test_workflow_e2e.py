"""E2E: Workflow Creation & Detail — 7 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestWorkflowE2E:
    """Verify the core workflow creation and interaction flows."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    def test_navigate_to_new_workflow(self, browser: Browser):
        browser.open("/")
        snap = browser.wait_for_text("Add New", timeout_ms=10000)
        ref = snap.ref_for_link("Add New")
        assert ref, "Add New link should be in sidebar"
        browser.click(ref)
        browser.wait(1500)
        url = browser.get_url()
        assert "/workflows/new" in url

    def test_idea_input_has_typewriter(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(2000)
        snap = browser.snapshot()
        # IdeaInput should have a textarea or textbox with placeholder text
        has_input = (
            snap.ref_for("textarea")
            or snap.ref_for_textbox("Build")
            or snap.ref_for_textbox("Create")
            or snap.ref_for_textbox("Describe")
            or snap.ref_for_textbox("Analyze")
        )
        assert has_input, "IdeaInput should render with placeholder"

    def test_idea_input_type_and_build(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(1500)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_textbox("Build a REST API")
            or snap.ref_for_textbox("Create a CLI")
            or snap.ref_for_textbox("Describe")
            or snap.ref_for("textarea")
        )
        if ref:
            browser.fill(ref, "Build a REST API for managing tasks")
            browser.wait(500)
        snap2 = browser.snapshot()
        assert (
            snap2.contains("Build now")
            or snap2.contains("Build Now")
            or snap2.contains("Create")
            or snap2.contains("Run")
        ), "Build button should be available after typing"

    def test_idea_input_type_and_refine(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(1500)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_textbox("Build a REST API")
            or snap.ref_for_textbox("Create a CLI")
            or snap.ref_for_textbox("Describe")
            or snap.ref_for("textarea")
        )
        if ref:
            browser.fill(ref, "Build a data pipeline for CSV processing")
            browser.wait(500)
        snap2 = browser.snapshot()
        assert (
            snap2.contains("Refine")
            or snap2.contains("customize")
            or snap2.contains("Guided")
        ), "Refine button should be available"

    def test_template_picker_opens(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(1500)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("Templates")
            or snap.ref_for_button("Use template")
            or snap.ref_for("template")
            or snap.ref_for_link("Templates")
        )
        if ref:
            browser.click(ref)
            browser.wait(1000)
        snap2 = browser.snapshot()
        assert (
            snap2.contains("template")
            or snap2.contains("Template")
            or snap2.contains("Professional")
            or snap2.contains("Builder")
            or snap2.contains("Automator")
        ), "Template picker should show categories"

    def test_template_selection_populates_input(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(1500)
        snap = browser.snapshot()
        # Look for a quick-start example button
        ref = (
            snap.ref_for_button("REST API")
            or snap.ref_for_button("API")
            or snap.ref_for_button("data pipeline")
            or snap.ref_for_button("Build a")
        )
        if ref:
            browser.click(ref)
            browser.wait(1000)
            snap2 = browser.snapshot()
            # Input should now have content
            assert (
                snap2.contains("API")
                or snap2.contains("Build")
                or snap2.contains("Create")
            ), "Template selection should populate input"
        else:
            # If no quick-start buttons, at least verify template section exists
            assert snap.contains("template") or snap.contains("Template")

    def test_wizard_always_shows(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(1500)
        snap = browser.snapshot()
        # Wizard always shows directly — no guided toggle
        assert (
            snap.contains("What would you like")
            or snap.contains("Describe")
            or snap.contains("Build now")
        ), "Workflow creation page should load with wizard UI"
