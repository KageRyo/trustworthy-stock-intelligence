# Trustworthy Stock Intelligence

A research-oriented framework for explainable, calibrated, and uncertainty-aware stock risk early-warning.

This project does not aim to provide investment advice, automated trading, or exact stock price prediction.  
Instead, it reformulates stock analysis as a future risk-event detection problem.

## Side Project Direction

The repository is also being extended into a complete trustworthy deep-learning
stock risk alerting side project: calibrated prediction, uncertainty
estimation, trust scoring, warning decisions, audit-ready outputs, dashboard,
and a later Go API gateway around the Python ML core.

See `docs/project_roadmap.md` for the implementation roadmap and
engineering rules.

Current v1 demo references:

```text
docs/architecture.md
docs/demo/local_demo.md
docs/api/warning_api.md
```

## Research Focus

Trustworthy Stock Intelligence studies whether stock risk warning models can issue reliable warnings under noisy and non-stationary market conditions. The core objective is not to maximize trading profit or predict the next closing price, but to detect future drawdown risk events early and explain why a warning is produced.

The first milestone is:

```text
Milestone 1: TSI-Risk-v0
```

## Main Task

```text
Given historical market observations up to day t,
predict whether a stock will experience a drawdown risk event within the next H trading days.
```

Initial setting:

```text
Universe: S&P 100
Frequency: Daily
Horizon: 5 trading days
Risk event: future 5-day max drawdown <= -5%
```

## Inputs and Outputs

Input:

```text
historical OHLCV
technical indicators
market index features
```

Output:

```text
future risk-event probability
warning level
calibrated confidence
uncertainty estimate
explanation factors
```

## Dataset Roadmap

```text
Demo: DJIA 30
Main experiment v0: S&P 100
Formal research v1: S&P 500
Benchmark comparison: ACL18 / StockNet, CIKM18, BigData22
```

The first implementation phase focuses only on:

```text
S&P 100
Daily OHLCV
Technical indicators
Market index
5-day drawdown risk label
```

Yahoo Finance is used for pilot experiments. For formal research, higher-quality data sources such as WRDS/CRSP, Polygon, Tiingo, or official exchange data are preferred.

## Research Scope

This repository is a research codebase, not a stock application.

In scope for Milestone 1:

- leakage-free future drawdown risk labeling
- walk-forward validation
- baseline models: Logistic Regression, Random Forest, XGBoost
- probability calibration
- uncertainty-aware warning levels
- alert-oriented evaluation
- reproducible experiment documentation

Out of scope for Milestone 1:

- investment recommendation
- automated trading
- exact stock price prediction
- dashboard
- FastAPI service
- real-time streaming
- news NLP
- LLM agents
- RAG
- full multimodal learning
- high-frequency data
- Taiwan stock data
- Transformer-scale models

## Repository Structure

```text
configs/dataset/     Dataset definitions for demo, v0, and v1 research settings.
data/                Local data artifact documentation; raw datasets are gitignored.
src/tsi/data/        Downloading, preprocessing, universe loading, and temporal splits.
src/tsi/features/    Technical indicator feature generation.
src/tsi/labeling/    Risk-event labeling and warning-level definitions.
src/tsi/models/      Baseline warning models.
src/tsi/trust/       Calibration, uncertainty, and explainability modules.
src/tsi/evaluation/  Alert-oriented metrics, lead-time evaluation, and backtesting checks.
docs/                Research definitions and experiment protocol.
experiments/         Experiment notes and reports.
notebooks/           Exploratory notebooks.
scripts/             Command-line experiment entry points.
tests/               Unit tests for leakage-sensitive logic.
```

## Evaluation Principles

Accuracy alone is not sufficient for stock risk early-warning. The first milestone evaluates:

```text
Precision
Recall
F1
AUC
False Alarm Rate
Miss Rate
Brier Score
Expected Calibration Error
Lead Time
Coverage
Selective Risk
```

All evaluation should use temporal or walk-forward splits. Random train-test splits are not allowed for the main protocol.

## Pilot Data Download

Pilot S&P 100 and S&P 500 OHLCV downloads are implemented with `yfinance`.

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python -m scripts.prepare_data \
  --universe all \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

Downloaded files are written under `data/raw/` and are intentionally excluded from git. See `docs/data_download.md` for details.

## Environment

This project uses `pyproject.toml` as the dependency definition. On this machine, the recommended setup is:

```text
conda for the Python 3.11 GPU environment
uv for fast Python package installation
explicit PyTorch CUDA wheel for RTX 4090 GPU support
```

The verified local environment is:

```text
/mnt/8tb_hdd/ryo/miniconda3/envs/stock
Python 3.11.15
PyTorch 2.11.0+cu128
2 x NVIDIA GeForce RTX 4090 visible to PyTorch
```

See `docs/environment.md` for installation details.

## Baseline Training

The repository now supports a minimal leakage-aware baseline pipeline:

```text
OHLCV CSV
-> technical features
-> future drawdown labels
-> walk-forward split
-> logistic regression baseline
-> calibration on a dedicated calibration window
-> fold-level evaluation
```

Example training run:

```bash
python -m scripts.train \
  --input data/raw/sp100/ohlcv.csv \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --calibration-method platt \
  --output data/artifacts/sp100_logistic_summary.json \
  --predictions-output data/artifacts/sp100_logistic_predictions.csv
```

The training summary JSON reports both raw and calibrated test metrics. The
prediction CSV includes:

```text
date
ticker
risk_label
fold_id
model
risk_probability
calibrated_risk_probability
calibration_method
alert_threshold
watch_threshold
warning_level
```

By default, the training pipeline also selects an alert threshold on each
calibration window using the chosen threshold objective. This separates
probability calibration from downstream alert decisions.

## Evaluation

Prediction artifacts can be re-evaluated independently:

```bash
python -m scripts.evaluate \
  --input data/artifacts/sp100_logistic_predictions.csv \
  --prob-col calibrated_risk_probability \
  --output data/artifacts/sp100_logistic_eval.json
```

Trust-aware warning artifacts can be evaluated separately:

```bash
python -m scripts.evaluate_warnings \
  --input data/artifacts/sp100_transformer_predictions.csv \
  --output data/artifacts/sp100_transformer_warning_eval.json
```

This reports warning-level counts, alert precision/recall, false alarm and miss
rates, coverage, selective risk, and trust/uncertainty summaries by warning
level.

Decision thresholds can be swept over an existing prediction CSV without
retraining:

```bash
python -m scripts.sweep_warning_thresholds \
  --input data/artifacts/sp100_transformer_predictions.csv \
  --output data/artifacts/sp100_transformer_threshold_sweep.csv
```

Use this before dashboard work to compare alert/watch/abstain/no_alert
distributions under different trust score methods, trust thresholds, and
uncertainty thresholds.

To diagnose why a warning policy produces too many or too few alerts, summarize
probability, uncertainty, trust score, and threshold distributions:

```bash
python -m scripts.diagnose_predictions \
  --input data/artifacts/sp100_transformer_predictions.csv \
  --output data/artifacts/sp100_transformer_diagnostics.json
```

After training, warning evaluation, and threshold sweep, generate a Markdown
experiment report:

```bash
python -m scripts.report_trust_experiment \
  --summary data/artifacts/sp100_transformer_summary.json \
  --warning-eval data/artifacts/sp100_transformer_warning_eval.json \
  --threshold-sweep data/artifacts/sp100_transformer_threshold_sweep.csv \
  --output experiments/005_temporal_transformer_trust/report.md
```

## Deep Training

The first deep-learning entry point trains a Temporal Transformer on 60-day
feature windows. CUDA is required by default, and the script uses multiple GPUs
through PyTorch `DataParallel` when more than one CUDA device is available.

```bash
python -m scripts.train_deep \
  --input data/raw/sp100/ohlcv.csv \
  --lookback 60 \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --epochs 20 \
  --batch-size 256 \
  --watch-threshold-ratio 0.8 \
  --min-watch-threshold 0.05 \
  --trust-score-method subtractive \
  --output data/artifacts/sp100_transformer_summary.json \
  --predictions-output data/artifacts/sp100_transformer_predictions.csv \
  --model-output data/artifacts/sp100_transformer_model_bundle
```

The prediction CSV includes:

```text
date
ticker
risk_label
fold_id
model
risk_probability
calibrated_risk_probability
calibration_method
uncertainty_score
trust_score
alert_threshold
warning_level
```

## Model Bundle And Inference

Deep training can export a model bundle containing the latest successful fold's
model weights, model config, feature columns, standardizer, calibrator, trust
config, and thresholds. Use it for repeatable batch inference without
retraining:

```bash
python -m scripts.predict_deep \
  --input data/raw/sp100/ohlcv.csv \
  --model-bundle data/artifacts/sp100_transformer_model_bundle \
  --output data/artifacts/latest_predictions.csv \
  --json-output data/artifacts/latest_warnings.json \
  --latest-only
```

The optional JSON output is the serving-ready contract for the Go API gateway
and dashboard. The batch includes `schema_version`, `run_id`, `data_as_of`,
`generated_at`, `record_count`, and records. Each record includes the calibrated
risk probability, uncertainty score, trust score, warning level, thresholds, and
reason codes such as `probability_above_watch_threshold` or
`trust_below_alert_threshold`.

## Go API Gateway

The Go API is a PostgreSQL-backed gateway around precomputed warning records.
It does not run model inference in request handlers. `TSI_DATABASE_URL` is
required; the service should fail fast when PostgreSQL is unavailable.

```bash
cd services/api-gateway-go
TSI_DATABASE_URL=postgresql://tsi:tsi_local_password@localhost:55432/tsi \
  CGO_ENABLED=0 go run ./cmd/server
```

Endpoints:

```text
GET /health
GET /metrics
GET /openapi.yaml
GET /swagger/
GET /api/v1/status
GET /api/v1/tickers
GET /api/v1/watchlists/default
POST /api/v1/watchlists/default/tickers
DELETE /api/v1/watchlists/default/tickers/{ticker}
GET /api/v1/analysis/{ticker}
GET /api/v1/warnings/latest
GET /api/v1/warnings/latest?level=watch&limit=20
GET /api/v1/warnings/latest?level=alert&sort=trust_score&order=desc&limit=20
GET /api/v1/warnings/{ticker}
GET /api/v1/models/current
```

The API reads the latest `prediction_batches` and `warning_records` from
PostgreSQL and exposes typed watchlist endpoints backed by PostgreSQL. See
`docs/api/warning_api.md` for the API contract. Ticker-level dashboard analysis uses the typed
`/api/v1/analysis/{ticker}` contract documented in `docs/api/analysis_api.md`.
Swagger UI is available at `/swagger/`, and the OpenAPI document is available
at `/openapi.yaml`.

## Local Demo Commands

Common demo commands are collected in `Makefile`:

```bash
docker compose up postgres
make download-tickers WATCHLIST_TICKERS="NVDA 2330" DOWNLOAD_INTERVAL=1d
make predict-latest-baseline DATA_INPUT=data/raw/watchlist/ohlcv.csv
make ingest-market-data WATCHLIST_TICKERS="NVDA 2330" MARKET_INTERVAL=5m
make ingest-watchlist-data MARKET_INTERVAL=5m
make api
make stock-dashboard
make dashboard
make test-all
```

Override paths or binaries as needed:

```bash
GO=/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/go make test-go
DATABASE_URL=postgresql://tsi:tsi_local_password@localhost:55432/tsi make api
```

`predict-latest-baseline` is the no-bundle local path for real OHLCV data. It
trains a leakage-aware logistic baseline on the downloaded daily data, writes an
optional JSON export, and upserts the serving warning batch into PostgreSQL:

```text
data/artifacts/latest_predictions.csv
data/artifacts/latest_warnings.json
prediction_batches
warning_records
```

Numeric Taiwan stock codes are supported through the downloader. For example,
`2330` is downloaded from yfinance as `2330.TW` but remains `2330` in the
serving `ticker` field.

The local watchlist flow only covers the tickers you download. It does not mean
the loaded warning batch covers all US and Taiwan stocks. Use
`GET /api/v1/tickers` or the dashboard table to see the current loaded coverage.

## Data Store

PostgreSQL is included in `docker-compose.yml` as the medium-term source of
truth for ticker universes, 1m/5m/1d market bars, ingestion runs, prediction
batches, and warning records. The initial schema lives in:

```text
infra/postgres/init/001_schema.sql
```

The Go API reads warning records and watchlists from PostgreSQL. JSON warning
exports are local artifacts for debugging or notifications, not the API's
primary store. See `docs/data_store.md`.

Start PostgreSQL locally with:

```bash
docker compose up postgres
```

Install the optional PostgreSQL writer dependency and ingest fresh watchlist
bars with:

```bash
python -m pip install -e ".[db]"
make ingest-market-data WATCHLIST_TICKERS="NVDA 2330" MARKET_INTERVAL=5m
```

The ingestion command validates downloaded rows through Pydantic schemas and
prints a `market_data_ingestion.v1` summary. Five-minute ingestion improves
market-data freshness, but the current baseline and deep warning models remain
daily unless trained and labeled on intraday features.

## Dashboards

The TypeScript stock dashboard is the primary interactive UI for ticker-level
risk analysis. It reads typed Go API responses and validates them with Zod
schemas before rendering.

```bash
make frontend-install
make api
make stock-dashboard
```

Open:

```text
http://localhost:5173
```

The first version supports ticker search, typed `/api/v1/analysis/{ticker}`
results, warning/trust metrics, reason explanations, model metadata, and the
latest warnings table.

The Streamlit dashboard shows trust experiment artifacts and can also read the
Go API gateway through the Live API tab.

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

It reads the latest committed experiment summaries by default. Ticker-level
timelines are shown when the local ignored `predictions.csv` exists in the run
folder. The Live API tab reads `/health`, `/api/v1/status`,
`/api/v1/models/current`, and latest alert/watch warning queries from the API
base URL configured in the sidebar.

## Experiment Reports

Compare trust policies:

```bash
python -m scripts.compare_experiments \
  --runs \
    experiments/005_temporal_transformer_trust/runs/platt_entropy_wr08 \
    experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08 \
  --output experiments/005_temporal_transformer_trust/comparison.md
```

Export reliability bins for dashboard calibration diagnostics:

```bash
python -m scripts.export_reliability_bins \
  --input experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08/predictions.csv \
  --output experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08/reliability_bins.csv
```

## Status

The v1 local end-to-end demo is complete:

```text
Python predict_deep.py
-> atomic latest_warnings.json
-> Go API Gateway
-> Streamlit Dashboard Live API tab
```

CI runs Python tests, ruff, and Go API tests on push and pull request events.
