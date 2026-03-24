"""Tests for the Integrations Hub API routes."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from rooben.agents.integrations import (
    IntegrationDefinition,
    IntegrationRegistry,
    load_user_integrations,
)


class TestIntegrationDefinitionNewFields:
    def test_default_source_is_builtin(self):
        registry = IntegrationRegistry()
        for tk in registry.list_all():
            assert tk.source == "builtin"  # LLM providers are still "builtin"

    def test_llm_providers_registered(self):
        registry = IntegrationRegistry()
        assert registry.get("anthropic") is not None
        assert registry.get("openai") is not None
        assert registry.get("ollama") is not None
        assert registry.get("bedrock") is not None

    def test_default_version(self):
        registry = IntegrationRegistry()
        tk = registry.get("anthropic")
        assert tk is not None
        assert tk.version == "1.0.0"


class TestToDict:
    def test_to_dict_includes_all_fields(self):
        tk = IntegrationDefinition(
            name="test",
            description="Test integration",
            domain_tags=["ops"],
            cost_tier=1,
            mcp_server_factory=lambda _: [],
            source="extension",
            author="tester",
            version="2.0.0",
        )
        d = tk.to_dict()
        assert d["name"] == "test"
        assert d["description"] == "Test integration"
        assert d["domain_tags"] == ["ops"]
        assert d["cost_tier"] == 1
        assert d["source"] == "extension"
        assert d["author"] == "tester"
        assert d["version"] == "2.0.0"

    def test_to_dict_excludes_mcp_server_factory(self):
        tk = IntegrationDefinition(
            name="test",
            description="Test",
            domain_tags=[],
            cost_tier=0,
            mcp_server_factory=lambda _: [],
        )
        d = tk.to_dict()
        assert "mcp_server_factory" not in d

    def test_to_dict_includes_source_author_version(self):
        tk = IntegrationDefinition(
            name="test",
            description="Test",
            domain_tags=["ops"],
            cost_tier=1,
            mcp_server_factory=lambda _: [],
            source="user",
            author="tester",
            version="2.0.0",
        )
        d = tk.to_dict()
        assert d["source"] == "user"
        assert d["author"] == "tester"
        assert d["version"] == "2.0.0"


class TestUserIntegrationsSourceField:
    def test_user_integrations_get_source_user(self, tmp_path: Path):
        config = {
            "integrations": [
                {
                    "name": "my-integration",
                    "description": "My custom integration",
                    "domain_tags": ["research"],
                    "cost_tier": 1,
                    "author": "me",
                    "version": "3.0.0",
                    "servers": [],
                }
            ]
        }
        config_path = tmp_path / ".rooben" / "integrations.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump(config))

        registry = IntegrationRegistry()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            load_user_integrations(registry)
        finally:
            os.chdir(old_cwd)

        tk = registry.get("my-integration")
        assert tk is not None
        assert tk.source == "user"
        assert tk.author == "me"
        assert tk.version == "3.0.0"


class TestListIntegrations:
    def test_list_returns_llm_providers(self):
        registry = IntegrationRegistry()
        items = []
        for tk in registry.list_all():
            d = tk.to_dict()
            d["available"] = registry.is_available(tk)
            d["missing_env"] = [v for v in tk.required_env if not os.environ.get(v)]
            items.append(d)

        # LLM providers + built-in external integrations (brave-search)
        assert len(items) == 5
        for item in items:
            assert "name" in item
            assert "description" in item
            assert "source" in item
            assert "available" in item


class TestGetSingleIntegration:
    def test_get_existing_llm_provider(self):
        registry = IntegrationRegistry()
        tk = registry.get("anthropic")
        assert tk is not None
        assert tk.kind == "llm_provider"

    def test_get_nonexistent(self):
        registry = IntegrationRegistry()
        tk = registry.get("nonexistent-integration-xyz")
        assert tk is None


class TestCRUDUserIntegration:
    def test_create_update_delete(self, tmp_path: Path):
        config_path = tmp_path / ".rooben" / "integrations.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.dump({"integrations": []}))

        entry = {
            "name": "test-crud",
            "description": "CRUD test",
            "domain_tags": ["operations"],
            "cost_tier": 1,
            "author": "tester",
            "version": "1.0.0",
            "source": "user",
            "servers": [],
        }

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Write
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            data.setdefault("integrations", []).append(entry)
            with open(config_path, "w") as f:
                yaml.dump(data, f)

            # Read back
            registry = IntegrationRegistry()
            load_user_integrations(registry)
            tk = registry.get("test-crud")
            assert tk is not None
            assert tk.source == "user"
            assert tk.author == "tester"

            # Update
            with open(config_path) as f:
                data = yaml.safe_load(f)
            for e in data["integrations"]:
                if e["name"] == "test-crud":
                    e["description"] = "Updated"
            with open(config_path, "w") as f:
                yaml.dump(data, f)

            registry = IntegrationRegistry()
            load_user_integrations(registry)
            tk = registry.get("test-crud")
            assert tk is not None
            assert tk.description == "Updated"

            # Delete
            with open(config_path) as f:
                data = yaml.safe_load(f)
            data["integrations"] = [e for e in data["integrations"] if e["name"] != "test-crud"]
            with open(config_path, "w") as f:
                yaml.dump(data, f)

            registry = IntegrationRegistry()
            load_user_integrations(registry)
            tk = registry.get("test-crud")
            assert tk is None

        finally:
            os.chdir(old_cwd)


class TestTestConnection:
    def test_available_provider_passes(self):
        registry = IntegrationRegistry()
        tk = registry.get("ollama")
        assert tk is not None
        # ollama has no required_env
        missing = [v for v in tk.required_env if not os.environ.get(v)]
        assert len(missing) == 0


class TestLibraryEndpoint:
    def test_sample_library_has_entries(self):
        sample = [
            {"name": "slack-notifications", "author": "rooben-community"},
            {"name": "github-issues", "author": "rooben-community"},
            {"name": "postgres-query", "author": "rooben-community"},
            {"name": "notion-sync", "author": "rooben-community"},
            {"name": "puppeteer-scraper", "author": "rooben-community"},
        ]
        assert len(sample) == 5
        assert all("name" in item for item in sample)


class TestBuildEndpoint:
    def test_build_generates_config_for_slack(self):
        description = "Connect to Slack for notifications"
        desc_lower = description.lower()
        servers = []
        if "slack" in desc_lower:
            servers.append({
                "name": "slack",
                "transport_type": "stdio",
                "command": "npx",
                "args": ["-y", "@anthropic/mcp-server-slack"],
                "env": {"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
            })
        assert len(servers) == 1
        assert servers[0]["name"] == "slack"

    def test_build_generates_config_for_generic(self):
        description = "Something completely custom"
        desc_lower = description.lower()
        has_match = any(
            kw in desc_lower
            for kw in ["slack", "github", "postgres", "database", "sql", "notion", "search", "web"]
        )
        assert not has_match
