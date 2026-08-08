package warnings

type PredictionBatch struct {
	SchemaVersion string             `json:"schema_version"`
	RunID         string             `json:"run_id"`
	DataAsOf      string             `json:"data_as_of"`
	GeneratedAt   string             `json:"generated_at"`
	RecordCount   int                `json:"record_count"`
	Records       []PredictionRecord `json:"records"`
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
