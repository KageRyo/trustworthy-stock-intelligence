package warnings

type PredictionBatch struct {
	SchemaVersion    string                   `json:"schema_version"`
	RunID            string                   `json:"run_id"`
	DataAsOf         string                   `json:"data_as_of"`
	GeneratedAt      string                   `json:"generated_at"`
	RecordCount      int                      `json:"record_count"`
	CalibrationDrift CalibrationDriftMetadata `json:"calibration_drift"`
	Records          []PredictionRecord       `json:"records"`
}

type CalibrationDriftMetadata struct {
	Status          string   `json:"status"`
	Method          string   `json:"method"`
	EventRateDelta  *float64 `json:"event_rate_delta"`
	ECEDelta        *float64 `json:"ece_delta"`
	BrierDelta      *float64 `json:"brier_delta"`
	Signals         []string `json:"signals"`
	Degraded        bool     `json:"degraded"`
	Abstain         bool     `json:"abstain"`
	TrustMultiplier float64  `json:"trust_multiplier"`
	CalibrationRows int      `json:"calibration_rows"`
	RecentRows      int      `json:"recent_rows"`
	Note            string   `json:"note"`
}

type PredictionRecord struct {
	RunID                     string               `json:"-"`
	DataAsOf                  string               `json:"-"`
	GeneratedAt               string               `json:"-"`
	Date                      string               `json:"date"`
	Ticker                    string               `json:"ticker"`
	Model                     string               `json:"model"`
	ModelBundle               string               `json:"model_bundle"`
	RiskProbability           float64              `json:"risk_probability"`
	CalibratedRiskProbability float64              `json:"calibrated_risk_probability"`
	CalibrationMethod         string               `json:"calibration_method"`
	UncertaintyScore          float64              `json:"uncertainty_score"`
	TrustScore                float64              `json:"trust_score"`
	AlertThreshold            float64              `json:"alert_threshold"`
	WatchThreshold            float64              `json:"watch_threshold"`
	WarningLevel              string               `json:"warning_level"`
	ReasonCodes               []string             `json:"reason_codes"`
	FeatureAttributions       []FeatureAttribution `json:"feature_attributions"`
}

type FeatureAttribution struct {
	Feature      string   `json:"feature"`
	Value        *float64 `json:"value"`
	Contribution float64  `json:"contribution"`
	Direction    string   `json:"direction"`
	Method       string   `json:"method"`
}

// ProviderHealthRecord is the schema-first serving representation of the
// latest provider/ticker observation retained by PostgreSQL.
type ProviderHealthRecord struct {
	SchemaVersion       string   `json:"schema_version"`
	Provider            string   `json:"provider"`
	Market              string   `json:"market"`
	Ticker              string   `json:"ticker"`
	QuerySymbol         string   `json:"query_symbol"`
	Status              string   `json:"status"`
	Coverage            string   `json:"coverage"`
	AttemptCount        int      `json:"attempt_count"`
	SuccessCount        int      `json:"success_count"`
	FailureCount        int      `json:"failure_count"`
	ConsecutiveFailures int      `json:"consecutive_failures"`
	LastSuccessAt       string   `json:"last_success_at,omitempty"`
	LastFailureAt       string   `json:"last_failure_at,omitempty"`
	LastLatencyMs       *float64 `json:"last_latency_ms,omitempty"`
	LastErrorCode       string   `json:"last_error_code,omitempty"`
	LastErrorMessage    string   `json:"last_error_message,omitempty"`
	ObservedAt          string   `json:"observed_at"`
}

// WarningHistoryRecord is the public, schema-first representation of one
// historical warning observation. It repeats the prediction fields so that a
// timeline response is self-contained and does not rely on private store
// metadata from PredictionRecord.
type WarningHistoryRecord struct {
	RunID                     string   `json:"run_id"`
	DataAsOf                  string   `json:"data_as_of"`
	GeneratedAt               string   `json:"generated_at"`
	Date                      string   `json:"date"`
	Ticker                    string   `json:"ticker"`
	Model                     string   `json:"model"`
	ModelBundle               string   `json:"model_bundle"`
	RiskProbability           float64  `json:"risk_probability"`
	CalibratedRiskProbability float64  `json:"calibrated_risk_probability"`
	CalibrationMethod         string   `json:"calibration_method"`
	UncertaintyScore          float64  `json:"uncertainty_score"`
	TrustScore                float64  `json:"trust_score"`
	AlertThreshold            float64  `json:"alert_threshold"`
	WatchThreshold            float64  `json:"watch_threshold"`
	WarningLevel              string   `json:"warning_level"`
	ReasonCodes               []string `json:"reason_codes"`
}

func HistoryRecordFromPrediction(record PredictionRecord) WarningHistoryRecord {
	return WarningHistoryRecord{
		RunID:                     record.RunID,
		DataAsOf:                  record.DataAsOf,
		GeneratedAt:               record.GeneratedAt,
		Date:                      record.Date,
		Ticker:                    record.Ticker,
		Model:                     record.Model,
		ModelBundle:               record.ModelBundle,
		RiskProbability:           record.RiskProbability,
		CalibratedRiskProbability: record.CalibratedRiskProbability,
		CalibrationMethod:         record.CalibrationMethod,
		UncertaintyScore:          record.UncertaintyScore,
		TrustScore:                record.TrustScore,
		AlertThreshold:            record.AlertThreshold,
		WatchThreshold:            record.WatchThreshold,
		WarningLevel:              record.WarningLevel,
		ReasonCodes:               append([]string(nil), record.ReasonCodes...),
	}
}
