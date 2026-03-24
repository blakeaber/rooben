"""E2E: Integrations Hub list page (P8)."""

from tests.e2e.browser import Browser


class TestIntegrationsListPage:

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        assert snap.contains("ROOBEN / INTEGRATIONS")
        assert snap.contains("Manage data sources, templates, and agents")

    def test_stat_chips_visible(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        for label in ["Installed", "Available", "User Created", "Unavailable"]:
            assert snap.contains(label), f"Missing stat chip: {label}"

    def test_integration_cards_render(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        for name in ["coding", "minimal", "writing"]:
            assert snap.contains(name), f"Missing integration card: {name}"

    def test_action_cards_present(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        assert snap.contains("Browse Library"), "Browse Library action card missing"
        assert snap.contains("Create Custom"), "Create Custom action card missing"

    def test_source_filter_builtin(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        ref = snap.ref_for_button("Builtin")
        assert ref, "Builtin filter button not found"
        browser.click(ref)
        browser.wait(1000)
        snap = browser.snapshot()
        assert snap.contains("builtin"), "Builtin cards not shown after filter"

    def test_source_filter_community(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        ref = snap.ref_for_button("Community")
        assert ref
        browser.click(ref)
        browser.wait(1000)
        snap = browser.snapshot()
        # Either shows community cards or empty state — both are valid
        assert snap.contains("community") or snap.contains("No community"), \
            "Community filter did not work"

    def test_cards_have_domain_tags(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        # coding card should show software/infrastructure/devops tags
        assert snap.contains("software"), "Missing domain tag: software"

    def test_cards_have_cost_tier(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        assert snap.contains("Medium") or snap.contains("Low") or snap.contains("Free"), \
            "No cost tier visible on cards"

    def test_cards_have_server_count(self, browser: Browser):
        browser.open("/integrations")
        snap = browser.wait_for_text("Integrations Hub")
        assert snap.contains("server"), "No server count visible on cards"
