PYTHON ?= python
GO ?= go
STREAMLIT ?= streamlit
NPM ?= npm

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
DATABASE_URL ?= postgresql://tsi:tsi_local_password@localhost:55432/tsi
DOWNLOAD_INTERVAL ?= 1d
MARKET_INTERVAL ?= 5m
MARKET_START ?=
MARKET_END ?=
MARKET_PROVIDER ?= yfinance
UNIVERSE_NAME ?= watchlist
MARKET_START_ARG := $(if $(MARKET_START),--start $(MARKET_START),)
MARKET_END_ARG := $(if $(MARKET_END),--end $(MARKET_END),)
PREDICT_DB_ARGS ?= --write-db --database-url $(DATABASE_URL)

.PHONY: download-tickers ingest-market-data ingest-watchlist-data predict-latest predict-latest-baseline api dashboard stock-dashboard frontend-install frontend-build test-python test-go lint test-all

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

api:
	cd services/api-gateway-go && \
		GOCACHE=$(GOCACHE) CGO_ENABLED=0 TSI_API_ADDR=$(API_ADDR) \
		TSI_DATABASE_URL=$(DATABASE_URL) $(GO) run ./cmd/server

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
