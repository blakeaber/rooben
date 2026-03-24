"""Discover and load Rooben extensions via entry points (PEP 621)."""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Any

logger = logging.getLogger("rooben.extensions")

_extensions: dict[str, Any] | None = None


def _discover() -> dict[str, Any]:
    """Load all extensions registered under the 'rooben.extensions' entry point group."""
    global _extensions
    if _extensions is not None:
        return _extensions

    _extensions = {}
    eps = importlib.metadata.entry_points()
    # Python 3.12+ returns a SelectableGroups; 3.9-3.11 returns a dict
    group = eps.select(group="rooben.extensions") if hasattr(eps, "select") else eps.get("rooben.extensions", [])
    for ep in group:
        try:
            register_fn = ep.load()
            ext = register_fn()
            _extensions[ep.name] = ext
            logger.info("extension.loaded", extra={"name": ep.name})
        except Exception:
            logger.warning("extension.load_failed", extra={"name": ep.name}, exc_info=True)
    return _extensions


def has_extension(name: str) -> bool:
    """Check if a named extension is available."""
    return name in _discover()


def get_extension(name: str) -> Any | None:
    """Return the extension object, or None."""
    return _discover().get(name)


def get_pro_routers() -> list[dict[str, Any]]:
    """Return Pro dashboard routers if the Pro extension is loaded."""
    ext = get_extension("pro")
    if ext and hasattr(ext, "get_routers"):
        try:
            return ext.get_routers()
        except Exception:
            import logging
            logging.getLogger(__name__).warning("pro.get_routers failed", exc_info=True)
    return []


async def run_pro_startup(pool: Any, deps: Any) -> None:
    """Call the Pro extension's on_startup hook if available."""
    ext = get_extension("pro")
    if ext and hasattr(ext, "on_startup"):
        await ext.on_startup(pool, deps)


async def run_pro_shutdown(pool: Any, deps: Any) -> None:
    """Call the Pro extension's on_shutdown hook if available."""
    ext = get_extension("pro")
    if ext and hasattr(ext, "on_shutdown"):
        await ext.on_shutdown(pool, deps)


def get_pro_cli_commands() -> list[Any]:
    """Return Pro CLI commands if the Pro extension is loaded."""
    ext = get_extension("pro")
    if ext and hasattr(ext, "get_cli_commands"):
        return ext.get_cli_commands()
    return []
