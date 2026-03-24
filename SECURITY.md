# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Rooben, please report it responsibly.

**Do NOT open a public issue.**

Instead, email **security@predicate.ventures** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and aim to release a fix within 7 days for critical issues.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Scope

The following are in scope:

- Credential leakage (API keys, tokens in logs or outputs)
- Authentication bypass in the dashboard API
- Code injection via specification YAML
- MCP server sandbox escapes
- Budget enforcement bypasses

The following are out of scope:

- Vulnerabilities in upstream dependencies (report to the dependency maintainer)
- Social engineering
- Denial of service via large specifications (this is a resource limit, not a vulnerability)

## Recognition

We appreciate responsible disclosure. Contributors who report valid security issues will be credited in the release notes (unless they prefer to remain anonymous).
