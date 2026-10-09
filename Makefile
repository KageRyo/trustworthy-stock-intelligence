UV ?= uv
PYTHON ?= $(UV) run --locked --no-sync python
GO ?= go
STREAMLIT ?= $(UV) run --locked --no-sync streamlit
NPM ?= npm
MDFORMAT ?= uvx --with mdformat-gfm==1.0.0 mdformat==1.0.0
MARKDOWN_FILES := $(shell git ls-files '*.md' '*.mdx')

ifneq (,$(wildcard .env))
include .env
export
endif

DATA_INPUT ?= data/raw/sp100/ohlcv.csv
WATCHLIST_TICKERS ?= NVDA 2330
WATCHLIST_DATA_DIR ?= data/raw/watchlist
MODEL_BUNDLE ?= data/artifacts/sp100_transformer_model_bundle
LATEST_PREDICTIONS ?= data/artifacts/latest_predictions.csv
LATEST_WARNINGS ?= data/artifacts/latest_warnings.json
API_ADDR ?= :18080
GOCACHE ?= /tmp/tsi-go-build-cache
FRONTEND_DIR ?= frontend/stock-dashboard
FRONTEND_API_BASE_URL ?= http://127.0.0.1:18080
DATABASE_URL ?= $(TSI_DATABASE_URL)
ON_DEMAND_ANALYSIS_COMMAND ?= $(PYTHON) -m scripts.analyze_ticker_on_demand
ON_DEMAND_ANALYSIS_WORKDIR ?= $(CURDIR)
ON_DEMAND_ANALYSIS_TIMEOUT_SECONDS ?= 120
ON_DEMAND_MAX_CONCURRENCY ?= 2
MODEL_BUNDLE_DIR ?= $(if $(TSI_MODEL_BUNDLE_DIR),$(TSI_MODEL_BUNDLE_DIR),data/artifacts/model_bundles)
US_BUNDLE_INPUT ?= data/raw/sp100/ohlcv.csv
TAIWAN_BUNDLE_INPUT ?= data/raw/tw_large/ohlcv.csv
DOWNLOAD_INTERVAL ?= 1d
MARKET_INTERVAL ?= 5m
MARKET_START ?=
MARKET_END ?=
MARKET_PROVIDER ?= yfinance
UNIVERSE_NAME ?= watchlist
MARKET_START_ARG := $(if $(MARKET_START),--start $(MARKET_START),)
MARKET_END_ARG := $(if $(MARKET_END),--end $(MARKET_END),)
PREDICT_DB_ARGS ?= --write-db --database-url $(DATABASE_URL)
PYTHON_SYNC_EXTRAS := --extra dev --extra data --extra db --extra dashboard --extra models --extra explainability --extra viz --extra notebooks

.PHONY: python-sync python-sync-gpu docs-format docs-check download-tickers ingest-market-data ingest-watchlist-data predict-latest predict-latest-baseline model-bundles api dashboard stock-dashboard frontend-install frontend-build test-python test-go lint test-all

python-sync:
	$(UV) sync --locked $(PYTHON_SYNC_EXTRAS) --extra deep

python-sync-gpu:
	$(UV) sync --locked $(PYTHON_SYNC_EXTRAS) --extra deep-cu126

docs-format:
	$(MDFORMAT) --wrap no $(MARKDOWN_FILES)

docs-check:
	$(MDFORMAT) --check --wrap no $(MARKDOWN_FILES)
	python3 -m scripts.check_markdown_links

download-tickers:
	$(PYTHON) -m scripts.download_tickers \
		--tickers $(WATCHLIST_TICKERS) \
		--output-dir $(WATCHLIST_DATA_DIR) \
		--interval $(DOWNLOAD_INTERVAL) \
		$(MARKET_START_ARG) \
		$(MARKET_END_ARG)

ingest-market-data:
	$(PYTHON) -m scripts.ingest_market_data \
		--tickers $(WATCHLIST_TICKERS) \
		--interval $(MARKET_INTERVAL) \
		--provider $(MARKET_PROVIDER) \
		--universe-name $(UNIVERSE_NAME) \
		--database-url $(DATABASE_URL) \
		$(MARKET_START_ARG) \
		$(MARKET_END_ARG)

ingest-watchlist-data:
	$(PYTHON) -m scripts.ingest_market_data \
		--watchlist-name $(UNIVERSE_NAME) \
		--interval $(MARKET_INTERVAL) \
		--provider $(MARKET_PROVIDER) \
		--universe-name $(UNIVERSE_NAME) \
		--database-url $(DATABASE_URL) \
		$(MARKET_START_ARG) \
		$(MARKET_END_ARG)

predict-latest:
	$(PYTHON) -m scripts.predict_deep \
		--input $(DATA_INPUT) \
		--model-bundle $(MODEL_BUNDLE) \
		--output $(LATEST_PREDICTIONS) \
		--json-output $(LATEST_WARNINGS) \
		--latest-only

predict-latest-baseline:
	$(PYTHON) -m scripts.predict_latest_baseline \
		--input $(DATA_INPUT) \
		--output $(LATEST_PREDICTIONS) \
		--json-output $(LATEST_WARNINGS) \
		$(PREDICT_DB_ARGS)

model-bundles:
	$(PYTHON) -m scripts.predict_latest_baseline \
		--input $(US_BUNDLE_INPUT) \
		--output $(MODEL_BUNDLE_DIR)/batch/us_predictions.csv \
		--json-output $(MODEL_BUNDLE_DIR)/batch/us_warnings.json \
		--run-id model_bundle_us \
		--model-bundle-root $(MODEL_BUNDLE_DIR) \
		--model-bundle-output us.json
	$(PYTHON) -m scripts.predict_latest_baseline \
		--input $(TAIWAN_BUNDLE_INPUT) \
		--output $(MODEL_BUNDLE_DIR)/batch/taiwan_predictions.csv \
		--json-output $(MODEL_BUNDLE_DIR)/batch/taiwan_warnings.json \
		--run-id model_bundle_taiwan \
		--model-bundle-root $(MODEL_BUNDLE_DIR) \
		--model-bundle-output taiwan.json

api:
	cd services/api-gateway-go && \
		GOCACHE=$(GOCACHE) CGO_ENABLED=0 TSI_API_ADDR=$(API_ADDR) \
		TSI_DATABASE_URL=$(DATABASE_URL) \
		TSI_ON_DEMAND_ANALYSIS_COMMAND="$(ON_DEMAND_ANALYSIS_COMMAND)" \
		TSI_ON_DEMAND_ANALYSIS_WORKDIR="$(ON_DEMAND_ANALYSIS_WORKDIR)" \
		TSI_ON_DEMAND_ANALYSIS_TIMEOUT_SECONDS=$(ON_DEMAND_ANALYSIS_TIMEOUT_SECONDS) \
		TSI_ON_DEMAND_MAX_CONCURRENCY=$(ON_DEMAND_MAX_CONCURRENCY) \
		TSI_MODEL_BUNDLE_DIR="$(abspath $(MODEL_BUNDLE_DIR))" \
		$(GO) run ./cmd/server

dashboard:
	$(STREAMLIT) run dashboard/app.py

frontend-install:
	cd $(FRONTEND_DIR) && $(NPM) ci

stock-dashboard:
	cd $(FRONTEND_DIR) && TSI_DASHBOARD_API_BASE_URL=$(FRONTEND_API_BASE_URL) $(NPM) run dev

frontend-build:
	cd $(FRONTEND_DIR) && $(NPM) run build

test-python:
	$(PYTHON) -m pytest

test-go:
	cd services/api-gateway-go && \
		GOCACHE=$(GOCACHE) CGO_ENABLED=0 $(GO) test ./...

lint:
	$(PYTHON) -m ruff check src tests scripts dashboard

test-all: test-python test-go lint
