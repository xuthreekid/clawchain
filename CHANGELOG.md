# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Frontend README.md with project-specific documentation
- Frontend `.env.example` for environment variable reference
- Backend data directory `.gitkeep` files to ensure directory structure is tracked
- Bilingual docs entry points (`docs/zh`, `docs/en`)
- Docs structure cleanup and simplification
- Open-source metadata files (LICENSE, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT)

### Changed

- Backend `requirements.txt`: added upper version bounds to avoid breaking changes
- `.gitignore`: preserve `.gitkeep` files in data directories
- Heartbeat reliability: avoid premature cron event consumption
- Heartbeat token stripping: no longer swallows short non-empty reminder text
- Cron semantics: explicit errors for mutating cron actions when `cron.enabled=false`
- README split into bilingual versions (`README.zh-CN.md`, `README.en.md`)

### Fixed

- Frontend README was generic Next.js template, now ClawChain-specific
- Missing `.gitkeep` files causing empty data directories not to be tracked
