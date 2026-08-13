package apihttp

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/jobs"
)

const predictionJobRequestSchemaVersion = "prediction_job_request.v1"

type PredictionJobCreateRequest struct {
	SchemaVersion   string         `json:"schema_version"`
	IdempotencyKey  string         `json:"idempotency_key,omitempty"`
	Ticker          string         `json:"ticker"`
	Market          string         `json:"market,omitempty"`
	FeatureInterval string         `json:"feature_interval,omitempty"`
	MaxAttempts     int            `json:"max_attempts,omitempty"`
	RequestPayload  map[string]any `json:"request_payload,omitempty"`
}

type PredictionJobResponse struct {
	SchemaVersion string             `json:"schema_version"`
	Job           jobs.PredictionJob `json:"job"`
}

func (h *Handlers) CreatePredictionJob(response http.ResponseWriter, request *http.Request) {
	if h.predictionJobs == nil {
		writeError(response, http.StatusServiceUnavailable, newHTTPError(
			"prediction_job_store_unavailable",
			"prediction job store is unavailable",
		))
		return
	}
	var payload PredictionJobCreateRequest
	decoder := json.NewDecoder(request.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&payload); err != nil {
		writeError(response, http.StatusBadRequest, newHTTPError("invalid_request", "invalid request JSON"))
		return
	}
	if payload.SchemaVersion != "" && payload.SchemaVersion != predictionJobRequestSchemaVersion {
		writeError(response, http.StatusBadRequest, newHTTPError(
			"invalid_schema_version",
			"schema_version must be prediction_job_request.v1",
		))
		return
	}
	if strings.TrimSpace(payload.Ticker) == "" {
		writeError(response, http.StatusBadRequest, newHTTPError("invalid_ticker", "ticker must not be empty"))
		return
	}
	job, err := h.predictionJobs.Enqueue(request.Context(), jobs.CreateRequest{
		IdempotencyKey:   payload.IdempotencyKey,
		Ticker:           payload.Ticker,
		Market:           payload.Market,
		FeatureInterval:  payload.FeatureInterval,
		MaxAttempts:      payload.MaxAttempts,
		RequestPayload:   payload.RequestPayload,
	})
	if err != nil {
		message := err.Error()
		code := "prediction_job_unavailable"
		status := http.StatusServiceUnavailable
		if strings.Contains(message, "ticker") || strings.Contains(message, "market") ||
			strings.Contains(message, "feature_interval") || strings.Contains(message, "max_attempts") {
			code = "invalid_prediction_job"
			status = http.StatusBadRequest
		}
		writeError(response, status, newHTTPError(code, message))
		return
	}
	writeJSON(response, http.StatusAccepted, PredictionJobResponse{
		SchemaVersion: jobs.SchemaVersion,
		Job:           job,
	})
}

func (h *Handlers) GetPredictionJob(response http.ResponseWriter, request *http.Request) {
	if h.predictionJobs == nil {
		writeError(response, http.StatusServiceUnavailable, newHTTPError(
			"prediction_job_store_unavailable",
			"prediction job store is unavailable",
		))
		return
	}
	id := strings.TrimSpace(request.PathValue("id"))
	if id == "" || strings.Contains(id, "/") {
		writeError(response, http.StatusBadRequest, newHTTPError("invalid_job_id", "job id must not be empty"))
		return
	}
	job, found, err := h.predictionJobs.Get(request.Context(), id)
	if err != nil {
		writeError(response, http.StatusServiceUnavailable, newHTTPError(
			"prediction_job_unavailable",
			"prediction job status could not be read",
		))
		return
	}
	if !found {
		writeError(response, http.StatusNotFound, newHTTPError("prediction_job_not_found", "prediction job not found"))
		return
	}
	writeJSON(response, http.StatusOK, PredictionJobResponse{
		SchemaVersion: jobs.SchemaVersion,
		Job:           job,
	})
}
