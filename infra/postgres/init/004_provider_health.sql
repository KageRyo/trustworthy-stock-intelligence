-- Provider health and coverage observations emitted by market-data ingestion.
-- This table is keyed by provider/market/ticker so the API can expose health
-- state without depending on the latest in-memory downloader request.
CREATE TABLE IF NOT EXISTS provider_health (
    provider TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('us', 'twse', 'tpex', 'emerging', 'taiwan', 'unknown')),
    ticker_symbol TEXT NOT NULL,
    query_symbol TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('healthy', 'degraded', 'unavailable')),
    coverage_status TEXT NOT NULL CHECK (
        coverage_status IN ('available', 'partial', 'unavailable', 'unknown')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    last_latency_ms DOUBLE PRECISION CHECK (last_latency_ms IS NULL OR last_latency_ms >= 0),
    last_error_code TEXT NOT NULL DEFAULT '',
    last_error_message TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, market, ticker_symbol)
);

CREATE INDEX IF NOT EXISTS provider_health_status_idx
    ON provider_health (status, coverage_status);

CREATE INDEX IF NOT EXISTS provider_health_observed_at_idx
    ON provider_health (observed_at DESC);
