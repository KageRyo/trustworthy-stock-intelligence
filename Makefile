PYTHON ?= python
GO ?= go
STREAMLIT ?= streamlit

DATA_INPUT ?= data/raw/sp100/ohlcv.csv
MODEL_BUNDLE ?= data/artifacts/sp100_transformer_model_bundle
LATEST_PREDICTIONS ?= data/artifacts/latest_predictions.csv
LATEST_WARNINGS ?= data/artifacts/latest_warnings.json
API_ADDR ?= :8080
GOCACHE ?= /tmp/tsi-go-build-cache

.PHONY: predict-latest api dashboard test-python test-go lint test-all

predict-latest:
	$(PYTHON) -m scripts.predict_deep \
		--input $(DATA_INPUT) \
		--model-bundle $(MODEL_BUNDLE) \
		--output $(LATEST_PREDICTIONS) \
		--json-output $(LATEST_WARNINGS) \
		--latest-only

api:
	cd services/api-gateway-go && \
		GOCACHE=$(GOCACHE) CGO_ENABLED=0 TSI_API_ADDR=$(API_ADDR) \
		TSI_WARNINGS_PATH=../../$(LATEST_WARNINGS) $(GO) run ./cmd/server

dashboard:
	$(STREAMLIT) run dashboard/app.py

test-python:
	$(PYTHON) -m pytest

test-go:
	cd services/api-gateway-go && \
		GOCACHE=$(GOCACHE) CGO_ENABLED=0 $(GO) test ./...

lint:
	$(PYTHON) -m ruff check src tests scripts dashboard

test-all: test-python test-go lint
