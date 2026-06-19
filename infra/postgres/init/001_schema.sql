CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS universes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tickers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    query_symbol TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('us', 'twse', 'tpex', 'taiwan', 'unknown')),
    name TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT '',
    exchange TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (market, symbol)
);

CREATE TABLE IF NOT EXISTS universe_tickers (
    universe_id UUID NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
    ticker_id UUID NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at TIMESTAMPTZ,
    PRIMARY KEY (universe_id, ticker_id)
);

CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS watchlists_single_default_idx
    ON watchlists (is_default)
    WHERE is_default;

CREATE TABLE IF NOT EXISTS watchlist_tickers (
    watchlist_id UUID NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    ticker_id UUID NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (watchlist_id, ticker_id)
);

CREATE INDEX IF NOT EXISTS watchlist_tickers_active_idx
    ON watchlist_tickers (watchlist_id, removed_at);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    universe_name TEXT NOT NULL DEFAULT '',
    interval TEXT NOT NULL CHECK (interval IN ('1m', '5m', '1d')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    requested_symbols TEXT[] NOT NULL DEFAULT '{}',
    downloaded_symbols TEXT[] NOT NULL DEFAULT '{}',
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS market_bars (
    ticker_id UUID NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    interval TEXT NOT NULL CHECK (interval IN ('1m', '5m', '1d')),
    provider TEXT NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    adj_close NUMERIC,
    volume NUMERIC NOT NULL,
    ingestion_run_id UUID REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker_id, interval, ts, provider)
);

CREATE INDEX IF NOT EXISTS market_bars_interval_ts_idx
    ON market_bars (interval, ts DESC);

CREATE INDEX IF NOT EXISTS market_bars_ticker_interval_ts_idx
    ON market_bars (ticker_id, interval, ts DESC);

CREATE TABLE IF NOT EXISTS prediction_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_version TEXT NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    data_as_of TIMESTAMPTZ NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    model TEXT NOT NULL,
    model_bundle TEXT NOT NULL,
    feature_interval TEXT NOT NULL CHECK (feature_interval IN ('1m', '5m', '1d')),
    record_count INTEGER NOT NULL CHECK (record_count >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS warning_records (
    batch_id UUID NOT NULL REFERENCES prediction_batches(id) ON DELETE CASCADE,
    ticker_id UUID NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    prediction_date TIMESTAMPTZ NOT NULL,
    risk_probability DOUBLE PRECISION NOT NULL CHECK (risk_probability >= 0 AND risk_probability <= 1),
    calibrated_risk_probability DOUBLE PRECISION NOT NULL CHECK (
        calibrated_risk_probability >= 0 AND calibrated_risk_probability <= 1
    ),
    calibration_method TEXT NOT NULL,
    uncertainty_score DOUBLE PRECISION NOT NULL CHECK (uncertainty_score >= 0 AND uncertainty_score <= 1),
    trust_score DOUBLE PRECISION NOT NULL CHECK (trust_score >= 0 AND trust_score <= 1),
    alert_threshold DOUBLE PRECISION NOT NULL CHECK (alert_threshold >= 0 AND alert_threshold <= 1),
    watch_threshold DOUBLE PRECISION NOT NULL CHECK (watch_threshold >= 0 AND watch_threshold <= 1),
    warning_level TEXT NOT NULL CHECK (warning_level IN ('alert', 'watch', 'abstain', 'no_alert')),
    reason_codes TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, ticker_id)
);

CREATE INDEX IF NOT EXISTS warning_records_level_idx
    ON warning_records (warning_level);

CREATE INDEX IF NOT EXISTS warning_records_ticker_date_idx
    ON warning_records (ticker_id, prediction_date DESC);
