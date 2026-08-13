# Trustworthy Stock Intelligence

[![CI](https://github.com/KageRyo/trustworthy-stock-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/KageRyo/trustworthy-stock-intelligence/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-0.3.2-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Go](https://img.shields.io/badge/go-1.25-blue)
![TypeScript](https://img.shields.io/badge/typescript-7.0-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

**Status: Active Open-Source Project**

Software maturity: operational prototype. This is a public portfolio project
for trustworthy ML and backend systems, with reproducible pilot evidence rather
than externally validated research.

## What Problem Does This Solve?

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

## Current Status

Version `0.3.2` is a maintenance and security release following the
`0.3.1` open-source product and research-quality release:

- Experiment 007 uses purged walk-forward train/calibration/test boundaries and
  per-row `label_end_date` overlap checks.
- Calibration results report ECE, Brier score, simple no-feature baselines, and
  breakdowns by fold, ticker, and year without presenting limited predictive
  skill as a trading edge.
- A dedicated AUC invariance audit records per-fold sample identity, recovered
  Platt parameters, ranking behavior, and mean-fold, weighted, and pooled AUC.
- Model-family comparisons, paired bootstrap intervals, and calibration-drift
  audits make uncertainty and failure cases inspectable rather than implied.
- Reproducible Taiwan and US/Taiwan transfer pilots are recorded with explicit
  current-universe, coverage, and provider-data limitations.
- Repository controls include required CI, Dependabot, vulnerability analysis,
  race tests, full-history Gitleaks scanning, and SHA-pinned CodeQL analysis.
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
- Ticker-level feature attributions, warning-history timelines, calibration
  drift state, and per-run TAI audit artifacts are available through typed
  contracts and reproducible artifacts.
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
http://<dashboard-host>:5175
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

## Example Output

The typed analysis response contains warning, trust, model, freshness,
explanations, and limitations:

```json
{
  "schema_version": "analysis.v1",
  "ticker": "2330",
  "date": "2026-07-28",
  "run_id": "daily-baseline-20260728",
  "data_as_of": "2026-07-28",
  "generated_at": "2026-07-29T00:10:00Z",
  "warning": {
    "level": "watch",
    "risk_probability": 0.1832,
    "calibrated_risk_probability": 0.1214,
    "alert_threshold": 0.15,
    "watch_threshold": 0.10,
    "summary": "Moderate drawdown-risk signal that should remain on watch."
  },
  "trust": {
    "trust_score": 0.0952,
    "uncertainty_score": 0.4321,
    "calibration_method": "platt",
    "trust_status": "limited_trust",
    "uncertainty_status": "acceptable_uncertainty",
    "summary": "Trust is below the configured alert threshold."
  },
  "model": {
    "name": "logistic_regression",
    "model_bundle": "baseline_daily_v1"
  },
  "data_freshness": {
    "data_as_of": "2026-07-28",
    "generated_at": "2026-07-29T00:10:00Z",
    "last_loaded_at": "2026-07-29T00:11:00Z",
    "file_modified_at": "",
    "record_count": 101
  },
  "reasons": [
    {
      "code": "probability_above_watch_threshold",
      "severity": "watch",
      "title": "Risk probability above watch threshold",
      "detail": "The calibrated probability is above the watch threshold."
    }
  ],
  "limitations": ["Drawdown-risk analysis, not investment advice."]
}
```

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

## Evaluation Evidence

The current reproducible pilot uses an S&P 100 snapshot, a 5-day/-5% drawdown
label, and 39 sliding walk-forward folds:

```text
252 train dates
-> 5 purged dates
-> 63 calibration dates
-> 5 purged dates
-> 63 test dates
```

Mean fold results:

| Variant | AUC | Brier | ECE | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Training-window event-rate prior | 0.5000 | 0.0935 | 0.0655 | 0.0000 | 0.0000 | 0.0000 |
| Raw logistic | 0.6153 | 0.2318 | 0.3736 | 0.1432 | 0.4502 | 0.2101 |
| Logistic + Platt at 0.5 | 0.6086 | 0.0917 | 0.0546 | 0.0622 | 0.0015 | 0.0030 |
| Logistic + Platt, threshold tuned on calibration only | 0.6086 | 0.0917 | 0.0546 | 0.1469 | 0.4344 | 0.2077 |

Calibration improved Brier and ECE over the raw logistic output in 38 of 39
folds. The exception covers the COVID-19 regime shift and is retained as a
failure case. Improvements over the no-feature prior are modest, and the fixed
0.5 warning threshold is unusable after calibration. See
`experiments/007_research_evidence/README.md` for dates, hashes, standard
deviations, subgroup checks, commands, and limitations.

The evidence record now also includes a paired model-family comparison with
bootstrap intervals, Taiwan current-universe pilots, and a US/Taiwan
cross-market transfer pilot. These artifacts demonstrate reproducible
engineering and expose failure modes; they do not claim a production-ready
warning policy or comprehensive market coverage.

## Limitations

- This is an S&P 100 daily-data pilot with survivorship and provider-revision
  risk, not evidence of all-market or intraday performance.
- Taiwan and cross-market pilots are available, but their current-universe,
  selected-symbol, provider, sector, liquidity, and market-cap coverage limits
  mean they are not all-market validation.
- Paired bootstrap intervals are reported for the documented comparisons. ECE
  remains bin-dependent, and pilot intervals do not remove data-selection or
  external-validation limitations.
- Transaction cost is outside the current risk-probability claim because the
  project does not execute a trading strategy. It becomes mandatory for any
  future strategy backtest.
- Provider snapshots are now fingerprinted, but repeat-download revision audits
  and licensed formal-research data are still open work.
- Trust scores and abstention policies are engineered and tested, but have not
  yet been externally validated as guarantees of safety or reliability.

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
| Review research evidence and gaps | `experiments/007_research_evidence/README.md` |
| Review data/model licensing | `docs/data_and_model_licenses.md` |
| Review public/private boundaries | `docs/public_private_boundary.md` |
| Develop and test changes | `docs/development.md` |
| Cite or contribute | `CITATION.cff`, `CONTRIBUTING.md` |
| Review release notes | `CHANGELOG.md` |

## Development Checks

Run the same checks before commit:

```bash
python -m pytest
python -m ruff check src tests scripts dashboard
cd services/api-gateway-go
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go vet ./...
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go run golang.org/x/vuln/cmd/govulncheck@v1.6.0 ./...
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go test ./...
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=1 go test -race ./...
cd ../../frontend/stock-dashboard
npm test -- --run
npm run build
npm audit --audit-level=moderate
```

CI runs Python tests/lint, Go API tests, and frontend tests/build on push and
pull request events. Dependabot covers Python, Go, npm, and GitHub Actions.
Basic static analysis covers Python with Ruff, Go with `go vet`, pinned
`govulncheck`, and race tests, and TypeScript through the production build's
typecheck. A least-privilege, SHA-pinned Gitleaks workflow scans repository
history, while the SHA-pinned CodeQL workflow analyzes Python, Go, and
JavaScript/TypeScript. Native GitHub Secret Scanning and Push Protection are
enabled; their status is recorded in `.github/REPOSITORY_SETTINGS.md`.
Applied remote controls and remaining plan-dependent settings are recorded in
`.github/REPOSITORY_SETTINGS.md`.

## Environment Versions

Project targets:

| Runtime | Version |
| --- | --- |
| Python package | `0.3.2` |
| Python | `>=3.10`, CI uses `3.11` |
| Go API | `1.25.x` |
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

## Data And Model License

Repository source code and documentation are Apache License 2.0. That license
does not grant rights to downloaded Yahoo Finance, TWSE, or TPEx data. Raw data
and local model artifacts are gitignored; users must comply with each provider's
terms and separately review redistribution or commercial use. See
`docs/data_and_model_licenses.md`.

## Roadmap

The v0.4.0 scope is product and open-source readiness: scheduled 5-minute
watchlist ingestion, provider health and freshness/stale-state handling,
queue-backed prediction jobs, warning-change detection, and richer
session-scoped watchlists. Point-in-time universe membership and licensed
historical data remain valuable research-quality enhancements, but are not
blockers for using or contributing to the project. Detailed work lives in
`docs/project_roadmap.md` and `docs/backlog.md`.

## License

Apache License 2.0
