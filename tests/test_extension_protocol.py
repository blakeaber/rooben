"""Contract test — verifies extension protocol exports exist with expected shapes.

This test runs in OSS CI and catches any accidental breakage of the
interface that rooben-pro depends on.
"""


def test_extension_protocol_exports():
    from rooben.dashboard.extension_protocol import (
        ANONYMOUS_USER,
        CurrentUser,
        DashboardDeps,
        DashboardEventAdapter,
        get_auth_dependency,
        get_deps,
        get_extension,
        has_extension,
        run_pro_shutdown,
        run_pro_startup,
        set_auth_dependency,
        set_deps,
    )

    # Auth hooks are callable
    assert callable(set_auth_dependency)
    assert callable(get_auth_dependency)

    # Event adapter has listener API
    assert hasattr(DashboardEventAdapter, "add_event_listener")
    assert callable(DashboardEventAdapter.add_event_listener)
    assert hasattr(DashboardEventAdapter, "_event_listeners")

    # CurrentUser has property accessors (extras is a dataclass field on instances)
    user = CurrentUser(id="test")
    assert hasattr(user, "extras")
    assert hasattr(user, "org_id")
    assert hasattr(user, "role")
    assert hasattr(user, "email")

    # DashboardDeps has extras on instances
    deps = DashboardDeps()
    assert hasattr(deps, "extras")

    # ANONYMOUS_USER is a CurrentUser
    assert isinstance(ANONYMOUS_USER, CurrentUser)
    assert ANONYMOUS_USER.id == "anonymous"

    # Deps accessors
    assert callable(get_deps)
    assert callable(set_deps)

    # Registry helpers
    assert callable(get_extension)
    assert callable(has_extension)
    assert callable(run_pro_startup)
    assert callable(run_pro_shutdown)


def test_current_user_extras():
    from rooben.dashboard.extension_protocol import CurrentUser

    # OSS default — no extras
    user = CurrentUser(id="test")
    assert user.email is None
    assert user.org_id is None
    assert user.role is None

    # Pro-style — with extras
    user = CurrentUser(
        id="user-123",
        extras={"email": "a@b.com", "org_id": "org-1", "role": "admin"},
    )
    assert user.email == "a@b.com"
    assert user.org_id == "org-1"
    assert user.role == "admin"


def test_event_adapter_listeners():
    """Verify listener registration works (idempotent — cleans up after)."""
    from rooben.dashboard.extension_protocol import DashboardEventAdapter

    original_count = len(DashboardEventAdapter._event_listeners)

    calls = []
    async def _test_listener(event_type, payload):
        calls.append((event_type, payload))

    DashboardEventAdapter.add_event_listener(_test_listener)
    assert len(DashboardEventAdapter._event_listeners) == original_count + 1

    # Clean up
    DashboardEventAdapter._event_listeners.pop()
    assert len(DashboardEventAdapter._event_listeners) == original_count


def test_dashboard_deps_extras():
    from rooben.dashboard.extension_protocol import DashboardDeps

    deps = DashboardDeps()
    assert deps.extras == {}
    deps.extras["webhook_service"] = "mock"
    assert deps.extras["webhook_service"] == "mock"
