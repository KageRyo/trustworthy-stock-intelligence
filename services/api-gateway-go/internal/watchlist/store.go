package watchlist

import (
	"context"
	"errors"
	"fmt"
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
)

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
	watchlistID, err := s.ensureWatchlist(ctx, name)
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
		Name:      normalizeWatchlistName(name),
		Tickers:   tickers,
		UpdatedAt: formatOptionalTime(updatedAt),
	}, nil
}

func (s *PostgresStore) AddTicker(
	ctx context.Context,
	name string,
	input AddTickerInput,
) (Ticker, error) {
	resolved, err := ResolveTicker(input.Ticker, input.Market)
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

func (s *PostgresStore) RemoveTicker(ctx context.Context, name string, ticker string) (bool, error) {
	watchlistID, err := s.ensureWatchlist(ctx, name)
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
		if isDigits(normalized) {
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
		if !isDigits(code) {
			return ResolvedTicker{}, errors.New("twse market requires a numeric Taiwan stock code")
		}
		return ResolvedTicker{Ticker: code, QuerySymbol: code + ".TW", Market: string(MarketTWSE)}, nil
	case MarketTPEX:
		code := strings.TrimSuffix(normalized, ".TWO")
		if !isDigits(code) {
			return ResolvedTicker{}, errors.New("tpex market requires a numeric Taiwan stock code")
		}
		return ResolvedTicker{Ticker: code, QuerySymbol: code + ".TWO", Market: string(MarketTPEX)}, nil
	default:
		return ResolvedTicker{}, fmt.Errorf("unsupported market: %s", market)
	}
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
	return tickerID, nil
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

func isDigits(value string) bool {
	if value == "" {
		return false
	}
	for _, char := range value {
		if char < '0' || char > '9' {
			return false
		}
	}
	return true
}

func formatOptionalTime(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339)
}
