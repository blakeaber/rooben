"""E2E: Community Library page (P8)."""

from tests.e2e.browser import Browser


class TestCommunityLibrary:

    def test_page_loads(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        assert snap.contains("ROOBEN / INTEGRATIONS / LIBRARY")
        assert snap.contains("Discover and install")

    def test_all_library_cards_visible(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        for name in ["slack-notifications", "github-issues", "postgres-query",
                      "notion-sync", "puppeteer-scraper"]:
            assert snap.contains(name), f"Missing library card: {name}"

    def test_install_buttons_present(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        assert snap.ref_for_button("Install"), "No Install button found"

    def test_search_filter(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        ref = snap.ref_for_textbox("Search integrations")
        assert ref, "Search input not found"
        browser.fill(ref, "slack")
        browser.wait(1500)
        snap = browser.snapshot()
        assert snap.contains("slack-notifications"), "slack-notifications not shown after search"
        assert snap.not_contains("github-issues"), "github-issues should be filtered out"

    def test_search_empty_state(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        ref = snap.ref_for_textbox("Search integrations")
        assert ref
        browser.fill(ref, "nonexistent-xyz-nope")
        browser.wait(1500)
        snap = browser.snapshot()
        assert snap.contains("No matching integrations found"), "Empty state message missing"

    def test_install_modal_opens(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        # Find first Install button
        ref = snap.ref_for_button("Install")
        assert ref
        browser.click(ref)
        browser.wait(1500)
        snap = browser.snapshot()
        assert snap.contains("Install") and snap.contains("Cancel"), \
            "Install modal did not open"

    def test_cancel_modal(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        ref = snap.ref_for_button("Install")
        assert ref
        browser.click(ref)
        browser.wait(1500)
        snap = browser.snapshot()
        cancel_ref = snap.ref_for_button("Cancel")
        assert cancel_ref, "Cancel button not found in modal"
        browser.click(cancel_ref)
        browser.wait(1000)
        snap = browser.snapshot()
        assert snap.contains("Community Library"), "Library page not visible after cancel"

    def test_install_from_library(self, browser: Browser):
        browser.open("/integrations/library")
        snap = browser.wait_for_text("Community Library")
        # Click Install on first card
        refs = snap.refs_for_button("Install")
        assert refs, "No Install buttons found"
        browser.click(refs[0])
        browser.wait(1500)
        snap = browser.snapshot()

        # Modal is open — there are now two Install buttons: cards + modal
        # The modal Install is the last one; Cancel is also present
        assert snap.contains("Cancel"), "Modal did not open (no Cancel button)"
        modal_refs = snap.refs_for_button("Install")
        # The last Install button is inside the modal
        assert len(modal_refs) >= 1
        browser.click(modal_refs[-1])
        browser.wait_for_text("Integrations Hub", timeout_ms=15000)
        url = browser.get_url()
        assert "/integrations" in url, "Did not redirect to integrations list"
