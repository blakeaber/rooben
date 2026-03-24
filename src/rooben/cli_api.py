"""Thin httpx-based client for CLI → Dashboard API communication."""

from __future__ import annotations

from typing import Any

import httpx


class APIClient:
    """CLI client for the Rooben dashboard API."""

    def __init__(self) -> None:
        from rooben.config import get_settings
        _cfg = get_settings()
        self.base_url = _cfg.rooben_api_url
        self.api_key = _cfg.rooben_api_key

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def get(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}{path}", headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def post(self, path: str, data: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}{path}", headers=self._headers(),
                json=data or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def put(self, path: str, data: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{self.base_url}{path}", headers=self._headers(),
                json=data or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def delete(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.base_url}{path}", headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
