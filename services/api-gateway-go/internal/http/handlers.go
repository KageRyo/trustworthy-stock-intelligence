package apihttp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/watchlist"
)

type WarningStore interface {
	Batch() warnings.PredictionBatch
	FindTicker(ticker string) (warnings.PredictionRecord, bool)
	Refresh() error
	Status() warnings.StoreStatus
}

type Handlers struct {
	store     WarningStore
	watchlist WatchlistStore
}

type WatchlistStore interface {
	List(ctx context.Context, name string) (watchlist.Watchlist, error)
	AddTicker(ctx context.Context, name string, input watchlist.AddTickerInput) (watchlist.Ticker, error)
	RemoveTicker(ctx context.Context, name string, ticker string) (bool, error)
}

type CurrentModelResponse struct {
	SchemaVersion string `json:"schema_version"`
	RunID         string `json:"run_id"`
	DataAsOf      string `json:"data_as_of"`
	Model         string `json:"model"`
	ModelBundle   string `json:"model_bundle"`
	GeneratedAt   string `json:"generated_at"`
	RecordCount   int    `json:"record_count"`
}

type HealthResponse struct {
	Status         string `json:"status"`
	WarningsLoaded bool   `json:"warnings_loaded"`
	SchemaVersion  string `json:"schema_version"`
	RunID          string `json:"run_id"`
	DataAsOf       string `json:"data_as_of"`
	GeneratedAt    string `json:"generated_at"`
	RecordCount    int    `json:"record_count"`
	LastError      string `json:"last_error,omitempty"`
}

type ErrorResponse struct {
	Error ErrorBody `json:"error"`
}

type ErrorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func NewHandlers(store WarningStore, watchlistStores ...WatchlistStore) *Handlers {
	var storeWatchlist WatchlistStore
	if len(watchlistStores) > 0 {
		storeWatchlist = watchlistStores[0]
	}
	return &Handlers{store: store, watchlist: storeWatchlist}
}

func (h *Handlers) Health(response http.ResponseWriter, _ *http.Request) {
	h.refreshStore()
	status := h.store.Status()
	writeJSON(response, http.StatusOK, HealthResponse{
		Status:         "ok",
		WarningsLoaded: status.WarningsLoaded,
		SchemaVersion:  status.SchemaVersion,
		RunID:          status.RunID,
		DataAsOf:       status.DataAsOf,
		GeneratedAt:    status.GeneratedAt,
		RecordCount:    status.RecordCount,
		LastError:      status.LastError,
	})
}

func (h *Handlers) Metrics(response http.ResponseWriter, _ *http.Request) {
	h.refreshStore()
	status := h.store.Status()
	warningsLoaded := 0
	if status.WarningsLoaded {
		warningsLoaded = 1
	}
	lastReloadError := 0
	if status.LastError != "" {
		lastReloadError = 1
	}
	response.Header().Set("Content-Type", "text/plain; version=0.0.4")
	response.WriteHeader(http.StatusOK)
	_, _ = fmt.Fprintf(
		response,
		"# HELP tsi_api_warnings_loaded Whether a warning batch is loaded.\n"+
			"# TYPE tsi_api_warnings_loaded gauge\n"+
			"tsi_api_warnings_loaded %d\n"+
			"# HELP tsi_api_warning_records Number of warning records in the loaded batch.\n"+
			"# TYPE tsi_api_warning_records gauge\n"+
			"tsi_api_warning_records %d\n"+
			"# HELP tsi_api_last_reload_error Whether the last warning reload failed.\n"+
			"# TYPE tsi_api_last_reload_error gauge\n"+
			"tsi_api_last_reload_error %d\n"+
			"# HELP tsi_api_batch_info Metadata for the loaded warning batch.\n"+
			"# TYPE tsi_api_batch_info gauge\n"+
			"tsi_api_batch_info{schema_version=%q,run_id=%q,data_as_of=%q} 1\n",
		warningsLoaded,
		status.RecordCount,
		lastReloadError,
		status.SchemaVersion,
		status.RunID,
		status.DataAsOf,
	)
}

func (h *Handlers) LatestWarnings(response http.ResponseWriter, request *http.Request) {
	h.refreshStore()
	batch, err := filterBatch(h.store.Batch(), request)
	if err != nil {
		writeError(response, http.StatusBadRequest, err)
		return
	}
	writeJSON(response, http.StatusOK, batch)
}

func (h *Handlers) Tickers(response http.ResponseWriter, _ *http.Request) {
	h.refreshStore()
	writeJSON(response, http.StatusOK, buildTickerList(h.store.Batch()))
}

func (h *Handlers) TickerWarning(response http.ResponseWriter, request *http.Request) {
	h.refreshStore()
	ticker := strings.TrimPrefix(request.URL.Path, "/api/v1/warnings/")
	ticker = strings.TrimSpace(ticker)
	if ticker == "" || strings.Contains(ticker, "/") {
		writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
		return
	}
	record, ok := h.store.FindTicker(ticker)
	if !ok {
		writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
		return
	}
	writeJSON(response, http.StatusOK, record)
}

func (h *Handlers) TickerAnalysis(response http.ResponseWriter, request *http.Request) {
	h.refreshStore()
	ticker := strings.TrimPrefix(request.URL.Path, "/api/v1/analysis/")
	ticker = strings.TrimSpace(ticker)
	if ticker == "" || strings.Contains(ticker, "/") {
		writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
		return
	}
	record, ok := h.store.FindTicker(ticker)
	if !ok {
		writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
		return
	}
	writeJSON(response, http.StatusOK, buildTickerAnalysis(record, h.store.Status()))
}

func (h *Handlers) CurrentModel(response http.ResponseWriter, _ *http.Request) {
	h.refreshStore()
	batch := h.store.Batch()
	payload := CurrentModelResponse{
		SchemaVersion: batch.SchemaVersion,
		RunID:         batch.RunID,
		DataAsOf:      batch.DataAsOf,
		GeneratedAt:   batch.GeneratedAt,
		RecordCount:   batch.RecordCount,
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

func writeError(response http.ResponseWriter, status int, err error) {
	apiError, ok := err.(httpError)
	if !ok {
		apiError = newHTTPError("internal_error", err.Error())
	}
	writeJSON(response, status, ErrorResponse{
		Error: ErrorBody{
			Code:    apiError.code,
			Message: apiError.message,
		},
	})
}

func filterBatch(batch warnings.PredictionBatch, request *http.Request) (warnings.PredictionBatch, error) {
	level := strings.TrimSpace(request.URL.Query().Get("level"))
	limitText := strings.TrimSpace(request.URL.Query().Get("limit"))
	sortField := strings.TrimSpace(request.URL.Query().Get("sort"))
	order := strings.TrimSpace(request.URL.Query().Get("order"))
	if level != "" && !validWarningLevel(level) {
		return warnings.PredictionBatch{}, newHTTPError(
			"invalid_level",
			"level must be one of alert, watch, abstain, no_alert",
		)
	}
	if sortField != "" && !validSortField(sortField) {
		return warnings.PredictionBatch{}, newHTTPError(
			"invalid_sort",
			"sort must be one of trust_score, calibrated_risk_probability, uncertainty_score",
		)
	}
	if order == "" {
		order = "desc"
	}
	if !validOrder(order) {
		return warnings.PredictionBatch{}, newHTTPError("invalid_order", "order must be asc or desc")
	}
	limit := len(batch.Records)
	if limitText != "" {
		parsed, err := strconv.Atoi(limitText)
		if err != nil || parsed < 0 {
			return warnings.PredictionBatch{}, newHTTPError(
				"invalid_limit",
				"limit must be a non-negative integer",
			)
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
	}
	if sortField != "" {
		sort.SliceStable(records, func(left int, right int) bool {
			leftValue := sortValue(records[left], sortField)
			rightValue := sortValue(records[right], sortField)
			if order == "asc" {
				return leftValue < rightValue
			}
			return leftValue > rightValue
		})
	}
	if len(records) > limit {
		records = records[:limit]
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

func validSortField(field string) bool {
	switch field {
	case "trust_score", "calibrated_risk_probability", "uncertainty_score":
		return true
	default:
		return false
	}
}

func validOrder(order string) bool {
	switch order {
	case "asc", "desc":
		return true
	default:
		return false
	}
}

func sortValue(record warnings.PredictionRecord, field string) float64 {
	switch field {
	case "trust_score":
		return record.TrustScore
	case "calibrated_risk_probability":
		return record.CalibratedRiskProbability
	case "uncertainty_score":
		return record.UncertaintyScore
	default:
		return 0.0
	}
}

type httpError struct {
	code    string
	message string
}

func newHTTPError(code string, message string) httpError {
	return httpError{code: code, message: message}
}

func (e httpError) Error() string {
	return e.message
}
