# Trustworthy Stock Intelligence

[![CI](https://github.com/KageRyo/trustworthy-stock-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/KageRyo/trustworthy-stock-intelligence/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-0.2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Go](https://img.shields.io/badge/go-1.22-blue)
![TypeScript](https://img.shields.io/badge/typescript-5.6-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

Trustworthy Stock Intelligence is a local stock drawdown-risk analysis system.
It accepts a stock ticker as input and returns a schema-validated risk analysis:

```text
ticker
-> market data ingestion
-> calibrated risk probability
-> uncertainty and trust score
-> warning level
-> reason codes and limitations
-> dashboard/API response
```

The project is not investment advice, an automated trading system, or an exact
price prediction tool. It is designed for human-in-the-loop risk assessment with
auditable data, model, and API contracts.

## Current Release

Version `0.2.0` is the first dashboard-oriented release:

- PostgreSQL is the source of truth for tickers, watchlists, market bars,
  prediction batches, and warning records.
- The Go API requires PostgreSQL at startup and serves schema-owned API
  responses.
- The TypeScript dashboard is the primary UI for ticker search and risk
  analysis.
- On-demand analysis can generate a missing ticker record through the Python ML
  core, then write the result back to PostgreSQL.
- US stocks, Taiwan listed stocks, TPEx listed stocks, Taiwan alphanumeric ETF
  codes, and TPEx emerging-stock daily fallback data are supported where the
  providers have coverage.
- The dashboard supports English and 正體中文.

## Quick Start

Create local configuration:

```bash
cp .env.example .env
```

Fill in local PostgreSQL values in `.env`. Do not commit `.env`.

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Install dependencies:

```bash
python -m pip install -e ".[dev,db,dashboard,deep]"
cd frontend/stock-dashboard
npm ci
cd ../..
```

Start the API on all interfaces:

```bash
make api API_ADDR=0.0.0.0:18080
```

Start the stock dashboard on all interfaces:

```bash
make stock-dashboard
```

Open:

```text
http://localhost:5175
http://140.123.105.126:5175
```

Swagger UI is available from the Go API:

```text
http://localhost:18080/swagger/
http://localhost:18080/openapi.yaml
```

## Example Tickers

Use the dashboard search box or call the API directly:

```text
GET /api/v1/analysis/NVDA
GET /api/v1/analysis/2330
GET /api/v1/analysis/00981A
GET /api/v1/analysis/5240
```

Ticker handling:

| Input | Intended market behavior |
| --- | --- |
| `NVDA` | US stock through yfinance |
| `2330` | Taiwan local code, TWSE first |
| `6488.TWO` | TPEx listed symbol |
| `00981A` | Taiwan alphanumeric ETF code, not a US ticker |
| `02001L` | Taiwan leveraged/inverse-style local code |
| `5240` | Can resolve to TPEx emerging fallback when listed providers miss |

If the provider has data but the local model cannot produce a calibrated
prediction with enough history, the API returns a typed `abstain` analysis with
an `insufficient_history` reason code instead of `ticker_not_found`.

## Architecture

```text
Provider APIs: yfinance / TWSE / TPEx
-> Python ingestion and ML core
-> PostgreSQL market_bars / prediction_batches / warning_records
-> Go API gateway
-> TypeScript dashboard
```

The optional `latest_warnings.json` export is only a debug, notification, or
snapshot artifact. It is not the primary serving store.

## Documentation

Start from the documentation index:

```text
docs/README.md
```

High-traffic documents:

| Need | Document |
| --- | --- |
| Use the dashboard and ticker search | `docs/user_guide.md` |
| Run the local demo | `docs/demo/local_demo.md` |
| Understand the system architecture | `docs/architecture.md` |
| Understand PostgreSQL and provider data | `docs/data_store.md` |
| Read API contracts | `docs/api/warning_api.md`, `docs/api/analysis_api.md` |
| Review trustworthy AI checkpoints | `docs/trustworthy_ai_checklist.md` |
| Develop and test changes | `docs/development.md` |
| Review release notes | `CHANGELOG.md` |

## Development Checks

Run the same checks before commit:

```bash
python -m pytest
python -m ruff check src tests scripts dashboard
cd services/api-gateway-go
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go test ./...
cd ../../frontend/stock-dashboard
npm test -- --run
npm run build
```

CI runs Python tests/lint, Go API tests, and frontend tests/build on push and
pull request events.

## Environment Versions

Project targets:

| Runtime | Version |
| --- | --- |
| Python package | `0.2.0` |
| Python | `>=3.10`, CI uses `3.11` |
| Go API | `1.22.x` |
| Node.js CI runtime | `22.x` |
| TypeScript | `5.6.x` |
| PostgreSQL container | `17-alpine` |

The verified local GPU research environment is documented in
`docs/environment.md`.

## Repository Layout

```text
src/tsi/                  Python data, features, labels, models, trust, evaluation
scripts/                  CLI entry points for ingestion, training, prediction
services/api-gateway-go/  Go PostgreSQL-backed API gateway
frontend/stock-dashboard/ TypeScript React dashboard
dashboard/                Streamlit research and live API dashboard
infra/postgres/init/      PostgreSQL schema and migrations
docs/                     User, API, architecture, research, and development docs
tests/                    Python tests for leakage-sensitive and serving behavior
experiments/              Experiment notes and reports
```

## License

Apache License 2.0
