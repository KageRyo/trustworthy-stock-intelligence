package watchlist

import (
	"context"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Market string

const (
	MarketAuto Market = "auto"
	MarketUS   Market = "us"
	MarketTWSE Market = "twse"
	MarketTPEX Market = "tpex"
	MarketESB  Market = "emerging"
)

var taiwanLocalTickerPattern = regexp.MustCompile(`^[0-9]{4,6}[A-Z]?$`)

type AddTickerInput struct {
	Ticker string
	Market Market
	Notes  string
}

type Watchlist struct {
	Name      string
	Tickers   []Ticker
	UpdatedAt string
}

type Ticker struct {
	Ticker      string
	QuerySymbol string
	Market      string
	AddedAt     string
	Notes       string
}

type ResolvedTicker struct {
	Ticker      string
	QuerySymbol string
	Market      string
}

type PostgresStore struct {
	pool *pgxpool.Pool
}

func NewPostgresStore(ctx context.Context, databaseURL string) (*PostgresStore, error) {
	if strings.TrimSpace(databaseURL) == "" {
		return nil, errors.New("TSI_DATABASE_URL is required")
	}
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, fmt.Errorf("create postgres pool: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("connect postgres: %w", err)
	}
	return &PostgresStore{pool: pool}, nil
}

func (s *PostgresStore) Close() {
	s.pool.Close()
}

func (s *PostgresStore) List(ctx context.Context, name string) (Watchlist, error) {
	normalizedName := normalizeWatchlistName(name)
	watchlistID, err := s.lookupWatchlist(ctx, normalizedName)
	if errors.Is(err, pgx.ErrNoRows) {
		return Watchlist{
			Name:      normalizedName,
			Tickers:   []Ticker{},
			UpdatedAt: "",
		}, nil
	}
	if err != nil {
		return Watchlist{}, err
	}
	rows, err := s.pool.Query(
		ctx,
		`
		SELECT t.symbol, t.query_symbol, t.market, wt.added_at, wt.notes
		FROM watchlist_tickers wt
		JOIN tickers t ON t.id = wt.ticker_id
		WHERE wt.watchlist_id = $1 AND wt.removed_at IS NULL
		ORDER BY t.symbol
		`,
		watchlistID,
	)
	if err != nil {
		return Watchlist{}, fmt.Errorf("list watchlist tickers: %w", err)
	}
	defer rows.Close()

	tickers := []Ticker{}
	var updatedAt time.Time
	for rows.Next() {
		var ticker Ticker
		var addedAt time.Time
		if err := rows.Scan(
			&ticker.Ticker,
			&ticker.QuerySymbol,
			&ticker.Market,
			&addedAt,
			&ticker.Notes,
		); err != nil {
			return Watchlist{}, fmt.Errorf("scan watchlist ticker: %w", err)
		}
		ticker.AddedAt = addedAt.UTC().Format(time.RFC3339)
		tickers = append(tickers, ticker)
		if addedAt.After(updatedAt) {
			updatedAt = addedAt
		}
	}
	if err := rows.Err(); err != nil {
		return Watchlist{}, fmt.Errorf("iterate watchlist tickers: %w", err)
	}
	return Watchlist{
		Name:      normalizedName,
		Tickers:   tickers,
		UpdatedAt: formatOptionalTime(updatedAt),
	}, nil
}

func (s *PostgresStore) AddTicker(
	ctx context.Context,
	name string,
	input AddTickerInput,
) (Ticker, error) {
	resolved, err := s.resolveTicker(ctx, input.Ticker, input.Market)
	if err != nil {
		return Ticker{}, err
	}
	watchlistID, err := s.ensureWatchlist(ctx, name)
	if err != nil {
		return Ticker{}, err
	}
	tickerID, err := s.upsertTicker(ctx, resolved)
	if err != nil {
		return Ticker{}, err
	}
	var addedAt time.Time
	var notes string
	err = s.pool.QueryRow(
		ctx,
		`
		INSERT INTO watchlist_tickers (watchlist_id, ticker_id, notes)
		VALUES ($1, $2, $3)
		ON CONFLICT (watchlist_id, ticker_id)
		DO UPDATE SET
		    removed_at = NULL,
		    notes = EXCLUDED.notes,
		    added_at = CASE
		        WHEN watchlist_tickers.removed_at IS NULL THEN watchlist_tickers.added_at
		        ELSE now()
		    END
		RETURNING added_at, notes
		`,
		watchlistID,
		tickerID,
		strings.TrimSpace(input.Notes),
	).Scan(&addedAt, &notes)
	if err != nil {
		return Ticker{}, fmt.Errorf("upsert watchlist ticker: %w", err)
	}
	return Ticker{
		Ticker:      resolved.Ticker,
		QuerySymbol: resolved.QuerySymbol,
		Market:      resolved.Market,
		AddedAt:     addedAt.UTC().Format(time.RFC3339),
		Notes:       notes,
	}, nil
}

func (s *PostgresStore) resolveTicker(ctx context.Context, input string, market Market) (ResolvedTicker, error) {
	normalized := strings.ToUpper(strings.TrimSpace(input))
	if market == "" || market == MarketAuto {
		code := strings.TrimSuffix(
			strings.TrimSuffix(
				strings.TrimSuffix(normalized, ".TW"),
				".TWO",
			),
			".EMERGING",
		)
		if isTaiwanLocalTicker(code) {
			existing, ok, err := s.lookupExistingTaiwanTicker(ctx, code)
			if err != nil {
				return ResolvedTicker{}, err
			}
			if ok {
				return existing, nil
			}
		}
	}
	return ResolveTicker(input, market)
}

func (s *PostgresStore) lookupExistingTaiwanTicker(
	ctx context.Context,
	symbol string,
) (ResolvedTicker, bool, error) {
	var resolved ResolvedTicker
	err := s.pool.QueryRow(
		ctx,
		`
		SELECT symbol, query_symbol, market
		FROM tickers
		WHERE upper(symbol) = upper($1)
		  AND market IN ('twse', 'tpex', 'emerging', 'taiwan')
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
		`,
		symbol,
	).Scan(&resolved.Ticker, &resolved.QuerySymbol, &resolved.Market)
	if errors.Is(err, pgx.ErrNoRows) {
		return ResolvedTicker{}, false, nil
	}
	if err != nil {
		return ResolvedTicker{}, false, fmt.Errorf("lookup existing Taiwan ticker: %w", err)
	}
	return resolved, true, nil
}

func (s *PostgresStore) RemoveTicker(ctx context.Context, name string, ticker string) (bool, error) {
	watchlistID, err := s.lookupWatchlist(ctx, normalizeWatchlistName(name))
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	commandTag, err := s.pool.Exec(
		ctx,
		`
		UPDATE watchlist_tickers wt
		SET removed_at = now()
		FROM tickers t
		WHERE wt.ticker_id = t.id
		  AND wt.watchlist_id = $1
		  AND wt.removed_at IS NULL
		  AND upper(t.symbol) = upper($2)
		`,
		watchlistID,
		strings.TrimSpace(ticker),
	)
	if err != nil {
		return false, fmt.Errorf("remove watchlist ticker: %w", err)
	}
	return commandTag.RowsAffected() > 0, nil
}

func ResolveTicker(ticker string, market Market) (ResolvedTicker, error) {
	normalized := strings.ToUpper(strings.TrimSpace(ticker))
	if normalized == "" {
		return ResolvedTicker{}, errors.New("ticker must not be empty")
	}
	switch market {
	case "", MarketAuto:
		if strings.HasSuffix(normalized, ".TW") {
			code := strings.TrimSuffix(normalized, ".TW")
			return ResolvedTicker{Ticker: code, QuerySymbol: code + ".TW", Market: string(MarketTWSE)}, nil
		}
		if strings.HasSuffix(normalized, ".TWO") {
			code := strings.TrimSuffix(normalized, ".TWO")
			return ResolvedTicker{Ticker: code, QuerySymbol: code + ".TWO", Market: string(MarketTPEX)}, nil
		}
		if strings.HasSuffix(normalized, ".EMERGING") {
			code := strings.TrimSuffix(normalized, ".EMERGING")
			return ResolvedTicker{Ticker: code, QuerySymbol: code + ".EMERGING", Market: string(MarketESB)}, nil
		}
		if isTaiwanLocalTicker(normalized) {
			return ResolvedTicker{
				Ticker:      normalized,
				QuerySymbol: normalized + ".TW",
				Market:      string(MarketTWSE),
			}, nil
		}
		symbol := normalizeUSSymbol(normalized)
		return ResolvedTicker{Ticker: symbol, QuerySymbol: symbol, Market: string(MarketUS)}, nil
	case MarketUS:
		symbol := normalizeUSSymbol(normalized)
		return ResolvedTicker{Ticker: symbol, QuerySymbol: symbol, Market: string(MarketUS)}, nil
	case MarketTWSE:
		code := strings.TrimSuffix(normalized, ".TW")
		if !isTaiwanLocalTicker(code) {
			return ResolvedTicker{}, errors.New("twse market requires a Taiwan stock code")
		}
		return ResolvedTicker{Ticker: code, QuerySymbol: code + ".TW", Market: string(MarketTWSE)}, nil
	case MarketTPEX:
		code := strings.TrimSuffix(normalized, ".TWO")
		if !isTaiwanLocalTicker(code) {
			return ResolvedTicker{}, errors.New("tpex market requires a Taiwan stock code")
		}
		return ResolvedTicker{Ticker: code, QuerySymbol: code + ".TWO", Market: string(MarketTPEX)}, nil
	case MarketESB:
		code := strings.TrimSuffix(normalized, ".EMERGING")
		if !isTaiwanLocalTicker(code) {
			return ResolvedTicker{}, errors.New("emerging market requires a Taiwan stock code")
		}
		return ResolvedTicker{Ticker: code, QuerySymbol: code + ".EMERGING", Market: string(MarketESB)}, nil
	default:
		return ResolvedTicker{}, fmt.Errorf("unsupported market: %s", market)
	}
}

func (s *PostgresStore) lookupWatchlist(ctx context.Context, name string) (string, error) {
	var watchlistID string
	err := s.pool.QueryRow(
		ctx,
		`
		SELECT id::text
		FROM watchlists
		WHERE name = $1
		`,
		name,
	).Scan(&watchlistID)
	if err != nil {
		return "", err
	}
	return watchlistID, nil
}

func (s *PostgresStore) ensureWatchlist(ctx context.Context, name string) (string, error) {
	normalized := normalizeWatchlistName(name)
	var watchlistID string
	err := s.pool.QueryRow(
		ctx,
		`
		INSERT INTO watchlists (name, description, is_default)
		VALUES ($1, $2, $3)
		ON CONFLICT (name)
		DO UPDATE SET updated_at = now()
		RETURNING id::text
		`,
		normalized,
		"User-managed stock risk watchlist",
		normalized == "default",
	).Scan(&watchlistID)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", errors.New("watchlist not found")
	}
	if err != nil {
		return "", fmt.Errorf("ensure watchlist: %w", err)
	}
	return watchlistID, nil
}

func (s *PostgresStore) upsertTicker(ctx context.Context, ticker ResolvedTicker) (string, error) {
	var tickerID string
	err := s.pool.QueryRow(
		ctx,
		`
		INSERT INTO tickers (symbol, query_symbol, market)
		VALUES ($1, $2, $3)
		ON CONFLICT (market, symbol)
		DO UPDATE SET query_symbol = EXCLUDED.query_symbol, updated_at = now()
		RETURNING id::text
		`,
		ticker.Ticker,
		ticker.QuerySymbol,
		ticker.Market,
	).Scan(&tickerID)
	if err != nil {
		return "", fmt.Errorf("upsert ticker: %w", err)
	}
	if err := s.mergeStaleUSTickerAlias(ctx, ticker, tickerID); err != nil {
		return "", err
	}
	return tickerID, nil
}

func (s *PostgresStore) mergeStaleUSTickerAlias(
	ctx context.Context,
	ticker ResolvedTicker,
	targetTickerID string,
) error {
	if !shouldMergeStaleUSTickerAlias(ticker) {
		return nil
	}
	rows, err := s.pool.Query(
		ctx,
		`
		SELECT id::text
		FROM tickers
		WHERE upper(symbol) = upper($1)
		  AND market = 'us'
		  AND id::text <> $2
		`,
		ticker.Ticker,
		targetTickerID,
	)
	if err != nil {
		return fmt.Errorf("lookup stale US ticker aliases: %w", err)
	}
	defer rows.Close()

	staleTickerIDs := []string{}
	for rows.Next() {
		var staleTickerID string
		if err := rows.Scan(&staleTickerID); err != nil {
			return fmt.Errorf("scan stale US ticker alias: %w", err)
		}
		staleTickerIDs = append(staleTickerIDs, staleTickerID)
	}
	if err := rows.Err(); err != nil {
		return fmt.Errorf("iterate stale US ticker aliases: %w", err)
	}
	for _, staleTickerID := range staleTickerIDs {
		if err := s.moveTickerReferences(ctx, staleTickerID, targetTickerID); err != nil {
			return err
		}
	}
	return nil
}

func (s *PostgresStore) moveTickerReferences(
	ctx context.Context,
	staleTickerID string,
	targetTickerID string,
) error {
	statements := []string{
		`
		INSERT INTO universe_tickers (universe_id, ticker_id, added_at, removed_at)
		SELECT universe_id, $1, added_at, removed_at
		FROM universe_tickers
		WHERE ticker_id = $2
		ON CONFLICT (universe_id, ticker_id)
		DO UPDATE SET
		    added_at = LEAST(universe_tickers.added_at, EXCLUDED.added_at),
		    removed_at = CASE
		        WHEN universe_tickers.removed_at IS NULL OR EXCLUDED.removed_at IS NULL THEN NULL
		        ELSE LEAST(universe_tickers.removed_at, EXCLUDED.removed_at)
		    END
		`,
		`DELETE FROM universe_tickers WHERE ticker_id = $2 AND $1::text <> ''`,
		`
		INSERT INTO watchlist_tickers (watchlist_id, ticker_id, added_at, removed_at, notes)
		SELECT watchlist_id, $1, added_at, removed_at, notes
		FROM watchlist_tickers
		WHERE ticker_id = $2
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
		    END
		`,
		`DELETE FROM watchlist_tickers WHERE ticker_id = $2 AND $1::text <> ''`,
		`
		INSERT INTO market_bars (
		    ticker_id, ts, interval, provider, open, high, low, close,
		    adj_close, volume, ingestion_run_id, created_at
		)
		SELECT
		    $1, ts, interval, provider, open, high, low, close,
		    adj_close, volume, ingestion_run_id, created_at
		FROM market_bars
		WHERE ticker_id = $2
		ON CONFLICT (ticker_id, interval, ts, provider)
		DO UPDATE SET
		    open = EXCLUDED.open,
		    high = EXCLUDED.high,
		    low = EXCLUDED.low,
		    close = EXCLUDED.close,
		    adj_close = EXCLUDED.adj_close,
		    volume = EXCLUDED.volume,
		    ingestion_run_id = COALESCE(EXCLUDED.ingestion_run_id, market_bars.ingestion_run_id)
		`,
		`DELETE FROM market_bars WHERE ticker_id = $2 AND $1::text <> ''`,
		`
		INSERT INTO warning_records (
		    batch_id, ticker_id, prediction_date, risk_probability,
		    calibrated_risk_probability, calibration_method,
		    uncertainty_score, trust_score, alert_threshold,
		    watch_threshold, warning_level, reason_codes, feature_attributions, created_at
		)
		SELECT
		    batch_id, $1, prediction_date, risk_probability,
		    calibrated_risk_probability, calibration_method,
		    uncertainty_score, trust_score, alert_threshold,
		    watch_threshold, warning_level, reason_codes, feature_attributions, created_at
		FROM warning_records
		WHERE ticker_id = $2
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
		    reason_codes = EXCLUDED.reason_codes,
		    feature_attributions = EXCLUDED.feature_attributions
		`,
		`DELETE FROM warning_records WHERE ticker_id = $2 AND $1::text <> ''`,
		`DELETE FROM tickers WHERE id::text = $2 AND $1::text <> ''`,
	}
	for _, statement := range statements {
		if _, err := s.pool.Exec(ctx, statement, targetTickerID, staleTickerID); err != nil {
			return fmt.Errorf("merge stale US ticker alias: %w", err)
		}
	}
	return nil
}

func shouldMergeStaleUSTickerAlias(ticker ResolvedTicker) bool {
	if !isTaiwanLocalTicker(ticker.Ticker) {
		return false
	}
	switch ticker.Market {
	case string(MarketTWSE), string(MarketTPEX), string(MarketESB), "taiwan":
		return true
	default:
		return false
	}
}

func normalizeWatchlistName(name string) string {
	normalized := strings.ToLower(strings.TrimSpace(name))
	if normalized == "" {
		return "default"
	}
	return normalized
}

func normalizeUSSymbol(ticker string) string {
	return strings.ReplaceAll(ticker, ".", "-")
}

func isTaiwanLocalTicker(value string) bool {
	normalized := strings.TrimSuffix(
		strings.TrimSuffix(
			strings.TrimSuffix(strings.ToUpper(strings.TrimSpace(value)), ".TW"),
			".TWO",
		),
		".EMERGING",
	)
	return taiwanLocalTickerPattern.MatchString(normalized)
}

func formatOptionalTime(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339)
}
