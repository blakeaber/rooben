"""Extension point protocols for the Rooben plugin system.

Third-party packages implement these protocols and register via
``pyproject.toml`` entry points under the ``rooben.extensions`` group.
All protocols are ``@runtime_checkable`` so the registry can verify
compliance at discovery time.

Example entry point (in a third-party ``pyproject.toml``)::

    [project.entry-points."rooben.extensions"]
    my_backend = "my_package:PostgresBackendExtension"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import click


@runtime_checkable
class StateBackendExtension(Protocol):
    """Extension point for state backends beyond the built-in filesystem backend."""

    name: str

    def create_backend(self, config: dict) -> object:
        """Return a ``StateBackend``-compatible object for the given *config*."""
        pass


@runtime_checkable
class ExportExtension(Protocol):
    """Extension point for output export formats (PDF, DOCX, etc.)."""

    name: str

    def export(self, report: object, output_path: str) -> None:
        """Write *report* to *output_path* in the extension's format."""
        pass


@runtime_checkable
class SchedulerExtension(Protocol):
    """Extension point for workflow scheduling."""

    name: str

    async def schedule(self, spec_path: str, cron: str, config: dict) -> str:
        """Schedule a workflow and return the schedule ID."""
        pass

    async def unschedule(self, schedule_id: str) -> None:
        """Remove a previously created schedule."""
        pass

    async def list_schedules(self) -> list[dict]:
        """List all active schedules."""
        pass


@runtime_checkable
class NotifierExtension(Protocol):
    """Extension point for workflow event notifications (Slack, email, webhooks, etc.)."""

    name: str

    async def notify(self, event_type: str, payload: dict) -> None:
        """Deliver a notification for the given *event_type*."""
        pass


@runtime_checkable
class CLIExtension(Protocol):
    """Extension point for additional CLI commands."""

    def register_commands(self, cli_group: click.Group) -> None:
        """Add commands or sub-groups to the Rooben CLI."""
        pass


@runtime_checkable
class TemplateProviderExtension(Protocol):
    """Extension point for template packs (marketplace, enterprise, community)."""

    name: str

    def list_templates(self) -> list[dict]:
        """Return metadata dicts for all templates this provider offers."""
        pass

    def get_template(self, template_id: str) -> str:
        """Return the YAML content for a specific template."""
        pass


@runtime_checkable
class AuthExtension(Protocol):
    """Extension point for authentication and authorization providers."""

    name: str

    async def authenticate(self, request: dict) -> object | None:
        """Authenticate a request and return a user object, or ``None``."""
        pass

    async def authorize(self, user: object, action: str, resource: str) -> bool:
        """Return ``True`` if *user* is permitted to perform *action* on *resource*."""
        pass