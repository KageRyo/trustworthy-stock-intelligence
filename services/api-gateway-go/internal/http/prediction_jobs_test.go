package apihttp

import (
	"context"
	"errors"
	"net/http"
	"testing"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/jobs"
)

type fakePredictionJobStore struct {
	job       jobs.PredictionJob
	found     bool
	enqueueErr error
	getErr    error
	request   jobs.CreateRequest
}

func (s *fakePredictionJobStore) Enqueue(_ context.Context, request jobs.CreateRequest) (jobs.PredictionJob, error) {
	s.request = request
	if s.enqueueErr != nil {
		return jobs.PredictionJob{}, s.enqueueErr
	}
	return s.job, nil
}

func (s *fakePredictionJobStore) Get(_ context.Context, _ string) (jobs.PredictionJob, bool, error) {
	return s.job, s.found, s.getErr
}

func testPredictionJob() jobs.PredictionJob {
	return jobs.PredictionJob{
		SchemaVersion:   jobs.SchemaVersion,
		ID:              "job-1",
		IdempotencyKey:  "request-1",
		Ticker:          "NVDA",
		Market:          "auto",
		FeatureInterval: "1d",
		Status:          jobs.StatusQueued,
		AttemptCount:    0,
		MaxAttempts:     3,
		AvailableAt:     "2026-08-13T02:00:00Z",
		EnqueuedAt:      "2026-08-13T02:00:00Z",
		RequestPayload:  map[string]any{},
		CreatedAt:       "2026-08-13T02:00:00Z",
		UpdatedAt:       "2026-08-13T02:00:00Z",
	}
}

func TestCreatePredictionJobReturnsAcceptedAndTypedJob(t *testing.T) {
	store := &fakePredictionJobStore{job: testPredictionJob()}
	handlers := NewHandlers(mustFileStore(t))
	handlers.SetPredictionJobStore(store)
	router := NewRouter(handlers)

	response := postJSON(t, router, "/api/v1/prediction-jobs", `{
        "schema_version": "prediction_job_request.v1",
        "idempotency_key": "request-1",
        "ticker": " nvda ",
        "market": "auto",
        "feature_interval": "1d"
    }`)

	if response.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202: %s", response.Code, response.Body.String())
	}
	if store.request.Ticker != " nvda " || store.request.IdempotencyKey != "request-1" {
		t.Fatalf("unexpected store request: %+v", store.request)
	}
	if contentType := response.Header().Get("Content-Type"); contentType != "application/json" {
		t.Fatalf("content type = %q, want application/json", contentType)
	}
}

func TestGetPredictionJobReturnsNotFoundAndStoreErrors(t *testing.T) {
	store := &fakePredictionJobStore{found: false}
	handlers := NewHandlers(mustFileStore(t))
	handlers.SetPredictionJobStore(store)
	router := NewRouter(handlers)

	missing := getJSON(t, router, "/api/v1/prediction-jobs/job-missing")
	if missing.Code != http.StatusNotFound {
		t.Fatalf("missing status = %d, want 404", missing.Code)
	}

	store.getErr = errors.New("database unavailable")
	unavailable := getJSON(t, router, "/api/v1/prediction-jobs/job-1")
	if unavailable.Code != http.StatusServiceUnavailable {
		t.Fatalf("unavailable status = %d, want 503", unavailable.Code)
	}
}

func TestPredictionJobHandlerRejectsInvalidRequests(t *testing.T) {
	store := &fakePredictionJobStore{job: testPredictionJob()}
	handlers := NewHandlers(mustFileStore(t))
	handlers.SetPredictionJobStore(store)
	router := NewRouter(handlers)

	invalidJSON := postJSON(t, router, "/api/v1/prediction-jobs", "not-json")
	if invalidJSON.Code != http.StatusBadRequest {
		t.Fatalf("invalid JSON status = %d, want 400", invalidJSON.Code)
	}

	invalidSchema := postJSON(t, router, "/api/v1/prediction-jobs", `{
        "schema_version": "prediction_job.v0",
        "ticker": "NVDA"
    }`)
	if invalidSchema.Code != http.StatusBadRequest {
		t.Fatalf("invalid schema status = %d, want 400", invalidSchema.Code)
	}

	emptyTicker := postJSON(t, router, "/api/v1/prediction-jobs", `{"ticker":"  "}`)
	if emptyTicker.Code != http.StatusBadRequest {
		t.Fatalf("empty ticker status = %d, want 400", emptyTicker.Code)
	}
}

func TestPredictionJobHandlerRequiresStore(t *testing.T) {
	router := testRouter(t)
	response := postJSON(t, router, "/api/v1/prediction-jobs", `{"ticker":"NVDA"}`)
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503", response.Code)
	}
}
