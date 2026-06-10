package warnings

import (
	"os"
	"path/filepath"
	"testing"
)

func writeTestBatch(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "latest_warnings.json")
	payload := `{
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
	if batch.Records[0].Ticker != "AAPL" {
		t.Fatalf("first ticker = %q, want AAPL", batch.Records[0].Ticker)
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
