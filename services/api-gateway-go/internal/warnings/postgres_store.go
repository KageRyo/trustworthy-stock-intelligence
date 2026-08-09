package warnings

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const postgresSource = "postgres"

type PostgresStore struct {
	mu           sync.RWMutex
	pool         *pgxpool.Pool
	batch        PredictionBatch
	byKey        map[string]PredictionRecord
	lastLoadedAt time.Time
	lastError    string
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
	store := &PostgresStore{
		pool:  pool,
		byKey: map[string]PredictionRecord{},
	}
	if err := store.Refresh(); err != nil {
		pool.Close()
		return nil, err
	}
	return store, nil
}

func (s *PostgresStore) Close() {
	s.pool.Close()
}

func (s *PostgresStore) Batch() PredictionBatch {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.batch
}

func (s *PostgresStore) FindTicker(ticker string) (PredictionRecord, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	record, ok := s.byKey[strings.ToUpper(ticker)]
	return record, ok
}

func (s *PostgresStore) History(ticker string, limit int) ([]WarningHistoryRecord, error) {
	if limit < 1 {
		return []WarningHistoryRecord{}, nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	rows, err := s.pool.Query(
		ctx,
		`
		SELECT wr.prediction_date, t.symbol, pb.run_id, pb.data_as_of, pb.generated_at,
		       pb.model, pb.model_bundle, wr.risk_probability,
		       wr.calibrated_risk_probability, wr.calibration_method,
		       wr.uncertainty_score, wr.trust_score, wr.alert_threshold,
		       wr.watch_threshold, wr.warning_level, wr.reason_codes
		FROM warning_records wr
		JOIN prediction_batches pb ON pb.id = wr.batch_id
		JOIN tickers t ON t.id = wr.ticker_id
		WHERE upper(t.symbol) = upper($1)
		ORDER BY wr.prediction_date DESC, pb.generated_at DESC, pb.created_at DESC
		LIMIT $2
		`,
		ticker,
		limit,
	)
	if err != nil {
		return nil, fmt.Errorf("load warning history for %q: %w", ticker, err)
	}
	defer rows.Close()

	history := []WarningHistoryRecord{}
	for rows.Next() {
		var predictionDate time.Time
		var recordDataAsOf time.Time
		var recordGeneratedAt time.Time
		var record PredictionRecord
		if err := rows.Scan(
			&predictionDate,
			&record.Ticker,
			&record.RunID,
			&recordDataAsOf,
			&recordGeneratedAt,
			&record.Model,
			&record.ModelBundle,
			&record.RiskProbability,
			&record.CalibratedRiskProbability,
			&record.CalibrationMethod,
			&record.UncertaintyScore,
			&record.TrustScore,
			&record.AlertThreshold,
			&record.WatchThreshold,
			&record.WarningLevel,
			&record.ReasonCodes,
		); err != nil {
			return nil, fmt.Errorf("scan warning history for %q: %w", ticker, err)
		}
		record.Date = formatDataTime(predictionDate)
		record.DataAsOf = formatDataTime(recordDataAsOf)
		record.GeneratedAt = recordGeneratedAt.UTC().Format(time.RFC3339)
		history = append(history, HistoryRecordFromPrediction(record))
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate warning history for %q: %w", ticker, err)
	}

	for left, right := 0, len(history)-1; left < right; left, right = left+1, right-1 {
		history[left], history[right] = history[right], history[left]
	}
	return history, nil
}

func (s *PostgresStore) Refresh() error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	batch, byKey, err := s.loadLatestBatch(ctx)
	if err != nil {
		s.setLastError(err)
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.batch = batch
	s.byKey = byKey
	s.lastLoadedAt = time.Now().UTC()
	s.lastError = ""
	return nil
}

func (s *PostgresStore) Status() StoreStatus {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return StoreStatus{
		WarningsPath:   postgresSource,
		WarningsLoaded: len(s.batch.Records) > 0,
		SchemaVersion:  s.batch.SchemaVersion,
		RunID:          s.batch.RunID,
		DataAsOf:       s.batch.DataAsOf,
		GeneratedAt:    s.batch.GeneratedAt,
		RecordCount:    s.batch.RecordCount,
		LastLoadedAt:   formatTime(s.lastLoadedAt),
		FileModifiedAt: "",
		LastError:      s.lastError,
	}
}

func (s *PostgresStore) loadLatestBatch(
	ctx context.Context,
) (PredictionBatch, map[string]PredictionRecord, error) {
	var schemaVersion string
	var runID string
	var dataAsOf time.Time
	var generatedAt time.Time
	err := s.pool.QueryRow(
		ctx,
		`
		SELECT schema_version, run_id, data_as_of, generated_at
		FROM prediction_batches
		ORDER BY generated_at DESC, created_at DESC
		LIMIT 1
		`,
	).Scan(&schemaVersion, &runID, &dataAsOf, &generatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return emptyBatch(), map[string]PredictionRecord{}, nil
	}
	if err != nil {
		return PredictionBatch{}, nil, fmt.Errorf("load latest prediction batch metadata: %w", err)
	}

	rows, err := s.pool.Query(
		ctx,
		`
		SELECT prediction_date, symbol, run_id, data_as_of, generated_at,
		       model, model_bundle, risk_probability,
		       calibrated_risk_probability, calibration_method,
		       uncertainty_score, trust_score, alert_threshold,
		       watch_threshold, warning_level, reason_codes
		FROM (
			SELECT DISTINCT ON (t.symbol)
			       wr.prediction_date, t.symbol, pb.run_id, pb.data_as_of,
			       pb.generated_at, pb.model, pb.model_bundle, wr.risk_probability,
			       wr.calibrated_risk_probability, wr.calibration_method,
			       wr.uncertainty_score, wr.trust_score, wr.alert_threshold,
			       wr.watch_threshold, wr.warning_level, wr.reason_codes,
			       pb.created_at
			FROM warning_records wr
			JOIN prediction_batches pb ON pb.id = wr.batch_id
			JOIN tickers t ON t.id = wr.ticker_id
			ORDER BY t.symbol, pb.generated_at DESC, wr.prediction_date DESC, pb.created_at DESC
		) latest_per_ticker
		ORDER BY symbol
		`,
	)
	if err != nil {
		return PredictionBatch{}, nil, fmt.Errorf("load latest warning records by ticker: %w", err)
	}
	defer rows.Close()

	records := []PredictionRecord{}
	byKey := map[string]PredictionRecord{}
	for rows.Next() {
		var predictionDate time.Time
		var recordDataAsOf time.Time
		var recordGeneratedAt time.Time
		var record PredictionRecord
		if err := rows.Scan(
			&predictionDate,
			&record.Ticker,
			&record.RunID,
			&recordDataAsOf,
			&recordGeneratedAt,
			&record.Model,
			&record.ModelBundle,
			&record.RiskProbability,
			&record.CalibratedRiskProbability,
			&record.CalibrationMethod,
			&record.UncertaintyScore,
			&record.TrustScore,
			&record.AlertThreshold,
			&record.WatchThreshold,
			&record.WarningLevel,
			&record.ReasonCodes,
		); err != nil {
			return PredictionBatch{}, nil, fmt.Errorf("scan warning record: %w", err)
		}
		record.Date = formatDataTime(predictionDate)
		record.DataAsOf = formatDataTime(recordDataAsOf)
		record.GeneratedAt = recordGeneratedAt.UTC().Format(time.RFC3339)
		records = append(records, record)
		byKey[strings.ToUpper(record.Ticker)] = record
	}
	if err := rows.Err(); err != nil {
		return PredictionBatch{}, nil, fmt.Errorf("iterate warning records: %w", err)
	}

	batch := PredictionBatch{
		SchemaVersion: schemaVersion,
		RunID:         runID,
		DataAsOf:      formatDataTime(dataAsOf),
		GeneratedAt:   generatedAt.UTC().Format(time.RFC3339),
		RecordCount:   len(records),
		Records:       records,
	}
	return batch, byKey, nil
}

func emptyBatch() PredictionBatch {
	return PredictionBatch{
		SchemaVersion: "v1",
		RunID:         "none",
		DataAsOf:      "",
		GeneratedAt:   "",
		RecordCount:   0,
		Records:       []PredictionRecord{},
	}
}

func formatDataTime(value time.Time) string {
	utc := value.UTC()
	if utc.Hour() == 0 && utc.Minute() == 0 && utc.Second() == 0 && utc.Nanosecond() == 0 {
		return utc.Format("2006-01-02")
	}
	return utc.Format(time.RFC3339)
}

func (s *PostgresStore) setLastError(err error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastError = err.Error()
}
