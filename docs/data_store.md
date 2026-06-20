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
watchlists
watchlist_tickers
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

Once users add tickers through the dashboard watchlist API, ingestion can read a
specific watchlist directly. The current TypeScript dashboard creates
browser-session watchlist names, so production scheduling needs a deliberate
policy for which session or curated list to ingest:

```bash
python -m scripts.ingest_market_data \
  --watchlist-name session-example \
  --interval 5m
```

## Prediction Serving Store

The baseline latest prediction script can upsert the generated serving batch
into PostgreSQL:

```bash
python -m scripts.predict_latest_baseline \
  --input data/raw/watchlist/ohlcv.csv \
  --output data/artifacts/latest_predictions.csv \
  --json-output data/artifacts/latest_warnings.json \
  --write-db
```

This writes:

```text
prediction_batches
warning_records
```

The JSON file remains useful as an export/debug artifact, but the Go API reads
from PostgreSQL and requires `TSI_DATABASE_URL`.

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

TWSE/TPEx official daily sources are used as Taiwan fallback providers for
on-demand ticker analysis when yfinance does not cover a Taiwan symbol. Their
responses should be validated through explicit provider schemas before being
normalized into OHLCV rows. yfinance remains acceptable for local demo and early
pipeline tests, especially for US symbols and Taiwan symbols it already covers.

## Current Limitation

The DB-backed API, watchlist state, and local on-demand ticker analysis bridge
are available. The remaining gap is coverage automation: broad US/Taiwan ticker
universe ingestion, scheduled 5-minute updates, warning history/change
detection, and intraday-trained models still need to be implemented.
