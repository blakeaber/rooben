"""Tests for extension protocol definitions.

Verifies that each protocol is runtime-checkable, that conforming stub
classes satisfy isinstance(), and that incomplete classes do not.
"""

from __future__ import annotations

from rooben.extensions.protocols import (
    AuthExtension,
    CLIExtension,
    ExportExtension,
    NotifierExtension,
    SchedulerExtension,
    StateBackendExtension,
    TemplateProviderExtension,
)


ALL_PROTOCOLS = [
    StateBackendExtension,
    ExportExtension,
    SchedulerExtension,
    NotifierExtension,
    CLIExtension,
    TemplateProviderExtension,
    AuthExtension,
]


def test_module_imports_cleanly():
    """Smoke test — the module loads without errors."""
    import rooben.extensions.protocols as mod

    assert hasattr(mod, "StateBackendExtension")
    assert hasattr(mod, "AuthExtension")


def test_all_protocols_are_runtime_checkable():
    for proto in ALL_PROTOCOLS:
        assert isinstance(proto, type), f"{proto.__name__} is not a type"
        # runtime_checkable protocols support isinstance checks
        assert hasattr(proto, "__protocol_attrs__") or hasattr(proto, "__abstractmethods__") or True
        # The real proof: calling isinstance on an empty object should not raise
        try:
            isinstance(object(), proto)
        except TypeError:
            raise AssertionError(f"{proto.__name__} is not @runtime_checkable")


# ---- Conforming stubs -------------------------------------------------------


class _StubStateBackend:
    async def save_state(self, workflow_id, state):
        pass

    async def load_state(self, workflow_id):
        return None

    async def delete_state(self, workflow_id):
        pass


class _StubExport:
    name = "stub"

    def export(self, workflow_id, artifacts, output_dir):
        return ""


class _StubScheduler:
    async def schedule(self, schedule_id, cron, callback):
        pass

    async def cancel(self, schedule_id):
        pass

    async def list_schedules(self):
        return []


class _StubNotifier:
    async def notify(self, event, payload):
        pass


class _StubCLI:
    name = "stub"

    def get_commands(self):
        return None


class _StubTemplateProvider:
    async def list_templates(self, query=""):
        return []

    async def fetch_template(self, template_id):
        return {}


class _StubAuth:
    async def authenticate(self, request):
        return None

    async def authorize(self, user, resource, action):
        return False


def test_state_backend_stub_satisfies_protocol():
    assert isinstance(_StubStateBackend(), StateBackendExtension)


def test_export_stub_satisfies_protocol():
    assert isinstance(_StubExport(), ExportExtension)


def test_scheduler_stub_satisfies_protocol():
    assert isinstance(_StubScheduler(), SchedulerExtension)


def test_notifier_stub_satisfies_protocol():
    assert isinstance(_StubNotifier(), NotifierExtension)


def test_cli_stub_satisfies_protocol():
    assert isinstance(_StubCLI(), CLIExtension)


def test_template_provider_stub_satisfies_protocol():
    assert isinstance(_StubTemplateProvider(), TemplateProviderExtension)


def test_auth_stub_satisfies_protocol():
    assert isinstance(_StubAuth(), AuthExtension)


# ---- Non-conforming classes --------------------------------------------------


class _MissingSaveState:
    """Missing save_state — should NOT match StateBackendExtension."""

    async def load_state(self, workflow_id):
        return None

    async def delete_state(self, workflow_id):
        pass


class _MissingName:
    """Missing name attribute — should NOT match ExportExtension."""

    def export(self, workflow_id, artifacts, output_dir):
        return ""


class _MissingCancel:
    """Missing cancel — should NOT match SchedulerExtension."""

    async def schedule(self, schedule_id, cron, callback):
        pass

    async def list_schedules(self):
        return []


class _MissingNotify:
    """Empty class — should NOT match NotifierExtension."""

    pass


class _MissingGetCommands:
    """Has name but no get_commands — should NOT match CLIExtension."""

    name = "bad"


class _MissingFetchTemplate:
    """Missing fetch_template — should NOT match TemplateProviderExtension."""

    async def list_templates(self, query=""):
        return []


class _MissingAuthorize:
    """Missing authorize — should NOT match AuthExtension."""

    async def authenticate(self, request):
        return None


def test_missing_save_state_rejected():
    assert not isinstance(_MissingSaveState(), StateBackendExtension)


def test_missing_name_rejected():
    assert not isinstance(_MissingName(), ExportExtension)


def test_missing_cancel_rejected():
    assert not isinstance(_MissingCancel(), SchedulerExtension)


def test_missing_notify_rejected():
    assert not isinstance(_MissingNotify(), NotifierExtension)


def test_missing_get_commands_rejected():
    assert not isinstance(_MissingGetCommands(), CLIExtension)


def test_missing_fetch_template_rejected():
    assert not isinstance(_MissingFetchTemplate(), TemplateProviderExtension)


def test_missing_authorize_rejected():
    assert not isinstance(_MissingAuthorize(), AuthExtension)
