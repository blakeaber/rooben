"""E2E: Backend API validation for integrations (P8) via browser fetch."""


from tests.e2e.browser import Browser


class TestIntegrationsAPI:

    def test_list_all(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json("/api/integrations")
        items = data["integrations"]
        assert len(items) >= 10, f"Expected ≥10 integrations, got {len(items)}"
        for item in items:
            for field in ["name", "source", "available", "server_count"]:
                assert field in item, f"Missing field '{field}' in integration"

    def test_get_detail(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json("/api/integrations/coding")
        assert data["name"] == "coding"
        assert data["source"] == "builtin"
        assert data["server_count"] >= 1

    def test_404_for_nonexistent(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        status = browser.fetch_status("/api/integrations/nonexistent-xyz")
        assert status == 404

    def test_create_user_integration(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json(
            "/api/integrations",
            method="POST",
            body={
                "name": "test-e2e-api",
                "description": "E2E test integration",
                "domain_tags": ["testing"],
                "cost_tier": 1,
                "servers": [],
            },
        )
        assert data.get("created") is True

    def test_duplicate_returns_409(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        status = browser.fetch_status(
            "/api/integrations",
            method="POST",
            body={
                "name": "coding",
                "description": "dup",
                "domain_tags": [],
                "cost_tier": 1,
                "servers": [],
            },
        )
        assert status == 409

    def test_update_user_integration(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json(
            "/api/integrations/test-e2e-api",
            method="PUT",
            body={"description": "Updated"},
        )
        assert data.get("updated") is True

    def test_update_builtin_returns_403(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        status = browser.fetch_status(
            "/api/integrations/coding",
            method="PUT",
            body={"description": "hack"},
        )
        assert status == 403

    def test_connection(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json("/api/integrations/coding/test", method="POST")
        assert "passed" in data
        assert "checks" in data

    def test_library(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json("/api/integrations/library")
        items = data.get("library", data.get("items", []))
        assert len(items) == 5, f"Expected 5 library items, got {len(items)}"

    def test_build(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json(
            "/api/integrations/build",
            method="POST",
            body={"description": "Slack notifications"},
        )
        assert "name" in str(data)
        assert "servers" in str(data)

    def test_delete_user_integration(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        data = browser.fetch_json("/api/integrations/test-e2e-api", method="DELETE")
        assert data.get("deleted") is True

    def test_delete_builtin_returns_403(self, browser: Browser):
        browser.open("/integrations")
        browser.wait_for_text("Integrations Hub")
        status = browser.fetch_status("/api/integrations/coding", method="DELETE")
        assert status == 403
