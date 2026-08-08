package apihttp

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/watchlist"
)

func writeRouterFixture(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "latest_warnings.json")
	payload := `{
  "schema_version": "v1",
  "run_id": "fixture_run",
  "data_as_of": "2026-06-08",
  "generated_at": "2026-06-10T00:00:00+00:00",
  "record_count": 2,
  "records": [
    {
      "date": "2026-06-08",
      "ticker": "AAPL",
      "model": "temporal_transformer",
      "model_bundle": "bundle",
      "risk_probability": 0.18,
      "calibrated_risk_probability": 0.12,
      "calibration_method": "platt",
      "uncertainty_score": 0.43,
      "trust_score": 0.09,
      "alert_threshold": 0.2,
      "watch_threshold": 0.16,
      "warning_level": "watch",
      "reason_codes": [
        "probability_above_watch_threshold",
        "trust_below_alert_threshold",
        "uncertainty_below_threshold",
        "warning_level_watch"
      ]
    },
    {
      "date": "2026-06-08",
      "ticker": "MSFT",
      "model": "temporal_transformer",
      "model_bundle": "bundle",
      "risk_probability": 0.03,
      "calibrated_risk_probability": 0.02,
      "calibration_method": "platt",
      "uncertainty_score": 0.12,
      "trust_score": 0.01,
      "alert_threshold": 0.2,
      "watch_threshold": 0.16,
      "warning_level": "no_alert",
      "reason_codes": [
        "calibrated_probability_below_watch_threshold",
        "trust_below_alert_threshold",
        "uncertainty_below_threshold",
        "warning_level_no_alert"
      ]
    }
  ]
}`
	if err := os.WriteFile(path, []byte(payload), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	return path
}

func testRouter(t *testing.T) http.Handler {
	t.Helper()
	return NewRouter(NewHandlers(mustFileStore(t)))
}

func mustFileStore(t *testing.T) *warnings.FileStore {
	t.Helper()
	path := writeRouterFixture(t)
	store, err := warnings.NewFileStore(path)
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}
	return store
}

func testRouterFromPayload(t *testing.T, payload string) http.Handler {
	t.Helper()
	path := filepath.Join(t.TempDir(), "latest_warnings.json")
	if err := os.WriteFile(path, []byte(payload), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	store, err := warnings.NewFileStore(path)
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}
	return NewRouter(NewHandlers(store))
}

func testRouterWithWatchlist(t *testing.T, watchlistStore WatchlistStore) http.Handler {
	t.Helper()
	path := writeRouterFixture(t)
	store, err := warnings.NewFileStore(path)
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}
	return NewRouter(NewHandlers(store, watchlistStore))
}

func getJSON(t *testing.T, router http.Handler, path string) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodGet, path, nil)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	return response
}

func postJSON(t *testing.T, router http.Handler, path string, body string) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodPost, path, bytes.NewBufferString(body))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	return response
}

func deleteJSON(t *testing.T, router http.Handler, path string) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodDelete, path, nil)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	return response
}

func TestCORSAllowsConfiguredOrigin(t *testing.T) {
	router := NewRouter(
		NewHandlers(mustFileStore(t)),
		CORSConfig{AllowedOrigins: []string{"https://dashboard.example.test"}},
	)
	request := httptest.NewRequest(http.MethodOptions, "/api/v1/status", nil)
	request.Header.Set("Origin", "https://dashboard.example.test")
	request.Header.Set("Access-Control-Request-Method", "GET")
	response := httptest.NewRecorder()

	router.ServeHTTP(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want 204", response.Code)
	}
	if got := response.Header().Get("Access-Control-Allow-Origin"); got != "https://dashboard.example.test" {
		t.Fatalf("allow origin = %q, want configured origin", got)
	}
	if got := response.Header().Get("Access-Control-Allow-Methods"); !strings.Contains(got, "POST") {
		t.Fatalf("allow methods missing POST: %q", got)
	}
}

func TestCORSAddsHeadersOnGET(t *testing.T) {
	router := NewRouter(
		NewHandlers(mustFileStore(t)),
		CORSConfig{AllowedOrigins: []string{"https://dashboard.example.test"}},
	)
	request := httptest.NewRequest(http.MethodGet, "/api/v1/status", nil)
	request.Header.Set("Origin", "https://dashboard.example.test")
	response := httptest.NewRecorder()

	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if got := response.Header().Get("Access-Control-Allow-Origin"); got != "https://dashboard.example.test" {
		t.Fatalf("allow origin = %q, want configured origin", got)
	}
}

func TestCORSRejectsUnconfiguredPreflightOrigin(t *testing.T) {
	router := NewRouter(
		NewHandlers(mustFileStore(t)),
		CORSConfig{AllowedOrigins: []string{"http://localhost:5175"}},
	)
	request := httptest.NewRequest(http.MethodOptions, "/api/v1/status", nil)
	request.Header.Set("Origin", "http://evil.example")
	request.Header.Set("Access-Control-Request-Method", "GET")
	response := httptest.NewRecorder()

	router.ServeHTTP(response, request)

	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403", response.Code)
	}
	if got := response.Header().Get("Access-Control-Allow-Origin"); got != "" {
		t.Fatalf("allow origin = %q, want empty", got)
	}
}

func TestHealthHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/health")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload HealthResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Status != "ok" {
		t.Fatalf("status payload = %q, want ok", payload.Status)
	}
	if !payload.WarningsLoaded {
		t.Fatalf("warnings_loaded = %v, want true", payload.WarningsLoaded)
	}
	if payload.SchemaVersion != "v1" || payload.RunID != "fixture_run" {
		t.Fatalf("unexpected contract metadata: %+v", payload)
	}
}

func TestMetricsHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/metrics")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	body := response.Body.String()
	if !strings.Contains(body, "tsi_api_warnings_loaded 1") {
		t.Fatalf("metrics missing warnings loaded gauge: %s", body)
	}
	if !strings.Contains(body, `tsi_api_batch_info{schema_version="v1",run_id="fixture_run",data_as_of="2026-06-08"} 1`) {
		t.Fatalf("metrics missing batch info: %s", body)
	}
}

func TestStatusHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/status")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload warnings.StoreStatus
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.RecordCount != 2 {
		t.Fatalf("record_count = %d, want 2", payload.RecordCount)
	}
	if payload.SchemaVersion != "v1" || payload.RunID != "fixture_run" {
		t.Fatalf("unexpected contract metadata: %+v", payload)
	}
}

func TestOpenAPIHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/openapi.yaml")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if contentType := response.Header().Get("Content-Type"); contentType != "application/yaml" {
		t.Fatalf("content type = %q, want application/yaml", contentType)
	}
	body := response.Body.String()
	if !strings.Contains(body, "openapi: 3.1.0") ||
		!strings.Contains(body, "/api/v1/analysis/{ticker}") ||
		!strings.Contains(body, "/api/v1/tickers") {
		t.Fatalf("openapi response missing expected content: %s", body)
	}
}

func TestSwaggerHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/swagger")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	body := response.Body.String()
	if !strings.Contains(body, "SwaggerUIBundle") || !strings.Contains(body, "/openapi.yaml") {
		t.Fatalf("swagger response missing expected content: %s", body)
	}

	response = getJSON(t, testRouter(t), "/swagger/")
	if response.Code != http.StatusOK {
		t.Fatalf("trailing slash status = %d, want 200", response.Code)
	}
}

func TestEmbeddedOpenAPISpecMatchesDocsSpec(t *testing.T) {
	docsSpec, err := os.ReadFile(filepath.Join("..", "..", "..", "..", "docs", "api", "openapi.yaml"))
	if err != nil {
		t.Fatalf("read docs openapi spec: %v", err)
	}
	if string(openAPISpec) != string(docsSpec) {
		t.Fatal("embedded openapi spec must match docs/api/openapi.yaml")
	}
}

func TestLatestWarningsHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/latest")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var batch warnings.PredictionBatch
	if err := json.NewDecoder(response.Body).Decode(&batch); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if batch.RecordCount != 2 {
		t.Fatalf("record_count = %d, want 2", batch.RecordCount)
	}
}

func TestTickersHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/tickers")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload TickerListResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.SchemaVersion != "ticker_list.v1" {
		t.Fatalf("schema version = %q, want ticker_list.v1", payload.SchemaVersion)
	}
	if payload.RecordCount != 2 {
		t.Fatalf("record_count = %d, want 2", payload.RecordCount)
	}
	if payload.Tickers[0].Ticker != "AAPL" || payload.Tickers[0].Market != "us" {
		t.Fatalf("unexpected first ticker: %+v", payload.Tickers[0])
	}
}

func TestLatestWarningsHandlerFiltersByLevel(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/latest?level=watch")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var batch warnings.PredictionBatch
	if err := json.NewDecoder(response.Body).Decode(&batch); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if batch.RecordCount != 1 {
		t.Fatalf("record_count = %d, want 1", batch.RecordCount)
	}
	if batch.Records[0].Ticker != "AAPL" {
		t.Fatalf("ticker = %q, want AAPL", batch.Records[0].Ticker)
	}
}

func TestLatestWarningsHandlerAppliesLimit(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/latest?limit=1")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var batch warnings.PredictionBatch
	if err := json.NewDecoder(response.Body).Decode(&batch); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if batch.RecordCount != 1 {
		t.Fatalf("record_count = %d, want 1", batch.RecordCount)
	}
}

func TestLatestWarningsHandlerSortsBeforeLimit(t *testing.T) {
	response := getJSON(
		t,
		testRouter(t),
		"/api/v1/warnings/latest?sort=trust_score&order=asc&limit=1",
	)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var batch warnings.PredictionBatch
	if err := json.NewDecoder(response.Body).Decode(&batch); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if batch.RecordCount != 1 {
		t.Fatalf("record_count = %d, want 1", batch.RecordCount)
	}
	if batch.Records[0].Ticker != "MSFT" {
		t.Fatalf("ticker = %q, want MSFT", batch.Records[0].Ticker)
	}
}

func TestLatestWarningsHandlerRejectsInvalidLevel(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/latest?level=bad")

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "invalid_level" {
		t.Fatalf("error code = %q, want invalid_level", payload.Error.Code)
	}
}

func TestLatestWarningsHandlerRejectsInvalidLimit(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/latest?limit=-1")

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "invalid_limit" {
		t.Fatalf("error code = %q, want invalid_limit", payload.Error.Code)
	}
}

func TestLatestWarningsHandlerRejectsInvalidSort(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/latest?sort=ticker")

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "invalid_sort" {
		t.Fatalf("error code = %q, want invalid_sort", payload.Error.Code)
	}
}

func TestTickerWarningHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/aapl")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var record warnings.PredictionRecord
	if err := json.NewDecoder(response.Body).Decode(&record); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if record.Ticker != "AAPL" {
		t.Fatalf("ticker = %q, want AAPL", record.Ticker)
	}
}

func TestTickerWarningHandlerReturnsNotFound(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/warnings/NVDA")

	if response.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "ticker_not_found" {
		t.Fatalf("error code = %q, want ticker_not_found", payload.Error.Code)
	}
}

func TestTickerAnalysisHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/analysis/aapl")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload TickerAnalysisResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.SchemaVersion != "analysis.v1" {
		t.Fatalf("schema_version = %q, want analysis.v1", payload.SchemaVersion)
	}
	if payload.Ticker != "AAPL" || payload.Date != "2026-06-08" {
		t.Fatalf("unexpected ticker metadata: %+v", payload)
	}
	if payload.Warning.Level != "watch" {
		t.Fatalf("warning level = %q, want watch", payload.Warning.Level)
	}
	if payload.Warning.CalibratedRiskProbability != 0.12 {
		t.Fatalf(
			"calibrated risk probability = %f, want 0.12",
			payload.Warning.CalibratedRiskProbability,
		)
	}
	if payload.Trust.TrustStatus != "limited_trust" {
		t.Fatalf("trust status = %q, want limited_trust", payload.Trust.TrustStatus)
	}
	if payload.Trust.UncertaintyStatus != "acceptable_uncertainty" {
		t.Fatalf(
			"uncertainty status = %q, want acceptable_uncertainty",
			payload.Trust.UncertaintyStatus,
		)
	}
	if payload.Model.Name != "temporal_transformer" || payload.Model.ModelBundle != "bundle" {
		t.Fatalf("unexpected model analysis: %+v", payload.Model)
	}
	if payload.DataFreshness.RecordCount != 2 || payload.DataFreshness.LastLoadedAt == "" {
		t.Fatalf("unexpected data freshness: %+v", payload.DataFreshness)
	}
	if len(payload.Reasons) != 4 {
		t.Fatalf("reasons length = %d, want 4", len(payload.Reasons))
	}
	if payload.Reasons[0].Code != "probability_above_watch_threshold" ||
		payload.Reasons[0].Severity != "watch" {
		t.Fatalf("unexpected first reason: %+v", payload.Reasons[0])
	}
	if len(payload.Limitations) == 0 {
		t.Fatal("expected limitations")
	}
}

func TestTickerWarningHistoryHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/analysis/aapl/history?limit=10")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload WarningHistoryResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.SchemaVersion != "warning_history.v1" || payload.Ticker != "AAPL" {
		t.Fatalf("unexpected history metadata: %+v", payload)
	}
	if payload.RecordCount != 1 || len(payload.Records) != 1 {
		t.Fatalf("record_count = %d, records = %d, want one", payload.RecordCount, len(payload.Records))
	}
	if payload.Records[0].Ticker != "AAPL" || payload.Records[0].WarningLevel != "watch" {
		t.Fatalf("unexpected history record: %+v", payload.Records[0])
	}
}

func TestTickerWarningHistoryHandlerRejectsInvalidLimit(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/analysis/AAPL/history?limit=0")

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "invalid_history_limit" {
		t.Fatalf("error code = %q, want invalid_history_limit", payload.Error.Code)
	}
}

func TestBuildTickerAnalysisPrefersRecordMetadata(t *testing.T) {
	payload := buildTickerAnalysis(
		warnings.PredictionRecord{
			RunID:                     "record_run",
			DataAsOf:                  "2026-06-18",
			GeneratedAt:               "2026-06-20T08:46:54Z",
			Date:                      "2026-06-18",
			Ticker:                    "2884",
			Model:                     "logistic_regression_latest",
			ModelBundle:               "bundle",
			RiskProbability:           0.3,
			CalibratedRiskProbability: 0.2,
			CalibrationMethod:         "platt",
			UncertaintyScore:          0.4,
			TrustScore:                0.1,
			AlertThreshold:            0.5,
			WatchThreshold:            0.4,
			WarningLevel:              "no_alert",
			ReasonCodes:               []string{"warning_level_no_alert"},
		},
		warnings.StoreStatus{
			RunID:       "global_latest_run",
			DataAsOf:    "2026-06-20",
			GeneratedAt: "2026-06-20T08:47:11Z",
		},
	)

	if payload.RunID != "record_run" {
		t.Fatalf("run_id = %q, want record_run", payload.RunID)
	}
	if payload.DataAsOf != "2026-06-18" || payload.DataFreshness.DataAsOf != "2026-06-18" {
		t.Fatalf("unexpected data_as_of metadata: %+v", payload)
	}
}

func TestExplainReasonCodeSupportsInsufficientHistory(t *testing.T) {
	reason := explainReasonCode("insufficient_history")

	if reason.Severity != "watch" {
		t.Fatalf("severity = %q, want watch", reason.Severity)
	}
	if !strings.Contains(strings.ToLower(reason.Detail), "not enough labeled history") {
		t.Fatalf("unexpected detail: %+v", reason)
	}
}

func TestTickerAnalysisHandlerReturnsNotFound(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/analysis/NVDA")

	if response.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "ticker_not_found" {
		t.Fatalf("error code = %q, want ticker_not_found", payload.Error.Code)
	}
}

func TestTickerAnalysisHandlerRunsOnDemandWhenTickerMissing(t *testing.T) {
	store := newMutableWarningStore()
	analyzer := &fakeOnDemandAnalyzer{
		onAnalyze: func(ticker string) {
			if ticker != "2884" {
				t.Fatalf("ticker = %q, want 2884", ticker)
			}
			store.setRecord(warnings.PredictionRecord{
				Date:                      "2026-06-19",
				Ticker:                    "2884",
				Model:                     "logistic_regression_latest",
				ModelBundle:               "baseline_latest:data/raw/on_demand/2884/ohlcv.csv",
				RiskProbability:           0.21,
				CalibratedRiskProbability: 0.17,
				CalibrationMethod:         "platt",
				UncertaintyScore:          0.22,
				TrustScore:                0.13,
				AlertThreshold:            0.3,
				WatchThreshold:            0.15,
				WarningLevel:              "watch",
				ReasonCodes:               []string{"warning_level_watch"},
			})
		},
	}
	handlers := NewHandlers(store)
	handlers.SetOnDemandAnalyzer(analyzer)
	router := NewRouter(handlers)

	response := getJSON(t, router, "/api/v1/analysis/2884")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200: %s", response.Code, response.Body.String())
	}
	var payload TickerAnalysisResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Ticker != "2884" || payload.Warning.Level != "watch" {
		t.Fatalf("unexpected analysis response: %+v", payload)
	}
	if len(analyzer.calls) != 1 || analyzer.calls[0] != "2884" {
		t.Fatalf("on-demand calls = %+v, want [2884]", analyzer.calls)
	}
}

func TestTickerAnalysisHandlerReturnsUnavailableWhenOnDemandFails(t *testing.T) {
	store := newMutableWarningStore()
	handlers := NewHandlers(store)
	handlers.SetOnDemandAnalyzer(&fakeOnDemandAnalyzer{err: errors.New("provider failed")})
	router := NewRouter(handlers)

	response := getJSON(t, router, "/api/v1/analysis/2884")

	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "on_demand_analysis_failed" {
		t.Fatalf("error code = %q, want on_demand_analysis_failed", payload.Error.Code)
	}
}

func TestHandlersSupportNumericTaiwanTicker(t *testing.T) {
	router := testRouterFromPayload(t, `{
  "schema_version": "v1",
  "run_id": "tw_fixture_run",
  "data_as_of": "2026-06-19",
  "generated_at": "2026-06-19T00:00:00+00:00",
  "record_count": 1,
  "records": [
    {
      "date": "2026-06-19",
      "ticker": "2330",
      "model": "temporal_transformer",
      "model_bundle": "tw_bundle",
      "risk_probability": 0.31,
      "calibrated_risk_probability": 0.22,
      "calibration_method": "platt",
      "uncertainty_score": 0.25,
      "trust_score": 0.18,
      "alert_threshold": 0.30,
      "watch_threshold": 0.15,
      "warning_level": "watch",
      "reason_codes": [
        "probability_above_watch_threshold",
        "trust_below_alert_threshold",
        "uncertainty_below_threshold",
        "warning_level_watch"
      ]
    }
  ]
}`)

	warningResponse := getJSON(t, router, "/api/v1/warnings/2330")
	if warningResponse.Code != http.StatusOK {
		t.Fatalf("warning status = %d, want 200", warningResponse.Code)
	}
	var warningRecord warnings.PredictionRecord
	if err := json.NewDecoder(warningResponse.Body).Decode(&warningRecord); err != nil {
		t.Fatalf("decode warning response: %v", err)
	}
	if warningRecord.Ticker != "2330" {
		t.Fatalf("warning ticker = %q, want 2330", warningRecord.Ticker)
	}

	analysisResponse := getJSON(t, router, "/api/v1/analysis/2330")
	if analysisResponse.Code != http.StatusOK {
		t.Fatalf("analysis status = %d, want 200", analysisResponse.Code)
	}
	var analysis TickerAnalysisResponse
	if err := json.NewDecoder(analysisResponse.Body).Decode(&analysis); err != nil {
		t.Fatalf("decode analysis response: %v", err)
	}
	if analysis.Ticker != "2330" || analysis.Warning.Level != "watch" {
		t.Fatalf("unexpected analysis response: %+v", analysis)
	}

	tickersResponse := getJSON(t, router, "/api/v1/tickers")
	if tickersResponse.Code != http.StatusOK {
		t.Fatalf("tickers status = %d, want 200", tickersResponse.Code)
	}
	var tickers TickerListResponse
	if err := json.NewDecoder(tickersResponse.Body).Decode(&tickers); err != nil {
		t.Fatalf("decode tickers response: %v", err)
	}
	if len(tickers.Tickers) != 1 || tickers.Tickers[0].Market != "taiwan" {
		t.Fatalf("unexpected tickers response: %+v", tickers)
	}
}

func TestTickerListClassifiesTaiwanAlphanumericTickers(t *testing.T) {
	batch := warnings.PredictionBatch{
		SchemaVersion: "v1",
		RunID:         "test",
		DataAsOf:      "2026-06-19",
		GeneratedAt:   "2026-06-19T00:00:00Z",
		Records: []warnings.PredictionRecord{
			{Ticker: "00981A", Date: "2026-06-19", WarningLevel: "abstain"},
			{Ticker: "02001L", Date: "2026-06-19", WarningLevel: "watch"},
			{Ticker: "5240.EMERGING", Date: "2026-06-19", WarningLevel: "watch"},
			{Ticker: "AAPL", Date: "2026-06-19", WarningLevel: "no_alert"},
		},
	}

	payload := buildTickerList(batch)
	markets := map[string]string{}
	for _, ticker := range payload.Tickers {
		markets[ticker.Ticker] = ticker.Market
	}

	if markets["00981A"] != "taiwan" ||
		markets["02001L"] != "taiwan" ||
		markets["5240.EMERGING"] != "taiwan" {
		t.Fatalf("taiwan tickers not classified as taiwan: %+v", markets)
	}
	if markets["AAPL"] != "us" {
		t.Fatalf("AAPL market = %q, want us", markets["AAPL"])
	}
}

func TestCurrentModelHandler(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/models/current")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload CurrentModelResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Model != "temporal_transformer" {
		t.Fatalf("model = %q, want temporal_transformer", payload.Model)
	}
	if payload.RecordCount != 2 {
		t.Fatalf("record_count = %d, want 2", payload.RecordCount)
	}
	if payload.SchemaVersion != "v1" || payload.RunID != "fixture_run" || payload.DataAsOf != "2026-06-08" {
		t.Fatalf("unexpected contract metadata: %+v", payload)
	}
}

func TestHandlersRefreshStoreBeforeServing(t *testing.T) {
	path := writeRouterFixture(t)
	store, err := warnings.NewFileStore(path)
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}
	router := NewRouter(NewHandlers(store))
	updated := `{
  "schema_version": "v1",
  "run_id": "fixture_run_v2",
  "data_as_of": "2026-06-09",
  "generated_at": "2026-06-11T00:00:00+00:00",
  "record_count": 1,
  "records": [
    {
      "date": "2026-06-09",
      "ticker": "NVDA",
      "model": "temporal_transformer",
      "model_bundle": "bundle_v2",
      "risk_probability": 0.38,
      "calibrated_risk_probability": 0.22,
      "calibration_method": "platt",
      "uncertainty_score": 0.25,
      "trust_score": 0.17,
      "alert_threshold": 0.2,
      "watch_threshold": 0.16,
      "warning_level": "alert",
      "reason_codes": ["warning_level_alert"]
    }
  ]
}`
	if err := os.WriteFile(path, []byte(updated), 0o644); err != nil {
		t.Fatalf("write updated fixture: %v", err)
	}
	if err := os.Chtimes(path, time.Now().Add(time.Second), time.Now().Add(time.Second)); err != nil {
		t.Fatalf("update mtime: %v", err)
	}

	response := getJSON(t, router, "/api/v1/warnings/NVDA")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var record warnings.PredictionRecord
	if err := json.NewDecoder(response.Body).Decode(&record); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if record.WarningLevel != "alert" {
		t.Fatalf("warning level = %q, want alert", record.WarningLevel)
	}
}

type fakeWatchlistStore struct {
	list      watchlist.Watchlist
	removeHit bool
}

func (s *fakeWatchlistStore) List(
	_ context.Context,
	name string,
) (watchlist.Watchlist, error) {
	if s.list.Name == "" {
		s.list.Name = name
	}
	return s.list, nil
}

func (s *fakeWatchlistStore) AddTicker(
	_ context.Context,
	name string,
	input watchlist.AddTickerInput,
) (watchlist.Ticker, error) {
	resolved, err := watchlist.ResolveTicker(input.Ticker, input.Market)
	if err != nil {
		return watchlist.Ticker{}, err
	}
	ticker := watchlist.Ticker{
		Ticker:      resolved.Ticker,
		QuerySymbol: resolved.QuerySymbol,
		Market:      resolved.Market,
		AddedAt:     "2026-06-19T00:00:00Z",
		Notes:       input.Notes,
	}
	s.list.Name = name
	s.list.Tickers = append(s.list.Tickers, ticker)
	s.list.UpdatedAt = ticker.AddedAt
	return ticker, nil
}

func (s *fakeWatchlistStore) RemoveTicker(
	_ context.Context,
	_ string,
	ticker string,
) (bool, error) {
	s.removeHit = true
	kept := make([]watchlist.Ticker, 0, len(s.list.Tickers))
	removed := false
	for _, entry := range s.list.Tickers {
		if strings.EqualFold(entry.Ticker, ticker) {
			removed = true
			continue
		}
		kept = append(kept, entry)
	}
	s.list.Tickers = kept
	return removed, nil
}

func TestWatchlistHandlerReturnsLatestWarningJoin(t *testing.T) {
	router := testRouterWithWatchlist(t, &fakeWatchlistStore{
		list: watchlist.Watchlist{
			Name:      "default",
			UpdatedAt: "2026-06-19T00:00:00Z",
			Tickers: []watchlist.Ticker{
				{
					Ticker:      "AAPL",
					QuerySymbol: "AAPL",
					Market:      "us",
					AddedAt:     "2026-06-19T00:00:00Z",
				},
			},
		},
	})

	response := getJSON(t, router, "/api/v1/watchlists/default")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload WatchlistResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.SchemaVersion != "watchlist.v1" || payload.RecordCount != 1 {
		t.Fatalf("unexpected watchlist response: %+v", payload)
	}
	if !payload.Tickers[0].HasLatestWarning || payload.Tickers[0].LatestWarning == nil {
		t.Fatalf("expected latest warning join: %+v", payload.Tickers[0])
	}
	if payload.Tickers[0].LatestWarning.WarningLevel != "watch" {
		t.Fatalf("warning level = %q, want watch", payload.Tickers[0].LatestWarning.WarningLevel)
	}
}

func TestAddWatchlistTickerAcceptsTaiwanNumericTicker(t *testing.T) {
	router := testRouterWithWatchlist(t, &fakeWatchlistStore{})

	response := postJSON(
		t,
		router,
		"/api/v1/watchlists/default/tickers",
		`{"schema_version":"watchlist_add.v1","ticker":"2330","market":"auto","notes":"core holding"}`,
	)

	if response.Code != http.StatusCreated {
		t.Fatalf("status = %d, want 201: %s", response.Code, response.Body.String())
	}
	var payload WatchlistResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.RecordCount != 1 {
		t.Fatalf("record_count = %d, want 1", payload.RecordCount)
	}
	ticker := payload.Tickers[0]
	if ticker.Ticker != "2330" || ticker.QuerySymbol != "2330.TW" || ticker.Market != "twse" {
		t.Fatalf("unexpected ticker mapping: %+v", ticker)
	}
	if ticker.HasLatestWarning {
		t.Fatalf("expected newly added ticker without latest warning: %+v", ticker)
	}
}

func TestAddWatchlistTickerAcceptsEmergingTicker(t *testing.T) {
	router := testRouterWithWatchlist(t, &fakeWatchlistStore{})

	response := postJSON(
		t,
		router,
		"/api/v1/watchlists/default/tickers",
		`{"schema_version":"watchlist_add.v1","ticker":"5240","market":"emerging","notes":""}`,
	)

	if response.Code != http.StatusCreated {
		t.Fatalf("status = %d, want 201: %s", response.Code, response.Body.String())
	}
	var payload WatchlistResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	ticker := payload.Tickers[0]
	if ticker.Ticker != "5240" || ticker.QuerySymbol != "5240.EMERGING" || ticker.Market != "emerging" {
		t.Fatalf("unexpected ticker mapping: %+v", ticker)
	}
}

func TestRemoveWatchlistTickerReturnsUpdatedWatchlist(t *testing.T) {
	store := &fakeWatchlistStore{
		list: watchlist.Watchlist{
			Name: "default",
			Tickers: []watchlist.Ticker{
				{Ticker: "AAPL", QuerySymbol: "AAPL", Market: "us"},
			},
		},
	}
	router := testRouterWithWatchlist(t, store)

	response := deleteJSON(t, router, "/api/v1/watchlists/default/tickers/AAPL")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if !store.removeHit {
		t.Fatal("expected fake store remove to be called")
	}
	var payload WatchlistResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.RecordCount != 0 {
		t.Fatalf("record_count = %d, want 0", payload.RecordCount)
	}
}

func TestWatchlistEndpointReportsUnavailableStore(t *testing.T) {
	response := getJSON(t, testRouter(t), "/api/v1/watchlists/default")

	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503", response.Code)
	}
	var payload ErrorResponse
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload.Error.Code != "watchlist_store_unavailable" {
		t.Fatalf("error code = %q, want watchlist_store_unavailable", payload.Error.Code)
	}
}

type mutableWarningStore struct {
	batch   warnings.PredictionBatch
	records map[string]warnings.PredictionRecord
	status  warnings.StoreStatus
}

func newMutableWarningStore() *mutableWarningStore {
	return &mutableWarningStore{
		batch: warnings.PredictionBatch{
			SchemaVersion: "v1",
			RunID:         "test_run",
			DataAsOf:      "2026-06-19",
			GeneratedAt:   "2026-06-19T00:00:00Z",
			Records:       []warnings.PredictionRecord{},
		},
		records: map[string]warnings.PredictionRecord{},
		status: warnings.StoreStatus{
			WarningsPath:   "test",
			WarningsLoaded: false,
			SchemaVersion:  "v1",
			RunID:          "test_run",
			DataAsOf:       "2026-06-19",
			GeneratedAt:    "2026-06-19T00:00:00Z",
			RecordCount:    0,
			LastLoadedAt:   "2026-06-19T00:00:00Z",
		},
	}
}

func (s *mutableWarningStore) Batch() warnings.PredictionBatch {
	return s.batch
}

func (s *mutableWarningStore) FindTicker(ticker string) (warnings.PredictionRecord, bool) {
	record, ok := s.records[strings.ToUpper(ticker)]
	return record, ok
}

func (s *mutableWarningStore) History(
	ticker string,
	limit int,
) ([]warnings.WarningHistoryRecord, error) {
	if limit < 1 {
		return []warnings.WarningHistoryRecord{}, nil
	}
	record, ok := s.FindTicker(ticker)
	if !ok {
		return []warnings.WarningHistoryRecord{}, nil
	}
	return []warnings.WarningHistoryRecord{warnings.HistoryRecordFromPrediction(record)}, nil
}

func (s *mutableWarningStore) Refresh() error {
	return nil
}

func (s *mutableWarningStore) Status() warnings.StoreStatus {
	return s.status
}

func (s *mutableWarningStore) setRecord(record warnings.PredictionRecord) {
	s.records[strings.ToUpper(record.Ticker)] = record
	s.batch.Records = []warnings.PredictionRecord{record}
	s.batch.RecordCount = 1
	s.status.WarningsLoaded = true
	s.status.RecordCount = 1
}

type fakeOnDemandAnalyzer struct {
	calls     []string
	err       error
	onAnalyze func(ticker string)
}

func (a *fakeOnDemandAnalyzer) Analyze(_ context.Context, ticker string) error {
	a.calls = append(a.calls, ticker)
	if a.err != nil {
		return a.err
	}
	if a.onAnalyze != nil {
		a.onAnalyze(ticker)
	}
	return nil
}
