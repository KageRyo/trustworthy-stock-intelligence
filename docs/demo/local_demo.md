# Local Demo Walkthrough

This walkthrough runs the `0.3.1` local dashboard demo:

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
python -m pip install -e ".[dev,db,dashboard,deep]"
cd frontend/stock-dashboard
npm ci
cd ../..
```

Go `1.25.x` or newer is required for the API gateway. Node `22.x` is used in
CI for the dashboard.

Create local environment configuration:

```bash
cp .env.example .env
```

Fill `.env` with local PostgreSQL credentials and CORS origins. Do not commit
`.env`.

## 1. Start PostgreSQL

```bash
docker compose up -d postgres
```

The database initializes schemas from:

```text
infra/postgres/init/
```

For an existing local database, apply any new migration files under that
directory before testing a new release.

## 2. Start Go API

```bash
make api API_ADDR=0.0.0.0:18080
```

The `api` target uses:

```text
TSI_DATABASE_URL
TSI_ON_DEMAND_ANALYSIS_COMMAND=python -m scripts.analyze_ticker_on_demand
TSI_ON_DEMAND_ANALYSIS_WORKDIR=<repo-root>
TSI_ON_DEMAND_ANALYSIS_TIMEOUT_SECONDS=120
```

Open:

```text
http://localhost:18080/health
http://localhost:18080/swagger/
http://localhost:18080/api/v1/status
http://localhost:18080/api/v1/models/current
```

If `TSI_DATABASE_URL` is missing or PostgreSQL is unreachable, the API should
fail at startup.

## 3. Start TypeScript Dashboard

```bash
make stock-dashboard
```

Open:

```text
http://localhost:5175
http://<dashboard-host>:5175
```

The Vite dev server binds to `0.0.0.0`. It proxies API calls to
`http://127.0.0.1:18080` by default through `TSI_DASHBOARD_API_BASE_URL`.

## 4. Try Ticker Analysis

Search for:

```text
NVDA
2330
00981A
5240
```

Expected behavior:

- stored warning records return immediately
- missing tickers trigger the configured Python on-demand command
- provider-backed but insufficient-history symbols return typed `abstain`
  analysis instead of an unstructured failure
- Taiwan alphanumeric symbols remain Taiwan symbols, not US tickers
- TPEx emerging fallback can resolve supported emerging-stock codes

## 5. Verify API Directly

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

## 6. Run Checks

```bash
python -m pytest
python -m ruff check src tests scripts dashboard
cd services/api-gateway-go
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go test ./...
cd ../../frontend/stock-dashboard
npm test -- --run
npm run build
npm audit --audit-level=moderate
```

## Optional Streamlit Dashboard

The Streamlit dashboard remains useful for research artifacts and a live API
tab:

```bash
streamlit run dashboard/app.py
```

Open:

```text
http://localhost:8501
```

## Optional JSON Export

`latest_warnings.json` can still be generated for debug snapshots,
notifications, or report exports. It is not the primary serving source for the
Go API in the `0.3.1` dashboard path.
