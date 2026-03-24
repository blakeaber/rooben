"""Extension installer — copy extensions into .rooben/extensions/ for local use."""

from __future__ import annotations

import json
import shutil
import logging
from pathlib import Path

logger = logging.getLogger("rooben.extensions")


def _tier1_dir() -> Path:
    """Return the path to the bundled extensions directory."""
    return Path(__file__).resolve().parent.parent.parent.parent / "extensions"


def _install_dir() -> Path:
    """Return the path to the user's installed extensions directory."""
    return Path(".rooben/extensions")


def _load_index() -> dict:
    """Load the Tier 1 extension index."""
    index_path = _tier1_dir() / "_index.json"
    if not index_path.exists():
        return {"extensions": []}
    with open(index_path) as f:
        return json.load(f)


def _examples_dir() -> Path:
    """Return the path to the docs/examples/extensions directory."""
    return Path(__file__).resolve().parent.parent.parent.parent / "docs" / "examples" / "extensions"


def find_extension_source(name: str) -> Path | None:
    """Find an extension by name in the Tier 1 directory or docs/examples/.

    Searches in order:
    1. Tier 1 extension index (_index.json)
    2. Tier 1 directory by name (rglob fallback)
    3. docs/examples/extensions/ (community examples for CLI install)
    """
    index = _load_index()
    for ext in index.get("extensions", []):
        if ext["name"] == name:
            source = _tier1_dir() / ext["path"]
            if source.exists():
                return source
    # Fallback: search by directory name in Tier 1
    for yaml_file in _tier1_dir().rglob("rooben-extension.yaml"):
        if yaml_file.parent.name == name:
            return yaml_file.parent
    # Secondary fallback: search docs/examples/extensions/
    examples = _examples_dir()
    if examples.exists():
        for yaml_file in examples.rglob("rooben-extension.yaml"):
            if yaml_file.parent.name == name:
                return yaml_file.parent
    return None


def install_extension(name: str) -> Path:
    """Install an extension by name. Returns the install path.

    Raises FileNotFoundError if extension not found.
    Raises FileExistsError if already installed.
    """
    source = find_extension_source(name)
    if source is None:
        raise FileNotFoundError(f"Extension '{name}' not found in available extensions")

    dest = _install_dir() / name
    if dest.exists():
        raise FileExistsError(f"Extension '{name}' is already installed at {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    logger.info("extension.installed", extra={"name": name, "path": str(dest)})
    return dest


def uninstall_extension(name: str) -> None:
    """Uninstall an extension by name.

    Raises FileNotFoundError if not installed.
    """
    dest = _install_dir() / name
    if not dest.exists():
        raise FileNotFoundError(f"Extension '{name}' is not installed")

    shutil.rmtree(dest)
    logger.info("extension.uninstalled", extra={"name": name})


def list_installed() -> list[str]:
    """List names of installed extensions."""
    install_dir = _install_dir()
    if not install_dir.exists():
        return []
    return sorted(
        d.name for d in install_dir.iterdir()
        if d.is_dir() and (d / "rooben-extension.yaml").exists()
    )


def is_installed(name: str) -> bool:
    """Check if an extension is installed."""
    return (_install_dir() / name / "rooben-extension.yaml").exists()
