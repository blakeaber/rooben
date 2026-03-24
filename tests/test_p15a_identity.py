"""P15a — Identity & Multi-Tenancy Foundation unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── CurrentUser model ────────────────────────────────────────────────────


class TestCurrentUser:
    def test_fields(self):
        from rooben.dashboard.models.user import CurrentUser

        u = CurrentUser(id="u1", extras={"email": "a@b.com", "org_id": "org1", "role": "admin"})
        assert u.id == "u1"
        assert u.email == "a@b.com"
        assert u.org_id == "org1"
        assert u.role == "admin"

    def test_anonymous_user_sentinel(self):
        from rooben.dashboard.models.user import ANONYMOUS_USER

        assert ANONYMOUS_USER.id == "anonymous"
        assert ANONYMOUS_USER.email is None
        assert ANONYMOUS_USER.org_id is None
        assert ANONYMOUS_USER.role is None


# ── Auth middleware ──────────────────────────────────────────────────────


def _make_request(auth_header: str | None = None) -> MagicMock:
    """Build a mock Request with optional Authorization header."""
    req = MagicMock()
    req.headers = {}
    if auth_header:
        req.headers["Authorization"] = auth_header
    req.state = MagicMock()
    return req


class TestAuth:
    @pytest.mark.asyncio
    async def test_dev_mode_returns_anonymous(self):
        """No ROOBEN_API_KEYS → ANONYMOUS_USER."""
        from rooben.dashboard.auth import require_auth
        from rooben.dashboard.models.user import ANONYMOUS_USER

        with patch.dict("os.environ", {}, clear=True):
            req = _make_request()
            user = await require_auth(req)
            assert user.id == "anonymous"
            assert req.state.current_user == ANONYMOUS_USER

    @pytest.mark.asyncio
    async def test_flat_key_returns_anonymous(self):
        """Valid flat key → ANONYMOUS_USER."""
        from rooben.dashboard.auth import require_auth

        with patch.dict("os.environ", {"ROOBEN_API_KEYS": "key123"}, clear=True):
            req = _make_request("Bearer key123")
            user = await require_auth(req)
            assert user.id == "anonymous"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_403(self):
        """Invalid token with keys configured → 403."""
        from fastapi import HTTPException
        from rooben.config import reset_settings
        from rooben.dashboard.auth import require_auth

        with patch.dict("os.environ", {"ROOBEN_API_KEYS": "key123"}, clear=True):
            reset_settings()
            try:
                req = _make_request("Bearer wrong")
                with pytest.raises(HTTPException) as exc_info:
                    await require_auth(req)
                assert exc_info.value.status_code == 403
            finally:
                reset_settings()

    @pytest.mark.asyncio
    async def test_missing_header_raises_401(self):
        """No header with keys configured → 401."""
        from fastapi import HTTPException
        from rooben.config import reset_settings
        from rooben.dashboard.auth import require_auth

        with patch.dict("os.environ", {"ROOBEN_API_KEYS": "key123"}, clear=True):
            reset_settings()
            try:
                req = _make_request()
                with pytest.raises(HTTPException) as exc_info:
                    await require_auth(req)
                assert exc_info.value.status_code == 401
            finally:
                reset_settings()



# ── Query scoping ────────────────────────────────────────────────────────


