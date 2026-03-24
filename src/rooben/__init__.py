"""Rooben — autonomous agent orchestration framework."""

__version__ = "0.1.0"


# Lazy public API — avoids importing heavy deps at import time
def __getattr__(name: str):
    if name == "public_api":
        import importlib
        return importlib.import_module("rooben.public_api")
    raise AttributeError(f"module 'rooben' has no attribute {name}")
