# Changelog

## [0.2.0] - 2026-04-24

### Changed
- **OSS / Pro boundary tightened.** `rooben_pro` imports removed from the OSS core. The CLI now exposes only the `filesystem` state backend; persistent backends are contributed by Pro via the extension protocol. The `go` command no longer advertises `--template` (a runtime stub that required `rooben-pro`). `check_spec_integrations` is OSS-native and Pro extends via the extension protocol.
- **Repository hygiene.** `.DS_Store` files untracked; `.gitignore` strengthened with comprehensive patterns for Python, Node, test, and editor artifacts.

### Fixed
- CI restored to green after a period of Pro-integration-induced failures.

### Known next
- Dashboard added to `docker compose up` plus a seeded demo workflow (`make demo`) so the UI is reachable without an API key — landing in a follow-up commit on this version line.
- End-to-end test harness that verifies the README quickstart — landing in a follow-up commit on this version line.

## [0.1.0] - 2026-03-24

### Added
- Initial Release
