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
provider_health
prediction_batches
warning_records
```

Schema files:

```text
infra/postgres/init/001_schema.sql
infra/postgres/init/004_provider_health.sql
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

The CLI downloads provider data, validates it through Pydantic schemas, applies
bounded exponential-backoff retries, upserts `tickers`, attaches them to
`universes`, records an `ingestion_runs` row, upserts `market_bars`, and persists
per-provider/ticker observations in `provider_health`. It prints a
`market_data_ingestion.v1` summary containing the same typed health snapshots.

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

### Scheduled watchlist ingestion

The scheduler provides a bounded, DB-backed five-minute loop for a deliberate
watchlist. It reads active symbols at each tick, normalizes and de-duplicates
them, and processes each ticker independently so one provider outage does not
discard neighboring updates:

```bash
TSI_INGESTION_ENABLED=true \
python -m scripts.schedule_market_ingestion \
  --database-url "$TSI_DATABASE_URL" \
  --watchlist-name session-example
```

Use `--once` for a job runner or smoke test. The default is disabled and emits
a typed `scheduled_ingestion.v1` disabled summary without opening PostgreSQL:

```bash
python -m scripts.schedule_market_ingestion --disabled --once
```

An enabled schedule requires `TSI_DATABASE_URL` (or `--database-url`). The
five-minute interval is fixed for this job, polling defaults to 300 seconds,
and retry/backoff settings are bounded by the same provider-health policy used
by one-off ingestion. Each ticker uses its newest stored bar as a cursor and is
skipped when the next five-minute slot is already current, so normal ticks do
not refetch stored bars. Successful writes still use the existing
`(ticker, interval, timestamp, provider)` upsert key, making retries and
overlapping provider windows idempotent. Provider failures persist their health
snapshots even when no bar is available; the summary reports `success`,
`partial`, `failed`, or `no_tickers` per tick and identifies `skipped` tickers
that are already up to date.

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
5240.EMERGING
```

For the dashboard and API, Taiwan stock codes should remain user-facing numeric
codes such as `2330`. Provider suffixes belong in ingestion metadata, not in the
main dashboard search experience.

TWSE/TPEx official daily sources are used as Taiwan fallback providers for
on-demand ticker analysis when yfinance does not cover a Taiwan symbol. The
fallback order is:

```text
TWSE daily
-> TPEx listed daily
-> TPEx emerging-stock daily
```

Their responses are validated through explicit provider schemas before being
normalized into OHLCV rows. yfinance remains acceptable for local demo and early
pipeline tests, especially for US symbols and Taiwan symbols it already covers.

Taiwan symbols are stored as strings. Leading zeroes and suffix letters such as
`00981A` and `02001L` must not be converted to numbers.

## Current Limitation

The DB-backed API, watchlist state, local on-demand ticker analysis bridge,
Taiwan provider fallbacks, provider health persistence, freshness policy, and
scheduled five-minute watchlist ingestion are available. Broad US/Taiwan
universe ingestion, warning-change detection, actionable stale-state serving,
and intraday-trained models remain follow-up work.
