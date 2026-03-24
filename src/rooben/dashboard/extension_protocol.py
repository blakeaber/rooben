"""Extension protocol — stable interface for rooben-pro.

⚠️  EXTENSION CONTRACT: Functions in this module are imported by rooben-pro.
    Changing signatures, renaming, or removing them will break Pro.
    Run `pytest tests/test_extension_protocol.py` before merging any changes.
"""

# Auth
from rooben.dashboard.auth import get_auth_dependency, set_auth_dependency  # noqa: F401

# Deps
from rooben.dashboard.deps import DashboardDeps, get_deps, set_deps  # noqa: F401

# User model
from rooben.dashboard.models.user import ANONYMOUS_USER, CurrentUser  # noqa: F401

# Event adapter
from rooben.dashboard.event_adapter import DashboardEventAdapter  # noqa: F401

# Extension registry
from rooben.extensions.registry import (  # noqa: F401
    get_extension,
    has_extension,
    run_pro_shutdown,
    run_pro_startup,
)
