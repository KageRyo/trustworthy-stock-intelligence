package warnings

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func writeTestBatch(t *testing.T) string {
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

func TestFileStoreLoadsPredictionBatch(t *testing.T) {
	store, err := NewFileStore(writeTestBatch(t))
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}

	batch := store.Batch()

	if batch.RecordCount != 2 {
		t.Fatalf("record_count = %d, want 2", batch.RecordCount)
	}
	if batch.SchemaVersion != "v1" || batch.RunID != "fixture_run" || batch.DataAsOf != "2026-06-08" {
		t.Fatalf("unexpected contract metadata: %+v", batch)
	}
	if batch.Records[0].Ticker != "AAPL" {
		t.Fatalf("first ticker = %q, want AAPL", batch.Records[0].Ticker)
	}
}

func TestDecodeCalibrationDriftReadsBatchMetadata(t *testing.T) {
	metadata, err := decodeCalibrationDrift([]byte(`{
    "source_schema": "v1",
    "calibration_drift": {
      "status": "degraded",
      "method": "calibration_drift_gate_v1",
      "signals": ["event_rate_shift"],
      "degraded": true,
      "abstain": false,
      "trust_multiplier": 0.5,
      "calibration_rows": 63,
      "recent_rows": 21,
      "note": "fixture"
    }
  }`))
	if err != nil {
		t.Fatalf("decodeCalibrationDrift returned error: %v", err)
	}
	if metadata.Status != "degraded" || metadata.TrustMultiplier != 0.5 {
		t.Fatalf("unexpected drift metadata: %+v", metadata)
	}
	if len(metadata.Signals) != 1 || metadata.Signals[0] != "event_rate_shift" {
		t.Fatalf("unexpected drift signals: %+v", metadata.Signals)
	}
}

func TestPredictionBatchJSONIncludesCalibrationDrift(t *testing.T) {
	batch := PredictionBatch{
		SchemaVersion: "v1",
		RunID:         "run",
		CalibrationDrift: CalibrationDriftMetadata{
			Status:          "stable",
			Method:          "calibration_drift_gate_v1",
			Signals:         []string{},
			TrustMultiplier: 1.0,
		},
		Records: []PredictionRecord{},
	}
	payload, err := json.Marshal(batch)
	if err != nil {
		t.Fatalf("marshal batch: %v", err)
	}
	if !strings.Contains(string(payload), `"calibration_drift"`) {
		t.Fatalf("batch JSON missing calibration_drift: %s", payload)
	}
}

func TestFileStoreFindsTickerCaseInsensitively(t *testing.T) {
	store, err := NewFileStore(writeTestBatch(t))
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}

	record, ok := store.FindTicker("aapl")

	if !ok {
		t.Fatal("expected to find AAPL")
	}
	if record.WarningLevel != "watch" {
		t.Fatalf("warning level = %q, want watch", record.WarningLevel)
	}
}

func TestFileStoreRejectsMissingFile(t *testing.T) {
	_, err := NewFileStore(filepath.Join(t.TempDir(), "missing.json"))

	if err == nil {
		t.Fatal("expected missing file error")
	}
}

func TestFileStoreRefreshReloadsWhenFileChanges(t *testing.T) {
	path := writeTestBatch(t)
	store, err := NewFileStore(path)
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}
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

	if err := store.Refresh(); err != nil {
		t.Fatalf("Refresh returned error: %v", err)
	}
	record, ok := store.FindTicker("NVDA")

	if !ok {
		t.Fatal("expected to find reloaded NVDA record")
	}
	if record.WarningLevel != "alert" {
		t.Fatalf("warning level = %q, want alert", record.WarningLevel)
	}
}

func TestFileStoreRefreshKeepsOldBatchOnInvalidReload(t *testing.T) {
	path := writeTestBatch(t)
	store, err := NewFileStore(path)
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}
	if err := os.WriteFile(path, []byte(`{"record_count": 1, "records": [`), 0o644); err != nil {
		t.Fatalf("write broken fixture: %v", err)
	}
	if err := os.Chtimes(path, time.Now().Add(time.Second), time.Now().Add(time.Second)); err != nil {
		t.Fatalf("update mtime: %v", err)
	}

	if err := store.Refresh(); err == nil {
		t.Fatal("expected refresh error for invalid JSON")
	}
	record, ok := store.FindTicker("AAPL")
	status := store.Status()

	if !ok {
		t.Fatal("expected old AAPL record to remain available")
	}
	if record.WarningLevel != "watch" {
		t.Fatalf("warning level = %q, want watch", record.WarningLevel)
	}
	if status.LastError == "" {
		t.Fatal("expected status to record last reload error")
	}
}

func TestFileStoreStatusReportsLoadedBatch(t *testing.T) {
	store, err := NewFileStore(writeTestBatch(t))
	if err != nil {
		t.Fatalf("NewFileStore returned error: %v", err)
	}

	status := store.Status()

	if !status.WarningsLoaded {
		t.Fatal("expected warnings_loaded to be true")
	}
	if status.RecordCount != 2 {
		t.Fatalf("record_count = %d, want 2", status.RecordCount)
	}
	if status.SchemaVersion != "v1" || status.RunID != "fixture_run" || status.DataAsOf != "2026-06-08" {
		t.Fatalf("unexpected contract metadata: %+v", status)
	}
	if status.GeneratedAt == "" || status.LastLoadedAt == "" || status.FileModifiedAt == "" {
		t.Fatalf("expected generated_at, last_loaded_at, and file_modified_at in status: %+v", status)
	}
}
