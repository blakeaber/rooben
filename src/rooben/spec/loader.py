"""Load a Specification from YAML or JSON files."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from rooben.spec.models import Specification


def load_spec(path: str | Path) -> Specification:
    """Parse a spec file (YAML or JSON) into a validated Specification."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    elif path.suffix == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(f"Unsupported spec format: {path.suffix}. Use .yaml, .yml, or .json")

    if not isinstance(data, dict):
        raise ValueError(f"Spec file must contain a mapping, got {type(data).__name__}")

    return Specification.model_validate(data)


def load_spec_from_string(yaml_string: str) -> Specification:
    """Parse a YAML string into a validated Specification."""
    data = yaml.safe_load(yaml_string)
    if not isinstance(data, dict):
        raise ValueError(f"Spec must contain a mapping, got {type(data).__name__}")
    return Specification.model_validate(data)
