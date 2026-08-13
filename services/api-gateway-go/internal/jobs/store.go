package jobs

import "context"

const SchemaVersion = "prediction_job.v1"

type Status string

const (
	StatusQueued    Status = "queued"
	StatusRunning   Status = "running"
	StatusCompleted Status = "completed"
	StatusFailed    Status = "failed"
	StatusCancelled Status = "cancelled"
)

type FailureCode string

const (
	FailureProviderUnavailable FailureCode = "provider_unavailable"
	FailureInsufficientHistory FailureCode = "insufficient_history"
	FailurePredictionFailed   FailureCode = "prediction_failed"
	FailureStaleData          FailureCode = "stale_data"
	FailureUnsupportedMarket  FailureCode = "unsupported_market"
	FailureUnsupportedInterval FailureCode = "unsupported_interval"
	FailureDatabaseError      FailureCode = "database_error"
	FailureWorkerError        FailureCode = "worker_error"
	FailureUnknown            FailureCode = "unknown"
)

type CreateRequest struct {
	IdempotencyKey string
	Ticker         string
	Market         string
	FeatureInterval string
	MaxAttempts    int
	RequestPayload map[string]any
}

type PredictionJob struct {
	SchemaVersion    string         `json:"schema_version"`
	ID               string         `json:"id"`
	IdempotencyKey   string         `json:"idempotency_key"`
	Ticker           string         `json:"ticker"`
	Market           string         `json:"market"`
	FeatureInterval  string         `json:"feature_interval"`
	Status           Status         `json:"status"`
	AttemptCount     int            `json:"attempt_count"`
	MaxAttempts      int            `json:"max_attempts"`
	AvailableAt      string         `json:"available_at"`
	EnqueuedAt       string         `json:"enqueued_at"`
	StartedAt        string         `json:"started_at,omitempty"`
	CompletedAt      string         `json:"completed_at,omitempty"`
	WorkerID         string         `json:"worker_id,omitempty"`
	LockedAt         string         `json:"locked_at,omitempty"`
	PredictionBatchID string        `json:"prediction_batch_id,omitempty"`
	ResultRunID      string         `json:"result_run_id,omitempty"`
	FailureCode      FailureCode    `json:"failure_code,omitempty"`
	FailureMessage   string         `json:"failure_message,omitempty"`
	RequestPayload   map[string]any `json:"request_payload,omitempty"`
	CreatedAt        string         `json:"created_at"`
	UpdatedAt        string         `json:"updated_at"`
}

type Store interface {
	Enqueue(ctx context.Context, request CreateRequest) (PredictionJob, error)
	Get(ctx context.Context, id string) (PredictionJob, bool, error)
}

type QueueMetrics struct {
	Queued    int
	Running   int
	Completed int
	Failed    int
	Cancelled int
}
