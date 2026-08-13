# TSI Go API Gateway

Version: `0.3.2`

REST API for serving trustworthy stock warning outputs and user-managed
watchlists generated/stored by the Python ML core and PostgreSQL.

## Data Source

The service reads PostgreSQL tables populated by prediction and ingestion jobs:

```text
prediction_batches
warning_records
prediction_jobs
watchlists
watchlist_tickers
```

Configure PostgreSQL with:

```bash
export TSI_DATABASE_URL="postgresql://<database-user>:<local-password>@localhost:55432/<database-name>"
```

`TSI_DATABASE_URL` is required. The default address is `:8080`. Override it
with `TSI_API_ADDR`, or `PORT` when `TSI_API_ADDR` is not set.

Browser clients are controlled by `TSI_CORS_ALLOWED_ORIGINS`, a comma-separated
list of exact origins. The local default is `*`; shared deployments should use
explicit dashboard origins.

Example for a shared local dashboard:

```bash
export TSI_CORS_ALLOWED_ORIGINS="http://<dashboard-host>:5175,http://localhost:5175"
```

For local interactive ticker search, set:

```bash
export TSI_ON_DEMAND_ANALYSIS_COMMAND="python -m scripts.analyze_ticker_on_demand"
export TSI_ON_DEMAND_ANALYSIS_WORKDIR="/absolute/path/to/trustworthy-stock-intelligence"
export TSI_ON_DEMAND_ANALYSIS_TIMEOUT_SECONDS=120
```

When enabled, `/api/v1/analysis/{ticker}` can delegate a missing ticker to the
Python ML core, write the generated warning record to PostgreSQL, refresh the
store, and return a typed analysis response.

Supported ticker normalization includes US symbols, Taiwan numeric codes,
Taiwan alphanumeric local codes, explicit `.TW`, `.TWO`, and `.EMERGING`
suffixes, and DB-preserved market metadata from previous provider ingestion.

## Run

From the repository root:

```bash
cd services/api-gateway-go
TSI_DATABASE_URL="postgresql://<database-user>:<local-password>@localhost:55432/<database-name>" \
  CGO_ENABLED=0 go run ./cmd/server
```

If Go is installed through conda, activate the environment first:

```bash
conda activate stock
which go
go version
```

## Docker

Build the API image from the service directory:

```bash
docker build -t tsi-api-gateway services/api-gateway-go
```

Run it with a PostgreSQL URL:

```bash
docker run --rm -p 8080:8080 \
  -e TSI_DATABASE_URL="postgresql://<database-user>:<local-password>@host.docker.internal:55432/<database-name>" \
  tsi-api-gateway
```

## Endpoints

```text
GET /health
GET /readyz
GET /metrics
GET /openapi.yaml
GET /swagger/
GET /api/v1/status
GET /api/v1/providers/health
POST /api/v1/prediction-jobs
GET /api/v1/prediction-jobs/{id}
GET /api/v1/tickers
GET /api/v1/watchlists/{name}
POST /api/v1/watchlists/{name}/tickers
DELETE /api/v1/watchlists/{name}/tickers/{ticker}
GET /api/v1/analysis/{ticker}
GET /api/v1/analysis/{ticker}/history
GET /api/v1/analysis/{ticker}/transitions
GET /api/v1/warnings/latest
GET /api/v1/warnings/latest?level=watch&limit=20
GET /api/v1/warnings/latest?level=alert&sort=trust_score&order=desc&limit=20
GET /api/v1/warnings/{ticker}
GET /api/v1/models/current
```

The service requires PostgreSQL through `TSI_DATABASE_URL`. It does not call
Python by default. If `TSI_ON_DEMAND_ANALYSIS_COMMAND` is configured, missing
ticker analysis is delegated to that Python command before the handler returns.

`/api/v1/analysis/{ticker}` returns a typed dashboard analysis schema built from
the latest warning record. See `docs/api/analysis_api.md`.

`/api/v1/analysis/{ticker}/transitions` returns deterministic warning-change
events such as `new_alert`, `upgraded`, `resolved`, and `low_trust_warning`.
Repeated identical snapshots are omitted. See the root
`docs/warning_transitions.md` for semantics.

`/api/v1/tickers` returns the symbols that currently have PostgreSQL warning
records. It is not a complete market universe endpoint.

`/api/v1/watchlists/{name}` and child ticker endpoints manage DB-backed
watchlists. A ticker may be present in a watchlist before a latest warning exists
for it.

Swagger UI is served from `/swagger/`, with the OpenAPI YAML at
`/openapi.yaml`.

The latest warning batch is loaded from PostgreSQL `prediction_batches` and
`warning_records`. Missing `TSI_DATABASE_URL` or an unreachable database is a
startup error.

Prediction work is queued in PostgreSQL with an idempotency key and returns
`202 Accepted`; a separate Python worker claims the job and writes the linked
prediction batch and warning records. Query `GET /api/v1/prediction-jobs/{id}`
for `queued`, `running`, `completed`, or typed `failed` state. See the root
`docs/prediction_jobs.md` for worker startup and retry semantics.

The lightweight Docker image contains only the Go API binary. Use the local
`make api` workflow for on-demand Python analysis, or build a combined
runtime/worker image before enabling `TSI_ON_DEMAND_ANALYSIS_COMMAND` in a
container.

## Test

```bash
CGO_ENABLED=0 go test ./...
```
