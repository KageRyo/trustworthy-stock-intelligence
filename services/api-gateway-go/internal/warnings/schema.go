package warnings

type PredictionBatch struct {
	GeneratedAt string             `json:"generated_at"`
	RecordCount int                `json:"record_count"`
	Records     []PredictionRecord `json:"records"`
}

type PredictionRecord struct {
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
