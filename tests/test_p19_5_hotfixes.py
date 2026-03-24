"""Tests for Phase P19.5 QC Hotfixes.

Covers:
- R-19.5.1: ensure_schema module existence
- R-19.5.2: A2A column verification (output/error in tasks table and route code)
- R-19.5.3: fpdf2 in dashboard extras, ExportBar workflowStatus prop
- R-19.5.4: Community install uses pub["artifact_id"]
- R-19.5.5: Error handling hardening — flag dedup narrowed, audit alias route
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── R-19.5.1: ensure_schema module ──────────────────────────────────────


def test_ensure_schema_module_importable():
    """ensure_schema.py can be imported and exposes ensure_schema()."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ensure_schema", ROOT / "scripts" / "ensure_schema.py"
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "ensure_schema")
    assert callable(mod.ensure_schema)
    assert hasattr(mod, "read_init_sql")


def test_ensure_schema_reads_init_sql():
    """read_init_sql returns the SQL content."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ensure_schema", ROOT / "scripts" / "ensure_schema.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sql = mod.read_init_sql()
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert len(sql) > 100


# ── R-19.5.2: A2A column verification ──────────────────────────────────


def test_init_sql_has_output_and_error_columns():
    """The tasks table in init.sql has output TEXT and error TEXT columns."""
    sql = (ROOT / "scripts" / "init.sql").read_text()
    # Find the tasks table definition
    match = re.search(
        r"CREATE TABLE IF NOT EXISTS tasks\s*\((.*?)\);",
        sql,
        re.DOTALL,
    )
    assert match, "tasks table not found in init.sql"
    table_body = match.group(1)
    assert "output" in table_body, "output column missing from tasks table"
    assert "error" in table_body, "error column missing from tasks table"


def test_a2a_route_uses_output_and_error():
    """A2A get-task route queries output and error columns."""
    try:
        import rooben_pro.dashboard.routes.a2a as a2a_mod
    except ImportError:
        pytest.skip("rooben-pro not installed")
    import inspect
    src = inspect.getsource(a2a_mod)
    # Completed artifacts query uses 'output'
    assert "SELECT title, output FROM tasks" in src
    # Failed tasks query uses 'error'
    assert "SELECT title, error FROM tasks" in src


# ── R-19.5.3: Export & Sharing ──────────────────────────────────────────


def test_fpdf2_in_pro_export_extras():
    """fpdf2 is available as a rooben-pro dependency."""
    try:
        import importlib.metadata
        requires = importlib.metadata.requires("rooben-pro") or []
        export_deps = [r for r in requires if "export" in r]
        assert any("fpdf2" in d for d in export_deps), f"fpdf2 not in rooben-pro deps: {export_deps}"
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("rooben-pro not installed")


def test_exportbar_accepts_workflow_status_prop():
    """ExportBar.tsx interface includes workflowStatus prop."""
    tsx = (
        ROOT / "dashboard" / "src" / "components" / "workflows" / "ExportBar.tsx"
    ).read_text()
    assert "workflowStatus" in tsx
    # Verify the guard logic exists
    assert 'workflowStatus !== "completed"' in tsx or "workflowStatus !== 'completed'" in tsx


# ── R-19.5.4: Community install uses artifact_id ────────────────────────


def test_community_install_uses_artifact_id():
    """Community install route looks up source via pub['artifact_id']."""
    src = (
        ROOT / "src" / "rooben" / "dashboard" / "routes" / "community.py"
    ).read_text()
    assert 'pub["artifact_id"]' in src


# ── R-19.5.5: Error handling hardening ──────────────────────────────────


def test_flag_create_narrows_exception():
    """create_flag catches only unique/duplicate violations, re-raises others."""
    src = (
        ROOT / "src" / "rooben" / "dashboard" / "queries" / "community.py"
    ).read_text()
    # Should check for "unique" or "duplicate" in the exception message
    assert '"unique" in str(exc).lower()' in src
    assert '"duplicate" in str(exc).lower()' in src
    assert "raise" in src  # re-raises unexpected errors


def test_audit_router_has_both_prefixes():
    """audit.py defines both /api/org/audit-logs and /api/org/audit prefixes."""
    try:
        import rooben_pro.dashboard.routes.audit as audit_mod
    except ImportError:
        pytest.skip("rooben-pro not installed")
    import inspect
    src = inspect.getsource(audit_mod)
    assert 'prefix="/api/org/audit-logs"' in src
    assert 'prefix="/api/org/audit"' in src


def test_pro_extension_routers_load_gracefully():
    """Pro extension get_routers does not crash the OSS app."""
    from rooben.extensions.registry import get_pro_routers
    # Should return empty list or valid routers without crashing
    routers = get_pro_routers()
    assert isinstance(routers, list)


def test_schema_applied_on_startup():
    """App lifespan applies init.sql on startup when pool is available."""
    src = (ROOT / "src" / "rooben" / "dashboard" / "app.py").read_text()
    assert "init.sql" in src
    assert "init_sql" in src


# ── Init SQL completeness ───────────────────────────────────────────────


def test_init_sql_has_all_expected_tables():
    """init.sql contains CREATE TABLE statements for all core tables."""
    sql = (ROOT / "scripts" / "init.sql").read_text()
    tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql)
    expected = [
        "workflows",
        "workstreams",
        "tasks",
        "task_dependencies",
        "workflow_usage",
        "agents",
        "workflow_agents",
        "shared_links",
        "schedules",
        "schedule_executions",
        "credentials",
        "agent_presets",
        "marketplace_templates",
        "marketplace_agents",
        "performance_snapshots",
        "a2a_task_map",
        "user_goals",
        "user_roles",
        "user_outcomes",
        "waitlist",
        "community_publications",
        "community_ratings",
        "community_flags",
        "invite_codes",
    ]
    for table in expected:
        assert table in tables, f"Missing CREATE TABLE for {table}"
