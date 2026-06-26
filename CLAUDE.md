# CLAUDE.md — rooben (OSS)

**Read [`AGENTS.md`](AGENTS.md) first.** It is the single source of truth — the
plan→execute→verify→deliver architecture, the house conventions to match (lazy
imports, `public_api` contract, result-not-exception, structlog, Protocol seams), the
full CLI/Make surface, and the **Demo surfaces** table (the two zero-key demo paths).

Claude-specific reminders:
- Green before commit: `make test` (or `make test-all`); `make lint` (ruff).
- The `dashboard/extension_protocol.py` signatures are a CONTRACT with `rooben-pro` —
  changing them breaks the downstream Pro package (`tests/test_extension_protocol.py` guards it).
- Never commit secrets; document credential names only.
