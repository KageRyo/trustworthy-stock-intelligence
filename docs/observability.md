# Observability

The Go gateway exposes two distinct probes:

- `GET /health` reports that the process is serving and includes the latest
  warning-store snapshot.
- `GET /readyz` checks PostgreSQL readiness for the production store and
  returns HTTP 503 while a required dependency or warning snapshot is not
  ready.

`GET /metrics` returns a small Prometheus-compatible text surface. It includes
request counters and latency summaries, stale-prediction state, warning-store
reload state, ingestion run counts (when PostgreSQL is available), and
prediction-job queue counts. Labels use route templates (`:ticker`, `:id`, and
`:name`) so public identifiers do not create unbounded metric cardinality.

The gateway and Python ingestion/worker processes emit JSON lines with
`schema_version=tsi_log.v1` to stdout/stderr as appropriate. Events contain
stable service, stage, status, count, and duration fields; database URLs,
tokens, and other credential-like fields are filtered from structured logs.

For a local deployment, inspect the endpoints with:

```bash
curl -i http://127.0.0.1:18080/health
curl -i http://127.0.0.1:18080/readyz
curl http://127.0.0.1:18080/metrics
```
