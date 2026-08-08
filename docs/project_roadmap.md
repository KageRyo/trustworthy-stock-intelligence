# Project Roadmap

## Goal

Trustworthy Stock Intelligence is a human-in-the-loop stock risk assessment
system. The main user flow is:

```text
stock ticker
-> market data
-> calibrated drawdown-risk model
-> uncertainty and trust score
-> warning level and reasons
-> dashboard/API analysis
```

The system focuses on trustworthy AI behavior: calibration, uncertainty,
abstention, transparency, auditability, and clear limitations. It is not an
investment recommendation system or automated trading system.

## Current State: 0.3.0

Version `0.3.0` is the research-evidence-hardening release. It is a
reproducible pilot, not externally validated research or investment advice.

Completed:

- leakage-aware baseline and deep-learning training/inference foundations
- trust score, uncertainty, warning levels, and reason codes
- PostgreSQL schema for tickers, market bars, watchlists, prediction batches,
  and warning records
- Go API gateway with DB-required startup, Swagger/OpenAPI, CORS, watchlists,
  latest warnings, and ticker analysis
- TypeScript dashboard with runtime schemas, English and 正體中文, ticker search,
  latest warnings, and session watchlists
- on-demand Python analysis bridge for missing ticker records
- US and Taiwan ticker handling, including Taiwan alphanumeric codes and TPEx
  emerging-stock fallback
- purged walk-forward evaluation with label-overlap checks, calibration
  diagnostics, baseline comparisons, and Experiment 007 audit artifacts
- required Python, Go, frontend, dependency, race-test, and full-history
  Gitleaks CI checks
- public-source documentation for licensing, security boundaries, citation, and
  contribution workflow

## Target Architecture

```text
Provider APIs
-> scheduled ingestion
-> PostgreSQL market_bars
-> Python feature and prediction jobs
-> PostgreSQL prediction_batches / warning_records
-> Go API gateway
-> TypeScript dashboard
```

The optional JSON export remains useful for notifications, snapshots, and debug
artifacts, but PostgreSQL is the serving source of truth.

## Next Milestones

### 0.3.x: Public Release Hardening

Complete the remaining repository-level public-readiness checks:

1. Verify native GitHub Secret Scanning and Push Protection settings.
2. Review the full Git history and commit-email privacy decision without
   rewriting history unless the maintainer explicitly requests it.
3. Keep CodeQL, Gitleaks, Dependabot, and required CI checks healthy.
4. Keep citation, contribution, release, and public/private-boundary documents
   aligned with the actual repository settings.

### 0.4.0: Comparative Evidence

Use the same purged walk-forward protocol, data fingerprint, and alert-oriented
metrics for the baseline families before making model claims:

1. Compare logistic, tree, and deep models under identical splits.
2. Add confidence intervals and paired bootstrap comparisons.
3. Report calibration, false alarm rate, miss rate, lead time, coverage, and
   selective risk for every model family.

### 0.5.0: Taiwan and Cross-Market Evidence

1. Evaluate Taiwan listed, TPEx listed, and TPEx emerging symbols within
   market, with explicit coverage and data-quality metadata.
2. Evaluate cross-market transfer only after within-market evaluation is
   reproducible and limitations are recorded.

### 0.6.0: Drift and Trust Under Shift

1. Monitor calibration drift and trust-score degradation over time.
2. Test stale data, provider revisions, market-noise perturbations, and
   abstention thresholds under distribution shift.

## Product Track After the Evidence Milestones

The dashboard remains the main product surface. Product work should preserve
the DB-backed, schema-first serving boundary while research evidence matures:

1. Scheduled 5-minute ingestion for user/session watchlists.
2. Warning history and change detection:

```text
new alert
new watch
upgraded
downgraded
resolved
persistent alert
low-trust warning
```

3. Ticker detail timelines for risk probability, trust score, uncertainty, and
   warning level.
4. Freshness badges and stale-data downgrade behavior in API/dashboard.
5. Market coverage metadata for US, TWSE, TPEx listed, and TPEx emerging
   symbols.

Later product work includes queue-based prediction jobs, a model-run TAI audit
artifact, feature attribution beyond reason codes, provider health monitoring,
and richer portfolio/watchlist grouping. These do not replace the evidence
milestones above.

## Later Research

- Build a point-in-time universe to measure survivorship and membership bias.
- Repeat provider-revision audits with licensed, versioned formal-research data.

## Engineering Rules

- Use schema-first contracts for API, provider parsing, CLI summaries, and
  frontend validation.
- Run Python, Go, and frontend tests before commit/push.
- Commit in tested slices with `type(scope): summary`.
- Do not commit `.env`, downloaded data, model bundles, or generated caches.
- Keep ticker symbols as strings.
- Keep Go serving dependent on PostgreSQL; missing DB should fail startup.
- Keep research claims scoped to the protocol, coverage, and evidence actually
  available in the corresponding experiment report.
