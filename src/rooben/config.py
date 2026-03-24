"""Centralized application settings.

Consolidates scattered ``os.environ.get()`` calls into a single typed object.
Uses only stdlib + pydantic (already a dependency) — no extra packages needed.
"""

from __future__ import annotations

import os

from pydantic import BaseModel


class Settings(BaseModel):
    """Typed application configuration sourced from environment variables."""

    # LLM provider keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Database
    database_url: str = ""

    # Core paths
    rooben_learning_store_path: str = ""
    rooben_extensions_dir: str = ""
    rooben_static_dir: str = ""

    # API
    rooben_api_key: str = ""
    rooben_api_keys: str = ""
    rooben_api_url: str = "http://127.0.0.1:8420"

    # Security
    rooben_credential_key: str = ""
    rooben_cors_origins: str = ""

    # Cloud
    aws_default_region: str = "us-east-1"
    mcp_gateway_url: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from current environment variables."""
        fields: dict[str, str] = {}
        for name in cls.model_fields:
            env_val = os.environ.get(name.upper(), "")
            if env_val:
                fields[name] = env_val
        return cls(**fields)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached application settings (created on first call)."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    """Clear cached settings (useful for testing)."""
    global _settings
    _settings = None
