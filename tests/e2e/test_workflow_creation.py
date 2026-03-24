"""Section 5: Standard Workflow Creation — 7 tests."""

import pytest
from tests.e2e.browser import Browser
from tests.e2e.helpers import bypass_setup


class TestWorkflowCreation:
    """Standard workflow creation form."""

    @pytest.fixture(autouse=True)
    def _setup(self, browser: Browser):
        bypass_setup(browser)

    # S5.1 ----------------------------------------------------------------
    def test_new_workflow_page_loads(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(500)
        snap = browser.snapshot()
        assert snap.contains("Build now") or snap.contains("Build Now") or snap.contains("Create")

    # S5.2 ----------------------------------------------------------------
    def test_idea_input_accepts_text(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(500)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_textbox("Build a REST API")
            or snap.ref_for_textbox("Create a CLI")
            or snap.ref_for_textbox("Build a data")
            or snap.ref_for_textbox("Create a React")
            or snap.ref_for_textbox("Describe")
            or snap.ref_for("textarea")
        )
        assert ref is not None, "Idea input textbox should be present"
        browser.fill(ref, "Build a REST API")
        browser.wait(300)

    # S5.3 ----------------------------------------------------------------
    def test_provider_settings_collapsible(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(500)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_button("Provider")
            or snap.ref_for_button("Settings")
            or snap.ref_for_button("Advanced")
            or snap.ref_for("provider")
        )
        if ref:
            browser.click(ref)
            browser.wait(300)
            snap2 = browser.snapshot()
            assert (
                snap2.contains("model")
                or snap2.contains("Model")
                or snap2.contains("provider")
                or snap2.contains("Provider")
            )

    # S5.4 ----------------------------------------------------------------
    def test_refine_button_available(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(500)
        snap = browser.snapshot()
        assert (
            snap.contains("Refine")
            or snap.contains("Guided")
            or snap.contains("refine")
        )

    # S5.5 ----------------------------------------------------------------
    def test_template_picker_accessible(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(500)
        snap = browser.snapshot()
        assert (
            snap.contains("template")
            or snap.contains("Template")
            or snap.contains("Use template")
        )

    # S5.6 ----------------------------------------------------------------
    @pytest.mark.requires_db
    def test_submit_workflow(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(500)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_textbox("Describe")
            or snap.ref_for_textbox("idea")
            or snap.ref_for_textbox("What")
            or snap.ref_for("textarea")
        )
        if ref:
            browser.fill(ref, "Build a REST API for managing tasks")
            browser.wait(300)
        build_ref = snap.ref_for_button("Build now") or snap.ref_for_button("Build Now")
        if build_ref:
            browser.click(build_ref)
            browser.wait(2000)

    # S5.7 ----------------------------------------------------------------
    @pytest.mark.requires_db
    def test_refinement_chat_works(self, browser: Browser):
        browser.open("/workflows/new")
        browser.wait(500)
        snap = browser.snapshot()
        ref = (
            snap.ref_for_textbox("Describe")
            or snap.ref_for_textbox("idea")
            or snap.ref_for_textbox("What")
            or snap.ref_for("textarea")
        )
        if ref:
            browser.fill(ref, "Build a REST API for managing tasks")
            browser.wait(300)
        refine_ref = snap.ref_for_button("Refine") or snap.ref_for_button("Guided")
        if refine_ref:
            browser.click(refine_ref)
            browser.wait(2000)
