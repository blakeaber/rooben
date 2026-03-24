"""Extension protocols for Rooben plugin system.

Third-party packages can implement these protocols and register them via
Python entry points (``rooben.extensions.*``). The core framework discovers
and loads conforming extensions at startup.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StateBackendExtension(Protocol):
    """Custom state persistence backend (e.g., S3, Redis)."""

    async def save_state(self, workflow_id: str, state: dict[str, Any]) -> None: ...

    async def load_state(self, workflow_id: str) -> dict[str, Any] | None: ...

    async def delete_state(self, workflow_id: str) -> None: ...


@runtime_checkable
class ExportExtension(Protocol):
    """Custom export format (e.g., PDF, DOCX, Notion)."""

    name: str

    def export(self, workflow_id: str, artifacts: list[dict[str, Any]], output_dir: str) -> str: ...


@runtime_checkable
class SchedulerExtension(Protocol):
    """Custom scheduling backend (e.g., Celery, cloud schedulers)."""

    async def schedule(self, schedule_id: str, cron: str, callback: Any) -> None: ...

    async def cancel(self, schedule_id: str) -> None: ...

    async def list_schedules(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class NotifierExtension(Protocol):
    """Webhook/notification extension (e.g., Slack, email, PagerDuty)."""

    async def notify(self, event: str, payload: dict[str, Any]) -> None: ...


@runtime_checkable
class CLIExtension(Protocol):
    """Additional CLI commands registered as click groups."""

    name: str

    def get_commands(self) -> Any: ...  # Returns click.Group


@runtime_checkable
class TemplateProviderExtension(Protocol):
    """Remote template source (e.g., marketplace, registry)."""

    async def list_templates(self, query: str = "") -> list[dict[str, Any]]: ...

    async def fetch_template(self, template_id: str) -> dict[str, Any]: ...


@runtime_checkable
class AuthExtension(Protocol):
    """Custom authentication/authorization provider."""

    async def authenticate(self, request: Any) -> dict[str, Any] | None: ...

    async def authorize(self, user: dict[str, Any], resource: str, action: str) -> bool: ...
