# Project Roadmap

## Goal

Trustworthy Stock Intelligence is a public open-source and portfolio project
for human-in-the-loop stock risk assessment. It is not a thesis vehicle. The
main user flow is:

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

## Current State: 0.3.1

Version `0.3.1` is the public open-source release built on the
research-evidence-hardening foundation. It remains a reproducible pilot, not
externally validated research or investment advice.

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
  diagnostics, baseline comparisons, paired bootstrap intervals,
  calibration-drift audits, and Experiment 007 audit artifacts
- Taiwan and US/Taiwan cross-market pilots with explicit provider,
  current-universe, and coverage limitations
- typed ticker feature attributions and warning-history timelines in the Go
  API and TypeScript dashboard
- per-run TAI audit artifacts that record evidence, limitations, and open risks
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

## v0.4.0: Product and Open-Source Readiness

The dashboard is the main product surface. The next release prioritizes a
usable, observable, DB-backed analysis flow over thesis-style novelty:

1. Schedule 5-minute ingestion for session watchlists, with explicit provider
   health, retry, and coverage state.
2. Make data freshness actionable in the API and dashboard: show the feature
   interval, flag stale predictions, and downgrade or block non-actionable
   outputs.
3. Move request-time on-demand analysis to queue-backed prediction jobs with
   progress and failure state, while retaining a usable local lookup bridge.
4. Build on the completed warning history/timeline with explicit warning-change
   detection:

```text
new alert
new watch
upgraded
downgraded
resolved
persistent alert
low-trust warning
```

5. Add richer session-scoped watchlist grouping, filtering, and cleanup while
   preserving the current no-auth privacy boundary.
6. Publish per-market coverage metadata for US, TWSE, TPEx listed, and TPEx
   emerging symbols.

## Maintenance and Release Hygiene

1. Keep CodeQL, Gitleaks, Dependabot, required CI checks, citation,
   contribution, release, and public/private-boundary documents accurate.
2. Review commit-email privacy and Git history without rewriting history unless
   the maintainer explicitly requests it.
3. Keep the reproducible experiments, model limitations, and TAI audit output
   linked from the public documentation.

## Research-Quality Enhancements (Not v0.4.0 Blockers)

- Build a legally usable point-in-time universe and quantify survivorship bias
  (#29); preserve its current status as the sole open issue.
- Expand the Taiwan pilots to dated membership, broader stratification, and
  reliable TPEx emerging history before making broad coverage claims.
- Re-run provider-revision, distribution-shift, and external-data studies with
  licensed, versioned research data where appropriate.

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
