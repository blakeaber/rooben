"""Embedding providers — stub for OSS."""
from __future__ import annotations


class NullEmbeddingProvider:
    """No-op embedding provider."""
    async def embed(self, text: str) -> list[float]:
        return []
