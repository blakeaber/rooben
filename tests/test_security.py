"""Tests for security components."""

from __future__ import annotations

import os

import pytest

from rooben.security.budget import BudgetExceeded, BudgetTracker
from rooben.security.rate_limiter import RateLimiter
from rooben.security.sanitizer import OutputSanitizer


class TestBudgetTracker:
    @pytest.mark.asyncio
    async def test_token_budget_enforced(self):
        tracker = BudgetTracker(max_total_tokens=100)
        await tracker.record_tokens(50)
        await tracker.record_tokens(30)
        with pytest.raises(BudgetExceeded, match="tokens"):
            await tracker.record_tokens(30)

    @pytest.mark.asyncio
    async def test_task_budget_enforced(self):
        tracker = BudgetTracker(max_total_tasks=2)
        await tracker.record_task_completion()
        await tracker.record_task_completion()
        with pytest.raises(BudgetExceeded, match="tasks"):
            await tracker.record_task_completion()



class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        limiter = RateLimiter(max_per_minute=5)
        for _ in range(5):
            await limiter.acquire("agent-1")
        # Should have succeeded without blocking

    @pytest.mark.asyncio
    async def test_reset(self):
        limiter = RateLimiter(max_per_minute=2)
        await limiter.acquire("agent-1")
        await limiter.acquire("agent-1")
        limiter.reset("agent-1")
        await limiter.acquire("agent-1")  # Should work after reset


class TestOutputSanitizer:
    def test_redacts_api_key_pattern(self):
        sanitizer = OutputSanitizer()
        text = "My key is sk-ant-abc123XYZdef456ghijklmnop"
        result = sanitizer.sanitize(text)
        assert "sk-ant-" not in result
        assert "[REDACTED_SECRET]" in result

    def test_redacts_github_pat(self):
        sanitizer = OutputSanitizer()
        text = "Token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = sanitizer.sanitize(text)
        assert "ghp_" not in result

    def test_redacts_private_key(self):
        sanitizer = OutputSanitizer()
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIBog..."
        result = sanitizer.sanitize(text)
        assert "PRIVATE KEY" not in result

    def test_clean_text_unchanged(self):
        sanitizer = OutputSanitizer()
        text = "This is a normal output with no secrets."
        result = sanitizer.sanitize(text)
        assert result == text

    def test_check_returns_issues(self):
        sanitizer = OutputSanitizer()
        text = "key = sk-ant-abc123XYZdef456ghijklmnop"
        issues = sanitizer.check(text)
        assert len(issues) > 0

    def test_redacts_env_var_values(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-12345678901234567890"
        try:
            sanitizer = OutputSanitizer()
            text = "The API key is test-key-12345678901234567890 in production"
            result = sanitizer.sanitize(text)
            assert "test-key-12345678901234567890" not in result
            assert "[REDACTED]" in result
        finally:
            del os.environ["ANTHROPIC_API_KEY"]
