ALTER TABLE tickers
    DROP CONSTRAINT IF EXISTS tickers_market_check;

ALTER TABLE tickers
    ADD CONSTRAINT tickers_market_check
    CHECK (market IN ('us', 'twse', 'tpex', 'emerging', 'taiwan', 'unknown'));
