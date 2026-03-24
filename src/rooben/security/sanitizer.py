"""Output sanitizer — prevents credential leakage and prompt injection propagation."""

from __future__ import annotations

import os
import re

import structlog

log = structlog.get_logger()

# Patterns that suggest credential leakage in agent output
_SECRET_PATTERNS = [
    re.compile(r'(?:api[_-]?key|secret|token|password|credential)\s*[:=]\s*["\']?[A-Za-z0-9+/=_-]{20,}', re.I),
    re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'),
    re.compile(r'sk-[A-Za-z0-9]{20,}'),       # OpenAI-style
    re.compile(r'sk-ant-[A-Za-z0-9]{20,}'),    # Anthropic-style
    re.compile(r'ghp_[A-Za-z0-9]{36,}'),       # GitHub PAT
    re.compile(r'xox[bprs]-[A-Za-z0-9-]+'),    # Slack
]

# Env vars whose values should never appear in output
_SENSITIVE_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "LINEAR_API_KEY",
    "DATABASE_URL",
    "SECRET_KEY",
    "AWS_SECRET_ACCESS_KEY",
]


class OutputSanitizer:
    """
    Sanitizes agent output to prevent credential leakage.

    Scans text for known secret patterns and env var values,
    replacing them with redaction markers.
    """

    def __init__(self) -> None:
        self._env_values: list[str] = []
        for var in _SENSITIVE_ENV_VARS:
            val = os.environ.get(var, "")
            if val and len(val) > 8:  # Only redact non-trivial values
                self._env_values.append(val)

    def sanitize(self, text: str) -> str:
        """Remove secrets from text, returning sanitized version."""
        result = text

        # Redact known env var values
        for val in self._env_values:
            if val in result:
                result = result.replace(val, "[REDACTED]")
                log.warning("sanitizer.env_value_redacted")

        # Redact pattern matches
        for pattern in _SECRET_PATTERNS:
            match = pattern.search(result)
            if match:
                result = pattern.sub("[REDACTED_SECRET]", result)
                log.warning("sanitizer.pattern_redacted", pattern=pattern.pattern[:40])

        return result

    def check(self, text: str) -> list[str]:
        """Return list of issues found (without modifying text)."""
        issues = []
        for val in self._env_values:
            if val in text:
                issues.append("Output contains a sensitive environment variable value")
                break
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                issues.append(f"Output matches secret pattern: {pattern.pattern[:40]}")
        return issues
