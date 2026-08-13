-- PostgreSQL-backed prediction work queue.
-- A unique idempotency key makes retries safe while SKIP LOCKED claims keep
-- multiple workers from processing the same queued row concurrently.
CREATE TABLE IF NOT EXISTS prediction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT NOT NULL UNIQUE,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('auto', 'us', 'twse', 'tpex', 'emerging')),
    feature_interval TEXT NOT NULL CHECK (feature_interval IN ('1m', '5m', '1d')),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    worker_id TEXT,
    locked_at TIMESTAMPTZ,
    prediction_batch_id UUID REFERENCES prediction_batches(id) ON DELETE SET NULL,
    result_run_id TEXT,
    failure_code TEXT NOT NULL DEFAULT '' CHECK (failure_code IN (
        '', 'provider_unavailable', 'insufficient_history', 'prediction_failed',
        'stale_data', 'unsupported_market', 'unsupported_interval',
        'database_error', 'worker_error', 'unknown'
    )),
    failure_message TEXT NOT NULL DEFAULT '',
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS prediction_jobs_claim_idx
    ON prediction_jobs (status, available_at, created_at, id);

CREATE INDEX IF NOT EXISTS prediction_jobs_ticker_idx
    ON prediction_jobs (ticker, created_at DESC);
