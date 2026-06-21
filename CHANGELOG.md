# Changelog

## 0.2.0 - 2026-06-21

### Added

- TypeScript stock dashboard as the primary ticker analysis UI.
- PostgreSQL-backed Go API serving warning records, ticker analysis, and
  watchlists.
- Swagger UI and OpenAPI 3.1 API documentation.
- On-demand ticker analysis path from Go API to the Python ML core.
- English and 正體中文 dashboard localization.
- Taiwan ticker support for numeric symbols, alphanumeric ETF-style symbols,
  TPEx listed suffixes, and TPEx emerging fallback.
- Schema-first provider parsing, API payload validation, and frontend Zod
  validation.

### Changed

- PostgreSQL is now the serving source of truth. `latest_warnings.json` remains
  an optional debug, notification, or snapshot artifact.
- Dashboard watchlists are user/session driven instead of preloaded defaults.
- Documentation is organized by user guide, architecture, API contracts,
  trustworthy AI, research protocol, development, and release workflow.

### Fixed

- Taiwan alphanumeric tickers such as `00981A` and `02001L` are no longer
  classified as US tickers.
- TPEx emerging tickers can return typed `abstain` analysis when provider data
  exists but model history is insufficient.
- Stale US ticker aliases created before Taiwan normalization are merged into
  the corrected Taiwan ticker metadata path.

## 0.1.0 - Initial Research Baseline

- Leakage-aware stock drawdown-risk labeling.
- Baseline model, calibration, trust score, and warning-level evaluation.
- Research documentation and experiment notes.
