# Backlog

This backlog tracks work after `0.2.0`. Items are grouped by product area, not
by implementation language.

## Near Term

```text
[Data] Schedule 5-minute ingestion for active watchlists.
[Data] Track provider freshness and provider coverage per ticker.
[API] Add warning changes endpoint.
[API] Add warning history/date endpoints.
[Dashboard] Add ticker detail timelines.
[Dashboard] Add warning changes page.
[Dashboard] Add freshness and low-trust badges.
[Trust] Generate model-run TAI audit artifacts.
[Docs] Keep release notes and documentation index current.
```

## Data And Providers

```text
[Data] Build broad US ticker universe metadata.
[Data] Build TWSE/TPEx listed universe metadata.
[Data] Build TPEx emerging universe metadata.
[Data] Add provider health checks and outage reporting.
[Data] Record provider source and query symbol for all market bars.
[Data] Validate intraday 5-minute data quality before model training.
```

## Modeling And Trust

```text
[Model] Add prediction job that consumes PostgreSQL market_bars directly.
[Model] Separate daily and intraday model metadata.
[Model] Add drift and stale-data monitoring.
[Trust] Add feature attribution for ticker detail pages.
[Trust] Add calibration monitoring over time.
[Trust] Add abstain-rate and coverage monitoring.
```

## API

```text
[API] GET /api/v1/warnings/changes
[API] GET /api/v1/history/dates
[API] GET /api/v1/history/{date}
[API] GET /api/v1/warnings/{ticker}/history
[API] GET /api/v1/watchlists
[API] Add schema version docs for every request/response model.
```

## Dashboard

```text
[Dashboard] Ticker detail page with probability, trust, uncertainty, and level timelines.
[Dashboard] Watchlist grouping and filtering.
[Dashboard] Warning changes page.
[Dashboard] Coverage state for unsupported/provider-missing symbols.
[Dashboard] Better empty, loading, stale, and error states.
```

## Research

```text
[Research] Keep walk-forward validation as the default.
[Research] Compare logistic, tree, and deep models under identical splits.
[Research] Report calibration, false alarm rate, miss rate, lead time, coverage, and selective risk.
[Research] Keep experiment reports under experiments/.
```

## Deferred

```text
[Deferred] Automated trading.
[Deferred] Investment recommendation wording.
[Deferred] LLM-based advice.
[Deferred] Full multimodal learning.
[Deferred] Production authentication and paid plans.
```
