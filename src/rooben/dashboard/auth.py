"""Simple API key authentication for OSS.

If ROOBEN_API_KEYS is set, requests must include a matching Bearer token.
If not set, all requests are allowed (dev mode).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request

from rooben.dashboard.models.user import ANONYMOUS_USER, CurrentUser


def _get_api_keys() -> list[str]:
    """Read allowed API keys from ROOBEN_API_KEYS env var (comma-separated)."""
    from rooben.config import get_settings
    raw = get_settings().rooben_api_keys.strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def _auth_enabled() -> bool:
    return len(_get_api_keys()) > 0


async def require_auth(request: Request) -> CurrentUser:
    """FastAPI dependency: validate API key if auth is enabled."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

    keys = _get_api_keys()
    if keys:
        if token and token in keys:
            request.state.current_user = ANONYMOUS_USER
            return ANONYMOUS_USER
        raise HTTPException(
            status_code=401 if not token else 403,
            detail="Missing or invalid API key",
        )

    # Dev mode — no keys configured
    request.state.current_user = ANONYMOUS_USER
    return ANONYMOUS_USER


_auth_fn: Callable | None = None


def get_auth_dependency() -> Callable:
    """Return the current auth dependency (Pro override or default)."""
    return _auth_fn or require_auth


def set_auth_dependency(fn: Callable) -> None:
    """Replace the auth dependency (called by Pro during startup)."""
    global _auth_fn
    _auth_fn = fn


def get_current_user_id(request: Request) -> str | None:
    """Extract user ID from request state (set by auth dependency)."""
    state = getattr(request, "state", None)
    if state is None:
        return ANONYMOUS_USER.id
    user = getattr(state, "current_user", ANONYMOUS_USER)
    return user.id if user else None


def validate_ws_token(token: str | None) -> bool:
    """Validate a WebSocket token. Returns True if valid or auth disabled."""
    keys = _get_api_keys()
    if not keys:
        return True
    return token is not None and token in keys
