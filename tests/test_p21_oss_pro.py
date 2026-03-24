"""Tests for P21 — OSS/Pro Package Architecture."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestPublicAPI:
    """R-21.3: Public API surface."""

    def test_public_api_importable(self):
        from rooben import public_api
        assert hasattr(public_api, "API_VERSION")
        assert public_api.API_VERSION == "0.1.0"

    def test_public_api_exports_orchestrator(self):
        from rooben.public_api import Orchestrator
        assert Orchestrator is not None

    def test_public_api_exports_planner(self):
        from rooben.public_api import Planner
        assert Planner is not None

    def test_public_api_exports_verifier(self):
        from rooben.public_api import Verifier
        assert Verifier is not None

    def test_public_api_exports_task(self):
        from rooben.public_api import Task, TaskResult
        assert Task is not None
        assert TaskResult is not None

    def test_public_api_exports_specification(self):
        from rooben.public_api import Specification
        assert Specification is not None

    def test_py_typed_marker_exists(self):
        marker = ROOT / "src" / "rooben" / "py.typed"
        assert marker.exists(), "PEP 561 py.typed marker is missing"


class TestRoobenProScaffold:
    """R-21.4: rooben-pro package — installed from separate repository."""

    def test_rooben_pro_importable(self):
        try:
            import rooben_pro
            assert rooben_pro.__version__ == "0.1.0"
        except ImportError:
            pytest.skip("rooben-pro not installed")

    def test_rooben_pro_has_register(self):
        try:
            from rooben_pro import register
            ext = register()
            assert hasattr(ext, "get_routers")
        except ImportError:
            pytest.skip("rooben-pro not installed")

    def test_rooben_pro_postgres_learning_importable(self):
        try:
            from rooben_pro.postgres_learning import PostgresLearningStore
            assert PostgresLearningStore is not None
        except ImportError:
            pytest.skip("rooben-pro not installed")

    def test_rooben_pro_linear_backend_importable(self):
        try:
            from rooben_pro.linear_backend import LinearBackend
            assert LinearBackend is not None
        except ImportError:
            pytest.skip("rooben-pro not installed")


class TestOSSRepoStructure:
    """R-21.6: Repository structure for OSS."""

    def test_license_exists_and_is_apache2(self):
        license_file = ROOT / "LICENSE"
        assert license_file.exists()
        content = license_file.read_text()
        assert "Apache License" in content

    def test_contributing_exists(self):
        contributing = ROOT / "CONTRIBUTING.md"
        assert contributing.exists()
        content = contributing.read_text()
        assert "Contributing" in content


class TestMigrationAndChangelog:
    """R-21.8: Migration guide and changelog."""

    def test_changelog_md_exists(self):
        changelog = ROOT / "CHANGELOG.md"
        assert changelog.exists()
        content = changelog.read_text()
        assert "0.1.0" in content
