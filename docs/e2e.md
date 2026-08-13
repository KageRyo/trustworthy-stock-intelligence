# Watchlist-to-warning end-to-end check

The CI `Watchlist-to-warning E2E` job runs a deterministic, network-free
pipeline against an isolated PostgreSQL service:

```text
fake OHLCV provider
  -> PostgreSQL market_bars
  -> prediction_jobs worker
  -> prediction_batches / warning_records
  -> Go /readyz, /api/v1/analysis/{ticker}, and /api/v1/watchlists/{name}
  -> TypeScript/Zod runtime schema validation
```

The Python test also enqueues a missing-ticker job and verifies the typed
`insufficient_history` terminal failure path. No market-data provider or model
artifact is downloaded in this check. The database is created by the CI
PostgreSQL service and migrations under `infra/postgres/init/` are applied to
it before each run.

To run the Python portion locally, point `TSI_E2E_DATABASE_URL` at a disposable
PostgreSQL database with the `db` extra installed:

```bash
python -m pip install -e ".[dev,db]"
TSI_E2E_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/tsi_e2e" \
  python -m pytest tests/test_e2e_watchlist_warning_pipeline.py -q
```

Set `TSI_E2E_API_BINARY` to a built `services/api-gateway-go/cmd/server`
binary when running without `go run`. Set `TSI_E2E_ANALYSIS_PATH` to have the
test write the analysis response for the frontend Vitest contract check.
