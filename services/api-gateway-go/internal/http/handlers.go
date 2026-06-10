package apihttp

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

type WarningStore interface {
	Batch() warnings.PredictionBatch
	FindTicker(ticker string) (warnings.PredictionRecord, bool)
	Refresh() error
	Status() warnings.StoreStatus
}

type Handlers struct {
	store WarningStore
}

type CurrentModelResponse struct {
	Model       string `json:"model"`
	ModelBundle string `json:"model_bundle"`
	GeneratedAt string `json:"generated_at"`
	RecordCount int    `json:"record_count"`
}

type HealthResponse struct {
	Status         string `json:"status"`
	WarningsLoaded bool   `json:"warnings_loaded"`
	GeneratedAt    string `json:"generated_at"`
	RecordCount    int    `json:"record_count"`
	LastError      string `json:"last_error,omitempty"`
}

func NewHandlers(store WarningStore) *Handlers {
	return &Handlers{store: store}
}

func (h *Handlers) Health(response http.ResponseWriter, _ *http.Request) {
	h.refreshStore()
	status := h.store.Status()
	writeJSON(response, http.StatusOK, HealthResponse{
		Status:         "ok",
		WarningsLoaded: status.WarningsLoaded,
		GeneratedAt:    status.GeneratedAt,
		RecordCount:    status.RecordCount,
		LastError:      status.LastError,
	})
}

func (h *Handlers) LatestWarnings(response http.ResponseWriter, request *http.Request) {
	h.refreshStore()
	batch, err := filterBatch(h.store.Batch(), request)
	if err != nil {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(response, http.StatusOK, batch)
}

func (h *Handlers) TickerWarning(response http.ResponseWriter, request *http.Request) {
	h.refreshStore()
	ticker := strings.TrimPrefix(request.URL.Path, "/api/v1/warnings/")
	ticker = strings.TrimSpace(ticker)
	if ticker == "" || strings.Contains(ticker, "/") {
		writeJSON(response, http.StatusNotFound, map[string]string{"error": "ticker not found"})
		return
	}
	record, ok := h.store.FindTicker(ticker)
	if !ok {
		writeJSON(response, http.StatusNotFound, map[string]string{"error": "ticker not found"})
		return
	}
	writeJSON(response, http.StatusOK, record)
}

func (h *Handlers) CurrentModel(response http.ResponseWriter, _ *http.Request) {
	h.refreshStore()
	batch := h.store.Batch()
	payload := CurrentModelResponse{
		GeneratedAt: batch.GeneratedAt,
		RecordCount: batch.RecordCount,
	}
	if len(batch.Records) > 0 {
		payload.Model = batch.Records[0].Model
		payload.ModelBundle = batch.Records[0].ModelBundle
	}
	writeJSON(response, http.StatusOK, payload)
}

func (h *Handlers) Status(response http.ResponseWriter, _ *http.Request) {
	h.refreshStore()
	writeJSON(response, http.StatusOK, h.store.Status())
}

func (h *Handlers) refreshStore() {
	_ = h.store.Refresh()
}

func writeJSON(response http.ResponseWriter, status int, payload any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(payload)
}

func filterBatch(batch warnings.PredictionBatch, request *http.Request) (warnings.PredictionBatch, error) {
	level := strings.TrimSpace(request.URL.Query().Get("level"))
	limitText := strings.TrimSpace(request.URL.Query().Get("limit"))
	if level != "" && !validWarningLevel(level) {
		return warnings.PredictionBatch{}, httpError("invalid level")
	}
	limit := len(batch.Records)
	if limitText != "" {
		parsed, err := strconv.Atoi(limitText)
		if err != nil || parsed < 0 {
			return warnings.PredictionBatch{}, httpError("invalid limit")
		}
		if parsed < limit {
			limit = parsed
		}
	}

	records := make([]warnings.PredictionRecord, 0, len(batch.Records))
	for _, record := range batch.Records {
		if level != "" && record.WarningLevel != level {
			continue
		}
		records = append(records, record)
		if len(records) == limit {
			break
		}
	}
	batch.Records = records
	batch.RecordCount = len(records)
	return batch, nil
}

func validWarningLevel(level string) bool {
	switch level {
	case "alert", "watch", "abstain", "no_alert":
		return true
	default:
		return false
	}
}

type httpError string

func (e httpError) Error() string {
	return string(e)
}
