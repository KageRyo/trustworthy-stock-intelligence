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

## Current State: 0.2.0

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

## Next Milestone: 0.3.0

Recommended focus:

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

## Later Milestones

0.4.0:

- queue-based prediction jobs instead of request-time synchronous analysis
- warning change endpoint and dashboard page
- watchlist ingestion scheduler
- model run audit artifact aligned with the TAI checklist

0.5.0:

- intraday-trained model path if 5-minute labels/features are validated
- feature attribution beyond reason codes
- provider health and coverage monitoring
- richer portfolio/watchlist grouping

Research track:

- preserve leakage-aware evaluation
- compare model families under walk-forward validation
- report calibration, false alarm rate, miss rate, lead time, coverage, and
  selective risk

## Engineering Rules

- Use schema-first contracts for API, provider parsing, CLI summaries, and
  frontend validation.
- Run Python, Go, and frontend tests before commit/push.
- Commit in tested slices with `type(scope): summary`.
- Do not commit `.env`, downloaded data, model bundles, or generated caches.
- Keep ticker symbols as strings.
- Keep Go serving dependent on PostgreSQL; missing DB should fail startup.
