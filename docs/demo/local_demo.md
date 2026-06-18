# Local Demo Walkthrough

This walkthrough runs the v1 local end-to-end demo:

```text
Python ML inference
-> atomic latest_warnings.json
-> Go API Gateway
-> Streamlit Dashboard Live API tab
```

The demo is not investment advice and does not run live trading.

## Prerequisites

Prepare these local artifacts first:

```text
data/raw/sp100/ohlcv.csv
data/artifacts/sp100_transformer_model_bundle/
```

The raw data, model bundle, and generated latest prediction files are local
artifacts and are not committed to git.

Install the Python package and dashboard dependencies:

```bash
pip install -e ".[dashboard,deep,dev]"
```

Go 1.22 or newer is required for the API gateway.

## 1. Generate Latest Warnings

```bash
make predict-latest
```

This writes:

```text
data/artifacts/latest_predictions.csv
data/artifacts/latest_warnings.json
```

`latest_warnings.json` is written atomically, so the Go API sees either the
previous complete file or the next complete file.

Override paths when needed:

```bash
DATA_INPUT=data/raw/sp100/ohlcv.csv \
MODEL_BUNDLE=data/artifacts/sp100_transformer_model_bundle \
make predict-latest
```

## 2. Start Go API

In a second terminal:

```bash
make api
```

If Go is installed in a conda environment:

```bash
GO=/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/go make api
```

Open or curl:

```text
http://localhost:8080/health
http://localhost:8080/metrics
http://localhost:8080/api/v1/status
http://localhost:8080/api/v1/models/current
http://localhost:8080/api/v1/warnings/latest?level=watch&limit=20
http://localhost:8080/api/v1/warnings/latest?level=alert&sort=trust_score&order=desc&limit=20
```

The API reloads the warning file when its modification time changes. If reload
fails, it keeps serving the last valid batch and reports the error through
`/health` and `/api/v1/status`.

## 3. Start Dashboard

In a third terminal:

```bash
make dashboard
```

Open:

```text
http://localhost:8501
```

Use the sidebar:

```text
API base URL: http://localhost:8080
API warning limit: 20
```

Open the `Live API` tab. It shows:

- API health and warning load status
- current model metadata
- generated and last-loaded timestamps
- latest alert warnings
- latest watch warnings
- raw health/status/model payloads

## 4. Verify Tests

```bash
make test-python
GO=/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/go make test-go
make lint
```

Or, if `go` is on `PATH`:

```bash
make test-all
```

## Expected Demo Story

The demo shows that the Python ML core produces calibrated, uncertainty-aware
warning records; the Go gateway serves those records without running inference;
and the Streamlit dashboard can inspect both experiment artifacts and the live
API output.

## Optional Docker Demo

After `make predict-latest` has created `data/artifacts/latest_warnings.json`,
run the API and dashboard containers:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8501
```

The dashboard container defaults to `http://api-gateway-go:8080` for the Live
API tab.
