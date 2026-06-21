DROP TABLE IF EXISTS stale_taiwan_us_ticker_aliases;

CREATE TEMP TABLE stale_taiwan_us_ticker_aliases (
    stale_ticker_id UUID PRIMARY KEY,
    target_ticker_id UUID NOT NULL
);

WITH stale AS (
    SELECT
        id AS stale_ticker_id,
        upper(symbol) AS symbol_key,
        symbol,
        name,
        currency,
        exchange,
        is_active
    FROM tickers
    WHERE market = 'us'
      AND upper(symbol) ~ '^[0-9]{4,6}[A-Z]$'
),
inserted AS (
    INSERT INTO tickers (symbol, query_symbol, market, name, currency, exchange, is_active)
    SELECT
        stale.symbol,
        stale.symbol_key || '.TW',
        'twse',
        stale.name,
        stale.currency,
        stale.exchange,
        stale.is_active
    FROM stale
    WHERE NOT EXISTS (
        SELECT 1
        FROM tickers target
        WHERE upper(target.symbol) = stale.symbol_key
          AND target.market IN ('twse', 'tpex', 'emerging', 'taiwan')
    )
    ON CONFLICT (market, symbol)
    DO UPDATE SET
        query_symbol = EXCLUDED.query_symbol,
        updated_at = now()
    RETURNING id AS target_ticker_id, upper(symbol) AS symbol_key
)
INSERT INTO stale_taiwan_us_ticker_aliases (stale_ticker_id, target_ticker_id)
SELECT
    stale.stale_ticker_id,
    COALESCE(existing.target_ticker_id, inserted.target_ticker_id) AS target_ticker_id
FROM stale
LEFT JOIN LATERAL (
    SELECT id AS target_ticker_id
    FROM tickers target
    WHERE upper(target.symbol) = stale.symbol_key
      AND target.market IN ('twse', 'tpex', 'emerging', 'taiwan')
    ORDER BY
      updated_at DESC,
      CASE market
        WHEN 'twse' THEN 1
        WHEN 'tpex' THEN 2
        WHEN 'emerging' THEN 3
        WHEN 'taiwan' THEN 4
        ELSE 5
      END
    LIMIT 1
) existing ON true
LEFT JOIN inserted ON inserted.symbol_key = stale.symbol_key
WHERE COALESCE(existing.target_ticker_id, inserted.target_ticker_id) IS NOT NULL;

INSERT INTO universe_tickers (universe_id, ticker_id, added_at, removed_at)
SELECT
    ut.universe_id,
    aliases.target_ticker_id,
    ut.added_at,
    ut.removed_at
FROM universe_tickers ut
JOIN stale_taiwan_us_ticker_aliases aliases ON aliases.stale_ticker_id = ut.ticker_id
ON CONFLICT (universe_id, ticker_id)
DO UPDATE SET
    added_at = LEAST(universe_tickers.added_at, EXCLUDED.added_at),
    removed_at = CASE
        WHEN universe_tickers.removed_at IS NULL OR EXCLUDED.removed_at IS NULL THEN NULL
        ELSE LEAST(universe_tickers.removed_at, EXCLUDED.removed_at)
    END;

INSERT INTO watchlist_tickers (watchlist_id, ticker_id, added_at, removed_at, notes)
SELECT
    wt.watchlist_id,
    aliases.target_ticker_id,
    wt.added_at,
    wt.removed_at,
    wt.notes
FROM watchlist_tickers wt
JOIN stale_taiwan_us_ticker_aliases aliases ON aliases.stale_ticker_id = wt.ticker_id
ON CONFLICT (watchlist_id, ticker_id)
DO UPDATE SET
    added_at = LEAST(watchlist_tickers.added_at, EXCLUDED.added_at),
    removed_at = CASE
        WHEN watchlist_tickers.removed_at IS NULL OR EXCLUDED.removed_at IS NULL THEN NULL
        ELSE LEAST(watchlist_tickers.removed_at, EXCLUDED.removed_at)
    END,
    notes = CASE
        WHEN watchlist_tickers.notes = '' THEN EXCLUDED.notes
        ELSE watchlist_tickers.notes
    END;

INSERT INTO market_bars (
    ticker_id, ts, interval, provider, open, high, low, close,
    adj_close, volume, ingestion_run_id, created_at
)
SELECT
    aliases.target_ticker_id,
    mb.ts,
    mb.interval,
    mb.provider,
    mb.open,
    mb.high,
    mb.low,
    mb.close,
    mb.adj_close,
    mb.volume,
    mb.ingestion_run_id,
    mb.created_at
FROM market_bars mb
JOIN stale_taiwan_us_ticker_aliases aliases ON aliases.stale_ticker_id = mb.ticker_id
ON CONFLICT (ticker_id, interval, ts, provider)
DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    adj_close = EXCLUDED.adj_close,
    volume = EXCLUDED.volume,
    ingestion_run_id = COALESCE(EXCLUDED.ingestion_run_id, market_bars.ingestion_run_id);

INSERT INTO warning_records (
    batch_id, ticker_id, prediction_date, risk_probability,
    calibrated_risk_probability, calibration_method,
    uncertainty_score, trust_score, alert_threshold,
    watch_threshold, warning_level, reason_codes, created_at
)
SELECT
    wr.batch_id,
    aliases.target_ticker_id,
    wr.prediction_date,
    wr.risk_probability,
    wr.calibrated_risk_probability,
    wr.calibration_method,
    wr.uncertainty_score,
    wr.trust_score,
    wr.alert_threshold,
    wr.watch_threshold,
    wr.warning_level,
    wr.reason_codes,
    wr.created_at
FROM warning_records wr
JOIN stale_taiwan_us_ticker_aliases aliases ON aliases.stale_ticker_id = wr.ticker_id
ON CONFLICT (batch_id, ticker_id)
DO UPDATE SET
    prediction_date = EXCLUDED.prediction_date,
    risk_probability = EXCLUDED.risk_probability,
    calibrated_risk_probability = EXCLUDED.calibrated_risk_probability,
    calibration_method = EXCLUDED.calibration_method,
    uncertainty_score = EXCLUDED.uncertainty_score,
    trust_score = EXCLUDED.trust_score,
    alert_threshold = EXCLUDED.alert_threshold,
    watch_threshold = EXCLUDED.watch_threshold,
    warning_level = EXCLUDED.warning_level,
    reason_codes = EXCLUDED.reason_codes;

DELETE FROM universe_tickers
WHERE ticker_id IN (SELECT stale_ticker_id FROM stale_taiwan_us_ticker_aliases);

DELETE FROM watchlist_tickers
WHERE ticker_id IN (SELECT stale_ticker_id FROM stale_taiwan_us_ticker_aliases);

DELETE FROM market_bars
WHERE ticker_id IN (SELECT stale_ticker_id FROM stale_taiwan_us_ticker_aliases);

DELETE FROM warning_records
WHERE ticker_id IN (SELECT stale_ticker_id FROM stale_taiwan_us_ticker_aliases);

DELETE FROM tickers
WHERE id IN (SELECT stale_ticker_id FROM stale_taiwan_us_ticker_aliases);

DROP TABLE stale_taiwan_us_ticker_aliases;
