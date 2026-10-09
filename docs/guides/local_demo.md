# Local Demo Walkthrough

This walkthrough runs the `0.9.0` local dashboard demo:

```text
Provider APIs
-> Python on-demand ingestion and prediction
-> PostgreSQL warning records
-> Go API Gateway
-> TypeScript Stock Dashboard
```

The demo is not investment advice and does not run live trading.

## Prerequisites

Install Python, Go, frontend, and DB dependencies:

```bash
uv sync --locked --extra dev --extra db --extra dashboard --extra deep
mise install  # optional; installs the versions pinned in mise.toml
cd frontend/stock-dashboard
npm ci
cd ../..
```

Go `1.27.2` and Node `22.23.2` match CI. On WSL2, use Docker Desktop with WSL integration or one native Docker Engine, not both at the same time.

Create local environment configuration:

```bash
cp .env.example .env
```

Fill `.env` with local PostgreSQL credentials and CORS origins. Do not commit `.env`.

## 1. Start PostgreSQL

```bash
docker compose up -d postgres
```

The database initializes schemas from:

```text
infra/postgres/init/
```

For an existing local database, apply any new migration files under that directory before testing a new release.

## 2. Build Pooled Model Bundles

On-demand analysis scores a ticker that has no stored warning with the pooled model of its market. Build one bundle per market from a multi-ticker reference universe:

```bash
make model-bundles \
  US_BUNDLE_INPUT=data/raw/sp100_current/ohlcv.csv \
  TAIWAN_BUNDLE_INPUT=data/raw/tw_large/ohlcv.csv
```

This writes `us.json` and `taiwan.json` to `data/artifacts/model_bundles/` (`MODEL_BUNDLE_DIR` or `TSI_MODEL_BUNDLE_DIR` changes the location). Each bundle is schema-validated JSON with the fitted logistic parameters, calibrator, thresholds, drift result, and reliability references, so loading it runs no fitting and no pickle.

Use a current download for the reference universe. A bundle whose data ends more than 30 days before the scored row adds the reason code `model_bundle_stale`. Without a bundle for the ticker's market, on-demand analysis fits the ticker alone and adds `single_ticker_model`; [Experiment 020](../../experiments/020_serving_replay/README.md) found such models much weaker.

## 3. Start Go API

```bash
make api API_ADDR=0.0.0.0:18080
```

The `api` target uses:

```text
TSI_DATABASE_URL
TSI_ON_DEMAND_ANALYSIS_COMMAND=python -m scripts.analyze_ticker_on_demand
TSI_ON_DEMAND_ANALYSIS_WORKDIR=<repo-root>
TSI_ON_DEMAND_ANALYSIS_TIMEOUT_SECONDS=120
TSI_ON_DEMAND_MAX_CONCURRENCY=2
TSI_MODEL_BUNDLE_DIR=<repo-root>/data/artifacts/model_bundles
```

Open:

```text
http://localhost:18080/health
http://localhost:18080/swagger/
http://localhost:18080/api/v1/status
http://localhost:18080/api/v1/models/current
```

If `TSI_DATABASE_URL` is missing or PostgreSQL is unreachable, the API should fail at startup.

## 4. Start TypeScript Dashboard

```bash
make stock-dashboard
```

Open:

```text
http://localhost:5175
http://<dashboard-host>:5175
```

The Vite dev server binds to `0.0.0.0`. It proxies API calls to `http://127.0.0.1:18080` by default through `TSI_DASHBOARD_API_BASE_URL`.

## 5. Try Ticker Analysis

Search for:

```text
NVDA
2330
00981A
5240
```

Expected behavior:

- stored warning records return immediately
- missing tickers trigger the configured Python on-demand command, which scores them with the pooled bundle for their market (`logistic_regression_pooled`)
- provider-backed but insufficient-history symbols return typed `abstain` analysis instead of an unstructured failure
- Taiwan alphanumeric symbols remain Taiwan symbols, not US tickers
- TPEx emerging fallback can resolve supported emerging-stock codes

## 6. Verify API Directly

```bash
curl http://localhost:18080/api/v1/analysis/NVDA
curl http://localhost:18080/api/v1/analysis/2330
curl http://localhost:18080/api/v1/analysis/00981A
curl http://localhost:18080/api/v1/analysis/5240
```

Watchlist example:

```bash
curl http://localhost:18080/api/v1/watchlists/session-demo
curl -X POST http://localhost:18080/api/v1/watchlists/session-demo/tickers \
  -H "Content-Type: application/json" \
  -d '{"schema_version":"watchlist_add.v1","ticker":"2330","market":"auto","notes":""}'
```

The request body is a schema-owned `watchlist_add.v1` payload.

## 7. Run Checks

```bash
uv run --locked --no-sync python -m pytest
uv run --locked --no-sync python -m ruff check src tests scripts dashboard
cd services/api-gateway-go
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go test ./...
cd ../../frontend/stock-dashboard
npm test -- --run
npm run build
npm audit --audit-level=moderate
```

## Optional Streamlit Dashboard

The Streamlit dashboard remains useful for research artifacts and a live API tab:

```bash
uv run --locked --no-sync streamlit run dashboard/app.py
```

Open:

```text
http://localhost:8501
```

## Optional JSON Export

`latest_warnings.json` can still be generated for debug snapshots, notifications, or report exports. It is not the primary serving source for the Go API in the `0.9.0` dashboard path.
