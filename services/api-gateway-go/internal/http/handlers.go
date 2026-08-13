package apihttp

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/jobs"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/observability"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/watchlist"
)

type WarningStore interface {
	Batch() warnings.PredictionBatch
	FindTicker(ticker string) (warnings.PredictionRecord, bool)
	History(ticker string, limit int) ([]warnings.WarningHistoryRecord, error)
	Refresh() error
	Status() warnings.StoreStatus
}

type ProviderHealthStore interface {
	ListProviderHealth(ctx context.Context) ([]warnings.ProviderHealthRecord, error)
}

type WarningTransitionStore interface {
	Transitions(ctx context.Context, ticker string, limit int) ([]warnings.WarningTransitionRecord, error)
}

type PredictionJobStore interface {
	Enqueue(ctx context.Context, request jobs.CreateRequest) (jobs.PredictionJob, error)
	Get(ctx context.Context, id string) (jobs.PredictionJob, bool, error)
}

type ReadinessStore interface {
	Ready(ctx context.Context) error
}

type IngestionMetricsStore interface {
	IngestionMetrics(ctx context.Context) (warnings.IngestionMetrics, error)
}

type PredictionJobMetricsStore interface {
	QueueMetrics(ctx context.Context) (jobs.QueueMetrics, error)
}

type Handlers struct {
	store            WarningStore
	providerHealth   ProviderHealthStore
	transitions      WarningTransitionStore
	watchlist        WatchlistStore
	predictionJobs   PredictionJobStore
	onDemandAnalyzer OnDemandAnalyzer
	metrics          *observability.Registry
	logger           *slog.Logger
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

type WarningHistoryResponse struct {
	SchemaVersion string                          `json:"schema_version"`
	Ticker        string                          `json:"ticker"`
	RecordCount   int                             `json:"record_count"`
	Records       []warnings.WarningHistoryRecord `json:"records"`
}

type ProviderHealthResponse struct {
	SchemaVersion string                          `json:"schema_version"`
	GeneratedAt   string                          `json:"generated_at"`
	RecordCount   int                             `json:"record_count"`
	Records       []warnings.ProviderHealthRecord `json:"records"`
}

func NewHandlers(store WarningStore, watchlistStores ...WatchlistStore) *Handlers {
	var storeWatchlist WatchlistStore
	if len(watchlistStores) > 0 {
		storeWatchlist = watchlistStores[0]
	}
	return &Handlers{
		store: store,
		watchlist: storeWatchlist,
		metrics: observability.NewRegistry(),
		logger: slog.New(slog.NewJSONHandler(io.Discard, nil)),
	}
}

func (h *Handlers) MetricsRegistry() *observability.Registry {
	if h.metrics == nil {
		h.metrics = observability.NewRegistry()
	}
	return h.metrics
}

func (h *Handlers) SetLogger(logger *slog.Logger) {
	if logger == nil {
		h.logger = slog.New(slog.NewJSONHandler(io.Discard, nil))
		return
	}
	h.logger = logger
}

func (h *Handlers) SetOnDemandAnalyzer(analyzer OnDemandAnalyzer) {
	h.onDemandAnalyzer = analyzer
}

func (h *Handlers) SetProviderHealthStore(store ProviderHealthStore) {
	h.providerHealth = store
}

func (h *Handlers) SetPredictionJobStore(store PredictionJobStore) {
	h.predictionJobs = store
}

func (h *Handlers) SetWarningTransitionStore(store WarningTransitionStore) {
	h.transitions = store
}

func (h *Handlers) ProviderHealth(response http.ResponseWriter, request *http.Request) {
	if h.providerHealth == nil {
		writeError(
			response,
			http.StatusServiceUnavailable,
			newHTTPError("provider_health_store_unavailable", "provider health store is unavailable"),
		)
		return
	}
	records, err := h.providerHealth.ListProviderHealth(request.Context())
	if err != nil {
		writeError(response, http.StatusServiceUnavailable, newHTTPError(
			"provider_health_store_unavailable",
			"provider health store could not be read",
		))
		return
	}
	if records == nil {
		records = []warnings.ProviderHealthRecord{}
	}
	writeJSON(response, http.StatusOK, ProviderHealthResponse{
		SchemaVersion: "provider_health.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		RecordCount:   len(records),
		Records:       records,
	})
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
	metrics := h.MetricsRegistry()
	metrics.SetGauge("tsi_api_warnings_loaded", nil, boolGauge(status.WarningsLoaded))
	metrics.SetGauge("tsi_api_warning_records", nil, float64(status.RecordCount))
	metrics.SetGauge("tsi_api_last_reload_error", nil, boolGauge(status.LastError != ""))
	metrics.SetGauge("tsi_api_stale_predictions", nil, stalePredictionGauge(status.DataAsOf))
	if ingestionStore, ok := h.store.(IngestionMetricsStore); ok {
		if ingestion, err := ingestionStore.IngestionMetrics(context.Background()); err == nil {
			metrics.SetGauge("tsi_ingestion_runs", observability.Labels{"status": "success"}, float64(ingestion.SuccessCount))
			metrics.SetGauge("tsi_ingestion_runs", observability.Labels{"status": "failed"}, float64(ingestion.FailureCount))
			metrics.SetGauge("tsi_ingestion_runs", observability.Labels{"status": "running"}, float64(ingestion.RunningCount))
		}
	}
	if jobStore, ok := h.predictionJobs.(PredictionJobMetricsStore); ok {
		if queue, err := jobStore.QueueMetrics(context.Background()); err == nil {
			for label, value := range map[string]int{
				"queued": queue.Queued, "running": queue.Running, "completed": queue.Completed,
				"failed": queue.Failed, "cancelled": queue.Cancelled,
			} {
				metrics.SetGauge("tsi_prediction_jobs", observability.Labels{"status": label}, float64(value))
			}
		}
	}
	response.Header().Set("Content-Type", "text/plain; version=0.0.4")
	response.WriteHeader(http.StatusOK)
	_, _ = fmt.Fprint(response, metrics.Render())
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
		int(boolGauge(status.WarningsLoaded)),
		status.RecordCount,
		int(boolGauge(status.LastError != "")),
		status.SchemaVersion,
		status.RunID,
		status.DataAsOf,
	)
}

func boolGauge(value bool) float64 {
	if value {
		return 1
	}
	return 0
}

func stalePredictionGauge(dataAsOf string) float64 {
	if strings.TrimSpace(dataAsOf) == "" {
		return 1
	}
	parsed, err := time.Parse(time.RFC3339, dataAsOf)
	if err != nil {
		parsed, err = time.Parse("2006-01-02", dataAsOf)
	}
	if err != nil || time.Since(parsed) > 48*time.Hour {
		return 1
	}
	return 0
}

type ReadinessResponse struct {
	SchemaVersion  string `json:"schema_version"`
	Status         string `json:"status"`
	ProcessUp      bool   `json:"process_up"`
	DatabaseReady  bool   `json:"database_ready"`
	WarningsLoaded bool   `json:"warnings_loaded"`
	CheckedAt      string `json:"checked_at"`
}

func (h *Handlers) Readiness(response http.ResponseWriter, request *http.Request) {
	status := h.store.Status()
	ready := status.WarningsLoaded && status.LastError == ""
	databaseReady := false
	if store, ok := h.store.(ReadinessStore); ok {
		ctx, cancel := context.WithTimeout(request.Context(), 2*time.Second)
		err := store.Ready(ctx)
		cancel()
		databaseReady = err == nil
		ready = ready && databaseReady
	} else {
		// File stores remain useful for local handler tests. Production PostgreSQL
		// stores implement ReadinessStore and therefore check the dependency.
		databaseReady = status.WarningsLoaded
	}
	payload := ReadinessResponse{
		SchemaVersion:  "readiness.v1",
		Status:         "not_ready",
		ProcessUp:      true,
		DatabaseReady:  databaseReady,
		WarningsLoaded: status.WarningsLoaded,
		CheckedAt:      time.Now().UTC().Format(time.RFC3339),
	}
	if ready {
		payload.Status = "ready"
		writeJSON(response, http.StatusOK, payload)
		return
	}
	writeJSON(response, http.StatusServiceUnavailable, payload)
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
		if h.onDemandAnalyzer == nil {
			writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
			return
		}
		if err := h.onDemandAnalyzer.Analyze(request.Context(), ticker); err != nil {
			writeError(
				response,
				http.StatusServiceUnavailable,
				newHTTPError("on_demand_analysis_failed", err.Error()),
			)
			return
		}
		h.refreshStore()
		record, ok = h.store.FindTicker(ticker)
		if !ok {
			writeError(
				response,
				http.StatusNotFound,
				newHTTPError("ticker_not_found", "ticker not found after on-demand analysis"),
			)
			return
		}
	}
	batch := h.store.Batch()
	writeJSON(
		response,
		http.StatusOK,
		buildTickerAnalysis(record, h.store.Status(), batch.CalibrationDrift, batch.FeatureInterval),
	)
}

func (h *Handlers) TickerWarningHistory(response http.ResponseWriter, request *http.Request) {
	h.refreshStore()
	ticker := strings.TrimPrefix(request.URL.Path, "/api/v1/analysis/")
	ticker = strings.TrimSuffix(ticker, "/history")
	ticker = strings.TrimSpace(ticker)
	if ticker == "" || strings.Contains(ticker, "/") {
		writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
		return
	}

	limit, err := parseHistoryLimit(request)
	if err != nil {
		writeError(response, http.StatusBadRequest, err)
		return
	}
	history, err := h.store.History(ticker, limit)
	if err != nil {
		writeError(response, http.StatusServiceUnavailable, newHTTPError("history_unavailable", err.Error()))
		return
	}
	if len(history) == 0 && h.onDemandAnalyzer != nil {
		if err := h.onDemandAnalyzer.Analyze(request.Context(), ticker); err != nil {
			writeError(response, http.StatusServiceUnavailable, newHTTPError("on_demand_analysis_failed", err.Error()))
			return
		}
		h.refreshStore()
		history, err = h.store.History(ticker, limit)
		if err != nil {
			writeError(response, http.StatusServiceUnavailable, newHTTPError("history_unavailable", err.Error()))
			return
		}
	}
	if len(history) == 0 {
		writeError(response, http.StatusNotFound, newHTTPError("ticker_not_found", "ticker not found"))
		return
	}

	writeJSON(response, http.StatusOK, WarningHistoryResponse{
		SchemaVersion: "warning_history.v1",
		Ticker:        history[0].Ticker,
		RecordCount:   len(history),
		Records:       history,
	})
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

func parseHistoryLimit(request *http.Request) (int, error) {
	const defaultHistoryLimit = 90
	const maxHistoryLimit = 3650
	limitText := strings.TrimSpace(request.URL.Query().Get("limit"))
	if limitText == "" {
		return defaultHistoryLimit, nil
	}
	limit, err := strconv.Atoi(limitText)
	if err != nil || limit < 1 || limit > maxHistoryLimit {
		return 0, newHTTPError(
			"invalid_history_limit",
			"limit must be an integer between 1 and 3650",
		)
	}
	return limit, nil
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
