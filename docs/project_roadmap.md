# Project Roadmap

## Goal

Trustworthy Stock Intelligence is a public open-source and portfolio project for human-in-the-loop
stock risk assessment. It is not a thesis vehicle. The main user flow is:

```text
stock ticker
-> market data
-> calibrated drawdown-risk model
-> uncertainty and trust score
-> warning level and reasons
-> dashboard/API analysis
```

The system focuses on trustworthy AI behavior: calibration, uncertainty, abstention, transparency,
auditability, and clear limitations. It is not an investment recommendation system or automated
trading system.

## Current State: 0.4.0

Version `0.4.0` is the product-readiness release following the `0.3.2` maintenance and security
release. It remains a reproducible pilot, not externally validated research or investment advice.

Completed:

- leakage-aware baseline and deep-learning training/inference foundations
- trust score, uncertainty, warning levels, and reason codes
- PostgreSQL schema for tickers, market bars, watchlists, prediction batches, and warning records
- Go API gateway with DB-required startup, Swagger/OpenAPI, CORS, watchlists, latest warnings, and
  ticker analysis
- TypeScript dashboard with runtime schemas, English and 正體中文, ticker search, latest warnings, and
  session watchlists
- on-demand Python analysis bridge for missing ticker records
- US and Taiwan ticker handling, including Taiwan alphanumeric codes and TPEx emerging-stock
  fallback
- purged walk-forward evaluation with label-overlap checks, calibration diagnostics, baseline
  comparisons, paired bootstrap intervals, calibration-drift audits, and Experiment 007 audit
  artifacts
- Taiwan and US/Taiwan cross-market pilots with explicit provider, current-universe, and coverage
  limitations
- typed ticker feature attributions and warning-history timelines in the Go API and TypeScript
  dashboard
- per-run TAI audit artifacts that record evidence, limitations, and open risks
- required Python, Go, frontend, dependency, race-test, and full-history Gitleaks CI checks
- scheduled five-minute watchlist ingestion with provider health and coverage
- freshness safety policy, PostgreSQL prediction jobs, typed job lifecycle API, and deterministic
  warning transitions
- dashboard operational states and richer session-scoped watchlist grouping
- readiness/metrics/structured observability plus a PostgreSQL E2E pipeline
- public-source documentation for licensing, security boundaries, citation, and contribution
  workflow

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

The optional JSON export remains useful for notifications, snapshots, and debug artifacts, but
PostgreSQL is the serving source of truth.

## v0.4.1+: Product and Open-Source Readiness

The dashboard is the main product surface. Future work prioritizes a usable, observable, DB-backed
analysis flow over thesis-style novelty:

1. Obtain a legally usable point-in-time constituent archive and complete the paired
   survivorship-bias benchmark in Issue #29.
1. Validate 5-minute data quality and interval-specific model behavior before presenting intraday
   predictions as more than ingestion coverage.
1. Harden the local prediction worker into a production job/worker deployment with progress
   tracking, scheduled recovery, and operational runbooks.
1. Expand ticker-universe ingestion and coverage reporting without claiming all-market coverage
   until historical membership and provider completeness are evidenced.

## Maintenance and Release Hygiene

1. Keep CodeQL, Gitleaks, Dependabot, required CI checks, citation, contribution, release, and
   public/private-boundary documents accurate.
1. Preserve contributor-email privacy and avoid history rewrites during normal maintenance.
1. Keep the reproducible experiments, model limitations, and TAI audit output linked from the public
   documentation.

## Research-Quality Enhancements (Not v0.4.0 Blockers)

- Build a legally usable point-in-time universe and quantify survivorship bias (#29); preserve its
  current status as the sole open issue.
- Expand the Taiwan pilots to dated membership, broader stratification, and reliable TPEx emerging
  history before making broad coverage claims.
- Re-run provider-revision, distribution-shift, and external-data studies with licensed, versioned
  research data where appropriate.

## Engineering Rules

- Use schema-first contracts for API, provider parsing, CLI summaries, and frontend validation.
- Run Python, Go, and frontend tests before commit/push.
- Commit in tested slices with `type(scope): summary`.
- Do not commit `.env`, downloaded data, model bundles, or generated caches.
- Keep ticker symbols as strings.
- Keep Go serving dependent on PostgreSQL; missing DB should fail startup.
- Keep research claims scoped to the protocol, coverage, and evidence actually available in the
  corresponding experiment report.
