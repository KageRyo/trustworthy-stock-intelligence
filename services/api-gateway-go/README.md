# TSI Go API Gateway

REST API for serving trustworthy stock warning outputs and user-managed
watchlists generated/stored by the Python ML core and PostgreSQL.

## Data Source

The service reads PostgreSQL tables populated by prediction and ingestion jobs:

```text
prediction_batches
warning_records
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

The service requires PostgreSQL through `TSI_DATABASE_URL`. It does not call
Python or run background inference jobs in request handlers.

`/api/v1/analysis/{ticker}` returns a typed dashboard analysis schema built from
the latest warning record. See `docs/api/analysis_api.md`.

`/api/v1/tickers` returns the symbols present in the loaded warning batch. It is
not a complete market universe endpoint.

`/api/v1/watchlists/{name}` and child ticker endpoints manage DB-backed
watchlists. A ticker may be present in a watchlist before a latest warning exists
for it.

Swagger UI is served from `/swagger/`, with the OpenAPI YAML at
`/openapi.yaml`.

The latest warning batch is loaded from PostgreSQL `prediction_batches` and
`warning_records`. Missing `TSI_DATABASE_URL` or an unreachable database is a
startup error.

## Test

```bash
CGO_ENABLED=0 go test ./...
```
