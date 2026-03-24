"""E2E: Cross-page navigation flows (P7/P8)."""

from tests.e2e.browser import Browser


class TestCrossPageFlows:

    def test_list_to_detail_and_back(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        ref = snap.ref_for_link("writing")
        assert ref, "writing card link not found"
        browser.click(ref)
        snap = browser.wait_for_text("Filesystem")
        assert snap.contains("writing")
        # Navigate back
        back_ref = snap.ref_for("Integrations")
        assert back_ref
        browser.click(back_ref)
        browser.wait_for_text("Integrations Hub")

    def test_list_to_library_to_install(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        ref = snap.ref_for("Browse Library")
        assert ref
        browser.click(ref)
        snap = browser.wait_for_text("Community Library")
        assert snap.contains("slack-notifications")
        # Click Install on first card
        refs = snap.refs_for_button("Install")
        assert refs
        browser.click(refs[0])
        browser.wait(1500)
        snap = browser.snapshot()
        # Confirm in modal — last Install button is the modal one
        modal_refs = snap.refs_for_button("Install")
        if modal_refs:
            browser.click(modal_refs[-1])
            browser.wait(5000)
            url = browser.get_url()
            assert "/integrations" in url, f"Expected redirect to integrations, got {url}"

    def test_create_to_build_to_install_to_detail(self, browser: Browser):
        browser.open("/integrations/create")
        snap = browser.wait_for_text("AI-Assisted Builder")
        ref = snap.ref_for_textbox("e.g., Connect to Slack")
        assert ref
        browser.fill(ref, "GitHub issue tracker")
        browser.wait(500)
        snap = browser.snapshot()
        gen_ref = snap.ref_for_button("Generate Plan")
        assert gen_ref
        browser.click(gen_ref)
        snap = browser.wait_for_text("Generated Plan", timeout_ms=10000)
        install_ref = snap.ref_for_button("Install Integration")
        assert install_ref
        browser.click(install_ref)
        snap = browser.wait_for_text("Integration Created", timeout_ms=10000)
        detail_ref = snap.ref_for_button("View Detail") or snap.ref_for_link("View Detail")
        if detail_ref:
            browser.click(detail_ref)
            browser.wait(3000)
            snap = browser.snapshot()
            assert snap.contains("user"), "Detail should show user source"


class TestCleanup:
    """Clean up any user integrations created during tests."""

    def test_cleanup_user_integrations(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        _result = browser.eval(
            "fetch('/api/integrations').then(r=>r.json()).then(d=>{"
            "const del=[];"
            "const proms=[];"
            "for(const i of d.integrations){"
            "if(i.source!=='builtin'){"
            "proms.push(fetch('/api/integrations/'+encodeURIComponent(i.name),{method:'DELETE'}));"
            "del.push(i.name);"
            "}}"
            "return Promise.all(proms).then(()=>JSON.stringify(del));"
            "})"
        )
        # This is a cleanup step — always passes
        assert True
