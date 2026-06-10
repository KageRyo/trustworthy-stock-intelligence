package apihttp

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

type WarningStore interface {
	Batch() warnings.PredictionBatch
	FindTicker(ticker string) (warnings.PredictionRecord, bool)
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

func NewHandlers(store WarningStore) *Handlers {
	return &Handlers{store: store}
}

func (h *Handlers) Health(response http.ResponseWriter, _ *http.Request) {
	writeJSON(response, http.StatusOK, map[string]string{"status": "ok"})
}

func (h *Handlers) LatestWarnings(response http.ResponseWriter, _ *http.Request) {
	writeJSON(response, http.StatusOK, h.store.Batch())
}

func (h *Handlers) TickerWarning(response http.ResponseWriter, request *http.Request) {
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

func writeJSON(response http.ResponseWriter, status int, payload any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(payload)
}
