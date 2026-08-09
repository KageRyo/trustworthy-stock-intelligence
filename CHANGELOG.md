# Changelog

## Unreleased

## 0.3.1 - 2026-08-09

### Added

- Ticker warning-history timelines and typed feature attributions across the
  PostgreSQL-backed Go API and TypeScript dashboard.
- Calibration-drift assessment/reason codes and a schema-first per-run TAI
  audit artifact that records evidence, limitations, and open risks.
- Reproducible current-universe Taiwan and US/Taiwan transfer pilots, aligned
  logistic/tree/GPU deep-model pilot evidence, and paired bootstrap artifacts.
- Official TWSE, TPEx listed, and TPEx emerging current-catalogue capture,
  with explicit market identity and coverage boundaries.
- `CITATION.cff`, contribution guidance, SHA-pinned CodeQL, and documented
  native GitHub Secret Scanning and Push Protection controls.

### Changed

- Repositioned the project as a public open-source portfolio project; v0.4 now
  prioritizes ingestion, freshness, prediction jobs, warning changes, and
  session-scoped watchlists over thesis-style novelty.
- Synchronized release metadata, OpenAPI documents, dashboard/API guides,
  environment guidance, local demo, roadmap, backlog, and citation data to
  version `0.3.1`.

### Security

- Continued full-history Gitleaks, CodeQL, Dependabot, CI, Go vulnerability,
  and race-test controls for the public repository.

## 0.3.0 - 2026-07-29

### Added

- Purged walk-forward research protocol with label-horizon gaps at
  train/calibration/test boundaries.
- Reproducible S&P 100 calibration evidence with fold, ticker, and yearly
  comparisons, plus a training-window event-rate baseline.
- SHA-256 fingerprints for downloaded OHLCV and ticker artifacts.
- Explicit false-discovery metrics alongside the legacy false-alarm/false-
  positive metric name.
- Dependabot configuration, cross-language basic static analysis, frontend
  dependency audit, SHA-pinned Gitleaks history scanning,
  repository-settings guidance, and a security policy.
- Data/model licensing and public/private boundary documentation.
- A reproducible Platt AUC invariance audit with per-fold sample hashes,
  calibrator diagnostics, ranking checks, and distinct mean-fold, weighted, and
  pooled AUC summaries.

### Changed

- README maturity is explicitly `Active Research`, with the product described as
  an operational prototype and research claims limited to pilot evidence.
- PostCSS is raised to a version that fixes GHSA-r28c-9q8g-f849.
- Historical Experiment 002 results are marked as unpurged preliminary
  evidence; Experiment 007 is the current calibration report.
- Public documentation uses deployment placeholders instead of a specific
  server address or private filesystem path.
- Ruff is constrained to the compatible `0.15.x` lint baseline; CI also runs
  `go vet`, while TypeScript remains checked by the production build.
- Remote `main` protection, Dependabot vulnerability alerts, and automatic
  security updates are enabled.
- The Go baseline is raised from `1.22.x` to `1.25.x`; `pgx/v5` is upgraded to
  `5.9.2`, the obsolete vulnerable `golang.org/x/crypto` dependency is removed,
  and `golang.org/x/text` is upgraded to `0.39.0` to address advisories exposed
  by Dependabot and `govulncheck`.
- Go CI now runs source-aware vulnerability analysis with pinned
  `govulncheck v1.6.0` and the race detector.
- GitHub Actions are SHA-pinned to Node 24-compatible releases, removing the
  runner-level Node 20 deprecation path without changing application runtimes.

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
