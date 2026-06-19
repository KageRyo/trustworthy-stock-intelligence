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
	var batchID string
	var schemaVersion string
	var runID string
	var dataAsOf time.Time
	var generatedAt time.Time
	var model string
	var modelBundle string
	var recordCount int
	err := s.pool.QueryRow(
		ctx,
		`
		SELECT id::text, schema_version, run_id, data_as_of, generated_at,
		       model, model_bundle, record_count
		FROM prediction_batches
		ORDER BY generated_at DESC, created_at DESC
		LIMIT 1
		`,
	).Scan(&batchID, &schemaVersion, &runID, &dataAsOf, &generatedAt, &model, &modelBundle, &recordCount)
	if errors.Is(err, pgx.ErrNoRows) {
		return emptyBatch(), map[string]PredictionRecord{}, nil
	}
	if err != nil {
		return PredictionBatch{}, nil, fmt.Errorf("load latest prediction batch: %w", err)
	}

	rows, err := s.pool.Query(
		ctx,
		`
		SELECT wr.prediction_date, t.symbol, wr.risk_probability,
		       wr.calibrated_risk_probability, wr.calibration_method,
		       wr.uncertainty_score, wr.trust_score, wr.alert_threshold,
		       wr.watch_threshold, wr.warning_level, wr.reason_codes
		FROM warning_records wr
		JOIN tickers t ON t.id = wr.ticker_id
		WHERE wr.batch_id = $1
		ORDER BY t.symbol
		`,
		batchID,
	)
	if err != nil {
		return PredictionBatch{}, nil, fmt.Errorf("load warning records: %w", err)
	}
	defer rows.Close()

	records := []PredictionRecord{}
	byKey := map[string]PredictionRecord{}
	for rows.Next() {
		var predictionDate time.Time
		var record PredictionRecord
		if err := rows.Scan(
			&predictionDate,
			&record.Ticker,
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
		record.Model = model
		record.ModelBundle = modelBundle
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
	if recordCount != len(records) {
		batch.RecordCount = len(records)
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
