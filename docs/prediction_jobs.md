# Prediction Jobs

Prediction work is persisted in PostgreSQL before a worker runs it. This keeps expensive model
execution out of synchronous API requests and gives operators a typed lifecycle to inspect:

```text
queued -> running -> completed
                 \-> queued (retryable failure)
                 \-> failed (terminal failure or exhausted attempts)
```

## Schema and idempotency

Migration `infra/postgres/init/005_prediction_jobs.sql` creates `prediction_jobs`. Every request has
an `idempotency_key`; enqueueing the same key returns the existing row rather than creating
duplicate work. A completed job records the `prediction_batch_id` and `result_run_id`. The existing
unique `prediction_batches.run_id` constraint makes a worker crash between writing the prediction
and acknowledging the job safe to retry.

## Claiming and failure states

Workers claim the oldest available row with PostgreSQL `FOR UPDATE SKIP LOCKED`. Consequently, two
workers can poll concurrently without processing the same row. Every claim increments
`attempt_count` and records `worker_id`/`locked_at`. A worker must complete or fail only the row it
owns.

Failure codes are stable schema values rather than free-form HTTP errors:

```text
provider_unavailable
insufficient_history
prediction_failed
stale_data
unsupported_market
unsupported_interval
database_error
worker_error
unknown
```

Retryable failures return to `queued` until `max_attempts`; terminal failures become `failed` with
the code and a bounded message. Startup recovery requeues expired worker leases, or marks exhausted
leases failed.

## Local worker

Install the PostgreSQL extra and start the database first:

```bash
python -m pip install -e ".[db]"
docker compose up postgres
```

Run one available job and exit when idle:

```bash
python -m scripts.prediction_worker \
  --database-url "$TSI_DATABASE_URL" \
  --once
```

Enqueue a job locally (repeat the same key to get the existing row):

```bash
python -m scripts.enqueue_prediction_job \
  --database-url "$TSI_DATABASE_URL" \
  --ticker NVDA \
  --idempotency-key local-nvda-2026-08-13
```

Run continuously as a local process or supervised service:

```bash
python -m scripts.prediction_worker \
  --database-url "$TSI_DATABASE_URL" \
  --worker-id "local-worker-1"
```

The current built-in processor consumes persisted `1d` `market_bars` and uses the existing
leakage-aware baseline writer. `1m` and `5m` jobs remain queueable, but fail explicitly with
`unsupported_interval` until an interval-trained model is available. Provider ingestion and model
execution are therefore separate processes, while predictions and warning records stay
PostgreSQL-backed.

Use `Ctrl-C` or the process supervisor's stop signal for graceful shutdown. Claimed rows have a
lease; if a worker exits unexpectedly, a later worker requeues stale rows after `--lease-seconds`
(default 900) and honors the remaining attempt budget.
