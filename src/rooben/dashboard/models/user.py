"""Minimal user identity model for OSS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CurrentUser:
    """Resolved identity for the current request."""

    id: str  # "anonymous" in OSS
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def email(self) -> str | None:
        return self.extras.get("email")

    @property
    def org_id(self) -> str | None:
        return self.extras.get("org_id")

    @property
    def role(self) -> str | None:
        return self.extras.get("role")


ANONYMOUS_USER = CurrentUser(id="anonymous")
