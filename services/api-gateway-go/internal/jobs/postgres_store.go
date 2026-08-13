package jobs

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const jobColumns = `
	id, idempotency_key, ticker, market, feature_interval, status,
	attempt_count, max_attempts, available_at, enqueued_at, started_at,
	completed_at, worker_id, locked_at, prediction_batch_id, result_run_id,
	failure_code, failure_message, request_payload, created_at, updated_at
`

type PostgresStore struct {
	pool *pgxpool.Pool
}

func NewPostgresStore(ctx context.Context, databaseURL string) (*PostgresStore, error) {
	if strings.TrimSpace(databaseURL) == "" {
		return nil, errors.New("TSI_DATABASE_URL is required")
	}
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, fmt.Errorf("create postgres prediction job pool: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("connect postgres prediction job store: %w", err)
	}
	return &PostgresStore{pool: pool}, nil
}

func (s *PostgresStore) Close() {
	s.pool.Close()
}

func (s *PostgresStore) Enqueue(ctx context.Context, request CreateRequest) (PredictionJob, error) {
	normalized, err := normalizeCreateRequest(request)
	if err != nil {
		return PredictionJob{}, err
	}
	payload, err := json.Marshal(normalized.RequestPayload)
	if err != nil {
		return PredictionJob{}, fmt.Errorf("encode prediction job payload: %w", err)
	}
	var job PredictionJob
	err = scanJob(s.pool.QueryRow(
		ctx,
		fmt.Sprintf(`
			INSERT INTO prediction_jobs (
				idempotency_key, ticker, market, feature_interval, status,
				max_attempts, request_payload
			)
			VALUES ($1, $2, $3, $4, 'queued', $5, $6::jsonb)
			ON CONFLICT (idempotency_key)
			DO UPDATE SET updated_at = prediction_jobs.updated_at
			RETURNING %s
		`, jobColumns),
		normalized.IdempotencyKey,
		normalized.Ticker,
		normalized.Market,
		normalized.FeatureInterval,
		normalized.MaxAttempts,
		string(payload),
	), &job)
	if err != nil {
		return PredictionJob{}, fmt.Errorf("enqueue prediction job: %w", err)
	}
	return job, nil
}

func (s *PostgresStore) Get(ctx context.Context, id string) (PredictionJob, bool, error) {
	if strings.TrimSpace(id) == "" {
		return PredictionJob{}, false, errors.New("job id must not be empty")
	}
	var job PredictionJob
	err := scanJob(s.pool.QueryRow(
		ctx,
		fmt.Sprintf("SELECT %s FROM prediction_jobs WHERE id = $1", jobColumns),
		strings.TrimSpace(id),
	), &job)
	if errors.Is(err, pgx.ErrNoRows) {
		return PredictionJob{}, false, nil
	}
	if err != nil {
		return PredictionJob{}, false, fmt.Errorf("load prediction job: %w", err)
	}
	return job, true, nil
}

func normalizeCreateRequest(request CreateRequest) (CreateRequest, error) {
	request.Ticker = strings.ToUpper(strings.TrimSpace(request.Ticker))
	if request.Ticker == "" {
		return CreateRequest{}, errors.New("ticker must not be empty")
	}
	request.IdempotencyKey = strings.TrimSpace(request.IdempotencyKey)
	if request.IdempotencyKey == "" {
		request.IdempotencyKey = newIdempotencyKey()
	}
	if request.Market == "" {
		request.Market = "auto"
	}
	if !validMarket(request.Market) {
		return CreateRequest{}, errors.New("market must be one of auto, us, twse, tpex, emerging")
	}
	if request.FeatureInterval == "" {
		request.FeatureInterval = "1d"
	}
	if request.FeatureInterval != "1m" && request.FeatureInterval != "5m" && request.FeatureInterval != "1d" {
		return CreateRequest{}, errors.New("feature_interval must be one of 1m, 5m, 1d")
	}
	if request.MaxAttempts == 0 {
		request.MaxAttempts = 3
	}
	if request.MaxAttempts < 1 || request.MaxAttempts > 8 {
		return CreateRequest{}, errors.New("max_attempts must be between 1 and 8")
	}
	if request.RequestPayload == nil {
		request.RequestPayload = map[string]any{}
	}
	return request, nil
}

func validMarket(market string) bool {
	switch market {
	case "auto", "us", "twse", "tpex", "emerging":
		return true
	default:
		return false
	}
}

func newIdempotencyKey() string {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err == nil {
		return "api-" + hex.EncodeToString(bytes)
	}
	return fmt.Sprintf("api-%d", time.Now().UnixNano())
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanJob(row rowScanner, job *PredictionJob) error {
	var (
		availableAt, enqueuedAt, createdAt, updatedAt time.Time
		startedAt, completedAt, lockedAt             *time.Time
		workerID, predictionBatchID, resultRunID     *string
		failureCode, failureMessage                 string
		payload                                      []byte
	)
	err := row.Scan(
		&job.ID,
		&job.IdempotencyKey,
		&job.Ticker,
		&job.Market,
		&job.FeatureInterval,
		&job.Status,
		&job.AttemptCount,
		&job.MaxAttempts,
		&availableAt,
		&enqueuedAt,
		&startedAt,
		&completedAt,
		&workerID,
		&lockedAt,
		&predictionBatchID,
		&resultRunID,
		&failureCode,
		&failureMessage,
		&payload,
		&createdAt,
		&updatedAt,
	)
	if err != nil {
		return err
	}
	job.SchemaVersion = SchemaVersion
	job.AvailableAt = formatTime(availableAt)
	job.EnqueuedAt = formatTime(enqueuedAt)
	job.StartedAt = formatOptionalTime(startedAt)
	job.CompletedAt = formatOptionalTime(completedAt)
	job.WorkerID = valueOrEmpty(workerID)
	job.LockedAt = formatOptionalTime(lockedAt)
	job.PredictionBatchID = valueOrEmpty(predictionBatchID)
	job.ResultRunID = valueOrEmpty(resultRunID)
	job.FailureCode = FailureCode(failureCode)
	job.FailureMessage = failureMessage
	job.RequestPayload = map[string]any{}
	if len(payload) > 0 {
		if err := json.Unmarshal(payload, &job.RequestPayload); err != nil {
			return fmt.Errorf("decode prediction job payload: %w", err)
		}
	}
	job.CreatedAt = formatTime(createdAt)
	job.UpdatedAt = formatTime(updatedAt)
	return nil
}

func formatTime(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339)
}

func formatOptionalTime(value *time.Time) string {
	if value == nil {
		return ""
	}
	return formatTime(*value)
}

func valueOrEmpty(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}
