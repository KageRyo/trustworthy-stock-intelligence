# Changelog

## Unreleased

## 0.7.0 - 2026-10-07

### Changed

- Serving now defaults to `--feature-set technical_range`:
  - It adds 5 split-adjusted range and drawdown features to the 7 technical features: Parkinson and
    Garman-Klass volatility, ATR(14) as a share of price, 20-day volatility, and drawdown from the
    20-day high.
  - In Experiment 017, against `technical`, AUC rose by 0.023 to 0.029 on S&P 100, on 402 held-out
    S&P 500 tickers, and on 53 Taiwan large caps. Watch recall rose by 0.034 to 0.047.
  - At the `alert_rate:0.05` default on S&P 100, alert precision rose from 0.250 to 0.279 and recall
    from 0.195 to 0.220.
  - The batch `model_bundle` now records the set as `baseline_latest:<feature_set>:<input>`.
  - `--feature-set technical` keeps the previous features.

### Added

- `tsi.features.volatility` range features, `tsi.features.market` as-of aligned market-relative
  features, and named feature sets in `tsi.features.sets`.
- `scripts/download_market_reference.py` for US reference series (SPY, ^VIX, Select Sector SPDR
  ETFs, and a Yahoo sector map) and the Taiwan TAIEX (^TWII).
- `scripts/evaluate_feature_sets.py`, which compares feature sets on identical walk-forward folds
  with paired fold-bootstrap intervals. Experiments 015 and 016 accept `--feature-set` and
  `--market-reference`.

### Notes

- Market regime features (SPY return and drawdown, VIX level and change) lowered AUC and alert
  recall in Experiment 017, so serving does not use them. A 60-day beta added 0.005 to 0.010 AUC in
  the US samples but nothing significant in Taiwan, and it would need a reference-data path in
  serving, so it remains experimental.

## 0.6.0 - 2026-10-07

### Changed

- Serving now chooses thresholds with calibration-window alert-rate policies:
  - `--alert-policy alert_rate:0.05` (alerts are the top 5% of calibration risk).
  - `--watch-policy alert_rate:0.2` (watch is the top 20%).
  - These replace the F1 threshold and the fixed 0.8 watch ratio.
  - On the S&P 100 pilot, alert days per ticker-month fall from 6.75 to 1.67, and precision beats F1
    in 85% of folds. Recall falls from 0.52 to 0.20.
  - `--alert-policy objective --watch-policy ratio` keeps the previous behavior.

### Added

- `AlertPolicy` threshold selection (`f1`, `target_precision`, `alert_rate`) and Experiment 016
  (`scripts/evaluate_alert_policies.py`).
- `alert_policy` batch metadata in Python schemas, PostgreSQL batch metadata, the Go analysis
  response, OpenAPI, and the dashboard, with a small-calibration-sample flag for single-ticker runs.

### Fixed

- Ticker analysis now uses calibration-drift and alert-policy metadata from the record's own batch
  instead of the most recent batch, which could be an unrelated on-demand run.

### Notes

- Alert precision remains low in absolute terms (about 0.16 in the median fold against a 0.10 base
  rate). Feature work is the next planned step. Issue #29 remains open.

## 0.5.0 - 2026-10-06

### Changed

- Serving now defaults to `--trust-method reliability`.
  - `uncertainty_score` comes from date-block bootstrap-ensemble disagreement and Ledoit-Wolf
    feature novelty, ranked against the calibration window.
  - `trust_score` is per-ticker data quality (labeled-history depth, staleness) multiplied by the
    calibration-drift multiplier.
  - Neither score is a function of the risk probability.
  - `--trust-method legacy` keeps the previous entropy-based behavior.
- Epistemic uncertainty no longer blocks alerts; it only moves below-watch rows to `abstain`.
- The default alert trust threshold is 0.4 for reliability trust.
- Expect more alerts at unchanged precision: in the S&P 100 pilot, alert volume rose from about 17%
  to about 32% of rows and recall from 0.26 to 0.52.
- Migrated the dashboard from Tailwind CSS 3 to 4.3.3 to clear new `braces`, `micromatch`, and
  `source-map-js` advisories in `npm audit`.
- Refreshed torch 2.14.0 / torchvision 0.29.0 (CPU and cu126), security-patched Python dependencies
  (werkzeug, urllib3, mako, tornado, notebook, jupyterlab), frontend minor/patch dependencies, and
  SHA-pinned GitHub Actions.

### Added

- Class-conditional conformal sets, `ReliabilityAssessor`, and a date-block bootstrap ensemble.
- Risk-coverage selective-prediction metrics with base-rate-adjusted Brier skill.
- Row-level reliability reason codes with Go API explanations and English and 正體中文 dashboard copy.
- Experiment 015 (`scripts/evaluate_selective_trust.py`), recording that epistemic signals do not
  identify more reliable predictions on the S&P 100 pilot.

### Fixed

- The selective-trust experiment rejects output directories that escape `--output-root` (SonarCloud
  S8707).

### Notes

- Trust scores and the alert policy are not externally validated. A precision- or volume-targeted
  alert policy is the next planned step.
- Issue #29 remains open.

## 0.4.4 - 2026-09-22

### Changed

- Refreshed the Go `pgx` dependency and the frontend dependency groups, including the Vitest 5.0.1
  test-toolchain update, with synchronized lockfiles.
- Refreshed GitHub Actions and CodeQL pins while preserving SHA-pinned CI and security scanning.

### Notes

- This is a backward-compatible dependency-maintenance release. The project remains an operational
  prototype and reproducible pilot, not externally validated research or investment advice.
- Issue #29 remains open pending a legally usable historical constituent archive, matching
  inactive/delisted OHLCV, rights review, and a completed paired benchmark.

## 0.4.3 - 2026-09-09

### Added

- Added versioned point-in-time identity/import and coverage-audit tooling plus paired
  current-versus- historical-universe benchmark reporting without closing Issue #29 prematurely.
- Added a schema-first five-minute market-bar quality audit with session/grid, duplicate, OHLCV,
  revision, and expected-ticker coverage checks; fail-closed quality results are not persisted.

### Changed

- Updated the operational prototype documentation and release metadata to describe the current
  data-quality, freshness, worker-recovery, and daily-model boundaries.
- Kept TorchAudio at `2.11.0` while upgrading the stable-ABI-compatible Torch/TorchVision profile to
  `2.13.0`/`0.28.0` for the patched PyTorch security baseline.

### Security

- Raised the setuptools build and lock floor to `83.0.0` (locked at `84.0.0`) for the Unicode
  normalization sdist exclusion advisory.
- Upgraded Vitest to `4.1.11` and refreshed the frontend lockfile for the `@vitest/mocker` advisory.
- Upgraded PyTorch to `2.13.0`, the first patched release for the `torch.jit.script`
  memory-corruption advisory; CPU and CUDA 12.6 profiles remain locked and tested.

### Notes

- This remains an operational prototype and reproducible pilot, not externally validated research or
  investment advice. Issue #29 remains open pending legally usable historical constituents,
  inactive/delisted OHLCV, and a completed real paired benchmark.

## 0.4.2 - 2026-08-19

### Added

- Added a committed uv lock, Python version pin, and optional mise runtime pin for reproducible
  contributor and maintainer environments.
- Added mutually exclusive uv CPU and CUDA 12.6 PyTorch profiles while keeping the published `deep`
  extra backward compatible.

### Changed

- Constrained the deep-learning stack to the verified PyTorch 2.11 family and aligned local, CI, and
  container runtimes on Go 1.25.13 and Node.js 22.23.2.
- Replaced the Conda-first contributor path with uv and separated portable requirements, current
  maintainer hardware, and historical GPU provenance.

### Security

- Updated the Go runtime from vulnerable 1.25.12 runners to 1.25.13, resolving the standard-library
  findings reported by `govulncheck`.

## 0.4.1 - 2026-08-14

### Added

- Defined a public `tsi` Python API for reusable feature, labeling, model, evaluation, trust, and
  serving-schema primitives.
- Added the `tsi` console command and `python -m tsi` entry point for package version checks, local
  CSV inspection, and deterministic metric evaluation.
- Added package metadata, PyPI project URLs, wheel/sdist validation, and a tag-triggered GitHub
  Actions Trusted Publishing workflow.

### Changed

- Split provider-ingestion dependencies into the `data` extra so the base library install remains
  focused on offline Python/ML core utilities.
- Added build and Twine validation tools to the development extra.

### Notes

- The PyPI package is the Python/ML core only. The Go API, PostgreSQL workers, and TypeScript
  dashboard remain separate deployment surfaces.
- The project remains a trustworthy-ML operational prototype with modest pilot predictive
  performance; this release makes no investment or production- deployment claim.

## 0.4.0 - 2026-08-13

### Added

- Scheduled five-minute watchlist ingestion with provider health, bounded retries, market coverage
  metadata, and PostgreSQL persistence.
- PostgreSQL-backed prediction jobs with idempotency, worker leases, typed completion/failure
  states, and an API job-status contract.
- Deterministic warning transitions for new, upgraded, downgraded, resolved, persistent, and
  low-trust warning states.
- Dashboard freshness, trust, provider coverage, prediction-job lifecycle, and session-scoped
  watchlist grouping/filtering/cleanup states.
- Readiness probes, structured JSON request/worker logs, runtime metrics, and a deterministic
  PostgreSQL watchlist-to-warning end-to-end CI job.

### Fixed

- Qualified PostgreSQL prediction-job claim columns for `UPDATE ... FROM` compatibility and included
  persisted feature attributions in the latest warning query.

### Documentation

- Documented provider coverage, freshness safety behavior, prediction jobs, warning transitions,
  dashboard operations, observability, E2E checks, and the remaining licensed point-in-time universe
  blocker in Issue #29.

## 0.3.2 - 2026-08-13

### Changed

- Updated the frontend toolchain, including Vite, the React plugin, PostCSS, Lucide, TypeScript,
  Zod, Vitest, and related type/build dependencies.
- Made the Ruff 0.16 migration explicit while preserving the existing lint baseline.
- Grouped routine Dependabot minor and patch updates by ecosystem while keeping major and security
  updates available for focused review.

### Security

- Migrated the CodeQL workflow to the SHA-pinned CodeQL Action v4 release.

### Fixed

- Restored the official Apache License 2.0 text in the repository license file.

## 0.3.1 - 2026-08-09

### Added

- Ticker warning-history timelines and typed feature attributions across the PostgreSQL-backed Go
  API and TypeScript dashboard.
- Calibration-drift assessment/reason codes and a schema-first per-run TAI audit artifact that
  records evidence, limitations, and open risks.
- Reproducible current-universe Taiwan and US/Taiwan transfer pilots, aligned logistic/tree/GPU
  deep-model pilot evidence, and paired bootstrap artifacts.
- Official TWSE, TPEx listed, and TPEx emerging current-catalogue capture, with explicit market
  identity and coverage boundaries.
- `CITATION.cff`, contribution guidance, SHA-pinned CodeQL, and documented native GitHub Secret
  Scanning and Push Protection controls.

### Changed

- Repositioned the project as a public open-source portfolio project; v0.4 now prioritizes
  ingestion, freshness, prediction jobs, warning changes, and session-scoped watchlists over
  thesis-style novelty.
- Synchronized release metadata, OpenAPI documents, dashboard/API guides, environment guidance,
  local demo, roadmap, backlog, and citation data to version `0.3.1`.

### Security

- Continued full-history Gitleaks, CodeQL, Dependabot, CI, Go vulnerability, and race-test controls
  for the public repository.

## 0.3.0 - 2026-07-29

### Added

- Purged walk-forward research protocol with label-horizon gaps at train/calibration/test
  boundaries.
- Reproducible S&P 100 calibration evidence with fold, ticker, and yearly comparisons, plus a
  training-window event-rate baseline.
- SHA-256 fingerprints for downloaded OHLCV and ticker artifacts.
- Explicit false-discovery metrics alongside the legacy false-alarm/false- positive metric name.
- Dependabot configuration, cross-language basic static analysis, frontend dependency audit,
  SHA-pinned Gitleaks history scanning, repository-settings guidance, and a security policy.
- Data/model licensing and public/private boundary documentation.
- A reproducible Platt AUC invariance audit with per-fold sample hashes, calibrator diagnostics,
  ranking checks, and distinct mean-fold, weighted, and pooled AUC summaries.

### Changed

- README maturity is explicitly `Active Research`, with the product described as an operational
  prototype and research claims limited to pilot evidence.
- PostCSS is raised to a version that fixes GHSA-r28c-9q8g-f849.
- Historical Experiment 002 results are marked as unpurged preliminary evidence; Experiment 007 is
  the current calibration report.
- Public documentation uses deployment placeholders instead of a specific server address or private
  filesystem path.
- Ruff is constrained to the compatible `0.15.x` lint baseline; CI also runs `go vet`, while
  TypeScript remains checked by the production build.
- Remote `main` protection, Dependabot vulnerability alerts, and automatic security updates are
  enabled.
- The Go baseline is raised from `1.22.x` to `1.25.x`; `pgx/v5` is upgraded to `5.9.2`, the obsolete
  vulnerable `golang.org/x/crypto` dependency is removed, and `golang.org/x/text` is upgraded to
  `0.39.0` to address advisories exposed by Dependabot and `govulncheck`.
- Go CI now runs source-aware vulnerability analysis with pinned `govulncheck v1.6.0` and the race
  detector.
- GitHub Actions are SHA-pinned to Node 24-compatible releases, removing the runner-level Node 20
  deprecation path without changing application runtimes.

## 0.2.0 - 2026-06-21

### Added

- TypeScript stock dashboard as the primary ticker analysis UI.
- PostgreSQL-backed Go API serving warning records, ticker analysis, and watchlists.
- Swagger UI and OpenAPI 3.1 API documentation.
- On-demand ticker analysis path from Go API to the Python ML core.
- English and 正體中文 dashboard localization.
- Taiwan ticker support for numeric symbols, alphanumeric ETF-style symbols, TPEx listed suffixes,
  and TPEx emerging fallback.
- Schema-first provider parsing, API payload validation, and frontend Zod validation.

### Changed

- PostgreSQL is now the serving source of truth. `latest_warnings.json` remains an optional debug,
  notification, or snapshot artifact.
- Dashboard watchlists are user/session driven instead of preloaded defaults.
- Documentation is organized by user guide, architecture, API contracts, trustworthy AI, research
  protocol, development, and release workflow.

### Fixed

- Taiwan alphanumeric tickers such as `00981A` and `02001L` are no longer classified as US tickers.
- TPEx emerging tickers can return typed `abstain` analysis when provider data exists but model
  history is insufficient.
- Stale US ticker aliases created before Taiwan normalization are merged into the corrected Taiwan
  ticker metadata path.

## 0.1.0 - Initial Research Baseline

- Leakage-aware stock drawdown-risk labeling.
- Baseline model, calibration, trust score, and warning-level evaluation.
- Research documentation and experiment notes.
