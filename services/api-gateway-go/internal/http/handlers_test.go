package apihttp

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
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
      "reason_codes": ["probability_above_watch_threshold"]
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
      "reason_codes": ["calibrated_probability_below_watch_threshold"]
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
	path := writeRouterFixture(t)
	store, err := warnings.NewFileStore(path)
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}
	return NewRouter(NewHandlers(store))
}

func getJSON(t *testing.T, router http.Handler, path string) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodGet, path, nil)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	return response
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
