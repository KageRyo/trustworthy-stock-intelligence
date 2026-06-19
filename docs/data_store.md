# Data Store Plan

## Decision

Use PostgreSQL as the medium-term source of truth and read store for market
data snapshots, ticker universes, prediction batches, and warning history.

The project can still fetch data from yfinance, TWSE, or another provider API.
The provider API is the ingestion source, not the durable state layer.

## Why Not Only Call Provider APIs Per Request?

Ticker lookup and dashboard rendering can call an API directly, but trustworthy
ML risk analysis needs stronger properties:

- reproducible input snapshots
- auditability for predictions and warning changes
- stable calibration and backtest datasets
- data freshness tracking
- provider outage isolation
- provider correction/revision tracking

The intended flow is:

```text
Provider API
-> ingestion job
-> PostgreSQL market_bars and metadata
-> feature/inference job
-> prediction_batches and warning_records
-> Go API / dashboard
```

## Freshness Target

The minimum near-real-time target is 5-minute bars.

Supported interval values:

```text
1m
5m
1d
```

Daily models must remain labeled as daily models. A 5-minute data ingestion
pipeline does not automatically make the prediction model a 5-minute model.

## Initial Tables

The docker-compose PostgreSQL service initializes:

```text
universes
tickers
universe_tickers
ingestion_runs
market_bars
prediction_batches
warning_records
```

Schema file:

```text
infra/postgres/init/001_schema.sql
```

## Market Data Ingestion

Install the optional DB dependency before writing to PostgreSQL:

```bash
python -m pip install -e ".[db]"
```

Start the local database:

```bash
docker compose up postgres
```

Ingest 5-minute watchlist bars:

```bash
python -m scripts.ingest_market_data \
  --tickers NVDA 2330 \
  --interval 5m \
  --universe-name watchlist
```

The CLI downloads provider data, validates it through Pydantic schemas, upserts
`tickers`, attaches them to `universes`, records an `ingestion_runs` row, and
upserts `market_bars`. It prints a `market_data_ingestion.v1` summary schema.

Use dry-run mode when validating provider coverage without writing to the DB:

```bash
python -m scripts.ingest_market_data \
  --tickers NVDA 2330 \
  --interval 5m \
  --dry-run
```

## Provider Notes

yfinance is useful for local pilot workflows and supports Yahoo symbols such as:

```text
NVDA
2330.TW
6488.TWO
```

For the dashboard and API, Taiwan stock codes should remain user-facing numeric
codes such as `2330`. Provider suffixes belong in ingestion metadata, not in the
main dashboard search experience.

TWSE/TPEx official sources should be evaluated for Taiwan market production-like
ingestion. yfinance remains acceptable for local demo and early pipeline tests.

## Current Limitation

The current Go API still reads `latest_warnings.json`. PostgreSQL is available
through docker-compose and market bars can be ingested into it, but the
DB-backed Go warning store is still a future task.
