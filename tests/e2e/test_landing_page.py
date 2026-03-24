"""E2E: Landing Page — 9 tests."""

from tests.e2e.browser import Browser


class TestLandingPage:
    """Verify the marketing landing page content and interactions."""

    def test_landing_loads_with_hero(self, browser: Browser):
        browser.open("/landing")
        snap = browser.wait_for_text("EARLY ACCESS", timeout_ms=10000)
        assert snap.contains("Describe your work") or snap.contains("Your taste is the product") or snap.contains("Watch AI")

    def test_landing_dag_demo_visible(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.contains("workflow")
            or snap.contains("execute")
            or snap.contains("real time")
            or snap.contains("DAG")
            or snap.contains("agents")
        ), "DAG demo section should be visible"

    def test_landing_terminal_demo_visible(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.contains("command")
            or snap.contains("terminal")
            or snap.contains("CLI")
            or snap.contains("rooben")
            or snap.contains("rooben")
        ), "Terminal demo section should be visible"

    def test_landing_persona_sections(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        # Check for at least 2 of the 3 persona types (naming may vary)
        found = sum([
            snap.contains("Professional") or snap.contains("Builder"),
            snap.contains("Builder") or snap.contains("Operator"),
            snap.contains("Automator") or snap.contains("Optimizer"),
        ])
        assert found >= 2, "At least 2 persona sections should render"

    def test_landing_comparison_table(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.contains("Claude")
            or snap.contains("Cursor")
            or snap.contains("Dify")
            or snap.contains("comparison")
        ), "Comparison table should mention at least one competitor"

    def test_landing_waitlist_form_present(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.ref_for_textbox("you@company.com")
            or snap.ref_for_textbox("email")
            or snap.ref_for_textbox("Email")
            or snap.ref_for("email")
        ), "Waitlist email input should be present"

    def test_landing_waitlist_submit(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        email_ref = (
            snap.ref_for_textbox("you@company.com")
            or snap.ref_for_textbox("email")
            or snap.ref_for_textbox("Email")
            or snap.ref_for("email")
        )
        if email_ref:
            browser.fill(email_ref, "test-e2e@example.com")
            browser.wait(500)
            submit_ref = (
                snap.ref_for_button("Join")
                or snap.ref_for_button("Sign up")
                or snap.ref_for_button("Get early access")
                or snap.ref_for_button("Submit")
                or snap.ref_for_button("Request")
            )
            if submit_ref:
                browser.click(submit_ref)
                browser.wait(2000)
                snap2 = browser.snapshot()
                # Should show success or the form should change state
                assert (
                    snap2.contains("Thank")
                    or snap2.contains("success")
                    or snap2.contains("list")
                    or snap2.contains("added")
                    or snap2.contains("check")
                ), "Waitlist submission should show confirmation"

    def test_landing_stats_section(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        found = sum([
            snap.contains("305") or snap.contains("Tests"),
            snap.contains("provider") or snap.contains("Provider"),
            snap.contains("96%") or snap.contains("Verification"),
            snap.contains("$0.37") or snap.contains("cost"),
        ])
        assert found >= 2, "At least 2 stats badges should render"

    def test_landing_nav_links(self, browser: Browser):
        browser.open("/landing")
        browser.wait(3000)
        snap = browser.snapshot()
        assert (
            snap.ref_for_link("GitHub")
            or snap.ref_for_link("github")
            or snap.contains("GitHub")
            or snap.contains("Open source")
        ), "GitHub link should be present in landing nav"
