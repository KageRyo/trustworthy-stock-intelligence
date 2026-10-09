package apihttp

import (
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/freshness"
	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

const analysisSchemaVersion = "analysis.v1"

type TickerAnalysisResponse struct {
	SchemaVersion       string                            `json:"schema_version"`
	Ticker              string                            `json:"ticker"`
	Date                string                            `json:"date"`
	RunID               string                            `json:"run_id"`
	DataAsOf            string                            `json:"data_as_of"`
	GeneratedAt         string                            `json:"generated_at"`
	Warning             WarningAnalysis                   `json:"warning"`
	Trust               TrustAssessment                   `json:"trust"`
	Model               ModelAnalysis                     `json:"model"`
	DataFreshness       DataFreshness                     `json:"data_freshness"`
	Reasons             []ReasonExplanation               `json:"reasons"`
	FeatureAttributions []warnings.FeatureAttribution     `json:"feature_attributions"`
	CalibrationDrift    warnings.CalibrationDriftMetadata `json:"calibration_drift"`
	AlertPolicy         *warnings.AlertPolicyMetadata     `json:"alert_policy"`
	Limitations         []string                          `json:"limitations"`
}

type WarningAnalysis struct {
	Level                     string  `json:"level"`
	RiskProbability           float64 `json:"risk_probability"`
	CalibratedRiskProbability float64 `json:"calibrated_risk_probability"`
	AlertThreshold            float64 `json:"alert_threshold"`
	WatchThreshold            float64 `json:"watch_threshold"`
	Summary                   string  `json:"summary"`
}

type TrustAssessment struct {
	TrustScore        float64 `json:"trust_score"`
	UncertaintyScore  float64 `json:"uncertainty_score"`
	CalibrationMethod string  `json:"calibration_method"`
	TrustStatus       string  `json:"trust_status"`
	UncertaintyStatus string  `json:"uncertainty_status"`
	SummaryCode       string  `json:"summary_code"`
	Summary           string  `json:"summary"`
}

type ModelAnalysis struct {
	Name        string `json:"name"`
	ModelBundle string `json:"model_bundle"`
}

type DataFreshness struct {
	DataAsOf       string               `json:"data_as_of"`
	GeneratedAt    string               `json:"generated_at"`
	LastLoadedAt   string               `json:"last_loaded_at"`
	FileModifiedAt string               `json:"file_modified_at"`
	RecordCount    int                  `json:"record_count"`
	Freshness      freshness.Assessment `json:"freshness"`
}

type ReasonExplanation struct {
	Code     string `json:"code"`
	Severity string `json:"severity"`
	Title    string `json:"title"`
	Detail   string `json:"detail"`
}

func buildTickerAnalysis(
	record warnings.PredictionRecord,
	status warnings.StoreStatus,
	calibrationDrift warnings.CalibrationDriftMetadata,
	featureIntervals ...string,
) TickerAnalysisResponse {
	runID := valueOrDefault(record.RunID, status.RunID)
	dataAsOf := valueOrDefault(record.DataAsOf, status.DataAsOf)
	generatedAt := valueOrDefault(record.GeneratedAt, status.GeneratedAt)
	featureInterval := "1d"
	if len(featureIntervals) > 0 && strings.TrimSpace(featureIntervals[0]) != "" {
		featureInterval = featureIntervals[0]
	}
	freshnessAssessment := freshness.Assess(
		dataAsOf,
		"",
		inferTickerMarket(record.Ticker),
		featureInterval,
	)
	trustSummaryCode, trustSummaryText := trustSummary(record)
	return TickerAnalysisResponse{
		SchemaVersion: analysisSchemaVersion,
		Ticker:        record.Ticker,
		Date:          record.Date,
		RunID:         runID,
		DataAsOf:      dataAsOf,
		GeneratedAt:   generatedAt,
		Warning: WarningAnalysis{
			Level:                     record.WarningLevel,
			RiskProbability:           record.RiskProbability,
			CalibratedRiskProbability: record.CalibratedRiskProbability,
			AlertThreshold:            record.AlertThreshold,
			WatchThreshold:            record.WatchThreshold,
			Summary:                   warningSummary(record),
		},
		Trust: TrustAssessment{
			TrustScore:        record.TrustScore,
			UncertaintyScore:  record.UncertaintyScore,
			CalibrationMethod: record.CalibrationMethod,
			TrustStatus:       trustStatus(record.ReasonCodes),
			UncertaintyStatus: uncertaintyStatus(record.ReasonCodes),
			SummaryCode:       trustSummaryCode,
			Summary:           trustSummaryText,
		},
		Model: ModelAnalysis{
			Name:        record.Model,
			ModelBundle: record.ModelBundle,
		},
		DataFreshness: DataFreshness{
			DataAsOf:       dataAsOf,
			GeneratedAt:    generatedAt,
			LastLoadedAt:   status.LastLoadedAt,
			FileModifiedAt: status.FileModifiedAt,
			RecordCount:    status.RecordCount,
			Freshness:      freshnessAssessment,
		},
		CalibrationDrift:    calibrationDrift,
		Reasons:             explainReasonCodes(record.ReasonCodes),
		FeatureAttributions: nonNilFeatureAttributions(record.FeatureAttributions),
		Limitations:         analysisLimitations(),
	}
}

// analysisBatchMetadata returns the calibration-drift and alert-policy metadata of the
// batch that produced the record, falling back to the store-level batch when the store
// does not track per-record batches.
func analysisBatchMetadata(
	record warnings.PredictionRecord,
	batch warnings.PredictionBatch,
) (warnings.CalibrationDriftMetadata, *warnings.AlertPolicyMetadata) {
	if record.BatchMetadataLoaded {
		return record.BatchCalibrationDrift, record.BatchAlertPolicy
	}
	return batch.CalibrationDrift, batch.AlertPolicy
}

func nonNilFeatureAttributions(attributions []warnings.FeatureAttribution) []warnings.FeatureAttribution {
	if attributions == nil {
		return []warnings.FeatureAttribution{}
	}
	return attributions
}

func valueOrDefault(value string, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func warningSummary(record warnings.PredictionRecord) string {
	switch record.WarningLevel {
	case "alert":
		return "High calibrated drawdown-risk signal with enough trust to issue an alert."
	case "watch":
		return "Moderate or elevated drawdown-risk signal that should remain on watch."
	case "abstain":
		return "Model uncertainty or calibration drift is too high for a confident warning decision."
	case "no_alert":
		return "No material drawdown-risk warning in the latest precomputed batch."
	default:
		return "Warning level is unknown for the latest precomputed batch."
	}
}

// trustSummaryRule maps reason codes to a stable summary code for the dashboard to localize,
// plus an English fallback. Rules are checked in order and the first match wins.
type trustSummaryRule struct {
	reasonCodes []string
	code        string
	text        string
}

const trustSummaryDefaultCode = "default"

var trustSummaryRules = []trustSummaryRule{
	{
		[]string{"insufficient_history"},
		"insufficient_history",
		"The ticker has market data, but not enough labeled history for a calibrated risk prediction.",
	},
	{
		[]string{"calibration_drift_abstain"},
		"calibration_drift_abstain",
		"Calibration drift crossed the abstention gate, so this output is not reliable enough for a warning.",
	},
	{
		[]string{"calibration_drift_detected"},
		"calibration_drift_detected",
		"Calibration drift was detected and the trust score was reduced for this output.",
	},
	{
		[]string{"calibration_drift_not_evaluated"},
		"calibration_drift_not_evaluated",
		"Calibration drift was not evaluated because no later labeled window was available.",
	},
	{
		[]string{"reliability_unavailable"},
		"reliability_unavailable",
		"Reliability could not be assessed for this batch, so trust was set to zero.",
	},
	{
		[]string{"stale_ticker_data", "limited_data_quality"},
		"limited_data_quality",
		"Data quality is limited (short labeled history or stale bars), so trust was reduced.",
	},
	{
		[]string{"uncertainty_above_threshold"},
		"high_uncertainty",
		"Uncertainty is above the configured threshold, so the model output should be treated cautiously.",
	},
	{
		[]string{"trust_above_alert_threshold"},
		"trusted_for_alert",
		"Trust score is above the configured alert threshold for this batch.",
	},
	{
		[]string{"trust_below_alert_threshold"},
		"limited_trust",
		"Trust score is below the configured alert threshold for this batch.",
	},
}

// trustSummary returns the summary code and English text for the first matching rule.
func trustSummary(record warnings.PredictionRecord) (string, string) {
	for _, rule := range trustSummaryRules {
		for _, reasonCode := range rule.reasonCodes {
			if hasReason(record.ReasonCodes, reasonCode) {
				return rule.code, rule.text
			}
		}
	}
	return trustSummaryDefaultCode, "Trust assessment is based on data quality and calibration drift; uncertainty is reported separately."
}

func trustStatus(reasonCodes []string) string {
	if hasReason(reasonCodes, "calibration_drift_abstain") ||
		hasReason(reasonCodes, "calibration_drift_detected") ||
		hasReason(reasonCodes, "calibration_drift_not_evaluated") ||
		hasReason(reasonCodes, "limited_data_quality") ||
		hasReason(reasonCodes, "stale_ticker_data") ||
		hasReason(reasonCodes, "reliability_unavailable") {
		return "limited_trust"
	}
	if hasReason(reasonCodes, "trust_above_alert_threshold") {
		return "trusted_for_alert"
	}
	if hasReason(reasonCodes, "trust_below_alert_threshold") {
		return "limited_trust"
	}
	return "unknown"
}

func uncertaintyStatus(reasonCodes []string) string {
	if hasReason(reasonCodes, "uncertainty_above_threshold") {
		return "high_uncertainty"
	}
	if hasReason(reasonCodes, "uncertainty_below_threshold") {
		return "acceptable_uncertainty"
	}
	return "unknown"
}

func explainReasonCodes(reasonCodes []string) []ReasonExplanation {
	explanations := make([]ReasonExplanation, 0, len(reasonCodes))
	for _, code := range reasonCodes {
		explanations = append(explanations, explainReasonCode(code))
	}
	return explanations
}

func explainReasonCode(code string) ReasonExplanation {
	switch code {
	case "probability_above_alert_threshold":
		return ReasonExplanation{
			Code:     code,
			Severity: "alert",
			Title:    "Risk probability above alert threshold",
			Detail:   "The calibrated risk probability is at or above the configured alert threshold.",
		}
	case "probability_above_watch_threshold":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Risk probability above watch threshold",
			Detail:   "The calibrated risk probability is at or above the configured watch threshold.",
		}
	case "calibrated_probability_below_watch_threshold":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "Risk probability below watch threshold",
			Detail:   "The calibrated risk probability is below the configured watch threshold.",
		}
	case "trust_above_alert_threshold":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "Trust score above alert threshold",
			Detail:   "The trust score is high enough to support an alert decision.",
		}
	case "trust_below_alert_threshold":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Trust score below alert threshold",
			Detail:   "The trust score is not high enough to support an alert decision.",
		}
	case "uncertainty_above_threshold":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Uncertainty above threshold",
			Detail:   "The uncertainty score is above the configured threshold.",
		}
	case "uncertainty_below_threshold":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "Uncertainty below threshold",
			Detail:   "The uncertainty score is below the configured threshold.",
		}
	case "warning_level_alert":
		return ReasonExplanation{
			Code:     code,
			Severity: "alert",
			Title:    "Alert warning level",
			Detail:   "The final warning decision is alert.",
		}
	case "warning_level_watch":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Watch warning level",
			Detail:   "The final warning decision is watch.",
		}
	case "warning_level_abstain":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Abstain warning level",
			Detail:   "The final warning decision is abstain because confidence is limited.",
		}
	case "warning_level_no_alert":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "No alert warning level",
			Detail:   "The final warning decision is no alert.",
		}
	case "calibration_drift_not_evaluated":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Calibration drift not evaluated",
			Detail:   "No later labeled window was available, so serving could not check calibration drift.",
		}
	case "calibration_drift_stable":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "Calibration drift stable",
			Detail:   "The later labeled window did not cross the configured event-rate, ECE, or Brier drift thresholds.",
		}
	case "calibration_drift_detected":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Calibration drift detected",
			Detail:   "Calibration reliability degraded in the later labeled window, so trust was reduced.",
		}
	case "calibration_drift_event_rate_shift":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Event-rate shift",
			Detail:   "The later labeled event rate shifted beyond the configured calibration-drift threshold.",
		}
	case "calibration_drift_ece_increase":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Calibration error increased",
			Detail:   "The later window's expected calibration error increased beyond the configured threshold.",
		}
	case "calibration_drift_brier_increase":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Brier score degraded",
			Detail:   "The later window's Brier score increased beyond the configured threshold.",
		}
	case "calibration_drift_abstain":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Calibration drift abstention",
			Detail:   "Multiple calibration-drift signals crossed threshold, so the serving decision abstains.",
		}
	case "calibration_slope_nonpositive":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Recent ranking did not hold",
			Detail:   "In the calibration window, higher model scores did not mean more drawdowns. The model's ranking is kept and only its probability level is adjusted, so treat this ranking as unconfirmed.",
		}
	case "ensemble_disagreement_high":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Model refits disagree",
			Detail:   "Models refit on resampled market days disagree more than on most recent labeled rows, so treat the probability as less stable.",
		}
	case "input_out_of_distribution":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Unusual market conditions",
			Detail:   "The latest features are far from the training data. Historically these periods carried higher drawdown rates, so a low reading is not reassuring.",
		}
	case "limited_data_quality":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Limited data quality",
			Detail:   "The ticker has a short labeled history or stale bars, so trust was reduced.",
		}
	case "stale_ticker_data":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Stale ticker data",
			Detail:   "The ticker's latest bar is older than the latest bar in this batch.",
		}
	case "reliability_unavailable":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Reliability unavailable",
			Detail:   "Reliability signals could not be fitted (for example single-class history), so trust was set to zero.",
		}
	case "conformal_set_ambiguous":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "Outcomes not separable",
			Detail:   "The conformal prediction set contains both drawdown and no drawdown at the configured coverage.",
		}
	case "conformal_set_drawdown_only":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Conformal set: drawdown",
			Detail:   "At the configured coverage, the conformal prediction set contains only the drawdown outcome.",
		}
	case "conformal_set_no_drawdown_only":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "Conformal set: no drawdown",
			Detail:   "At the configured coverage, the conformal prediction set contains only the no-drawdown outcome.",
		}
	case "conformal_set_empty":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Conformal set empty",
			Detail:   "The conformal prediction set is empty, which indicates an unusual calibrated probability for this batch.",
		}
	case "conformal_set_unavailable":
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    "Conformal set unavailable",
			Detail:   "The calibration window did not contain both outcomes, so no conformal set was computed.",
		}
	case "insufficient_history":
		return ReasonExplanation{
			Code:     code,
			Severity: "watch",
			Title:    "Insufficient price history",
			Detail:   "The ticker has market data, but not enough labeled history for a calibrated risk prediction.",
		}
	default:
		return ReasonExplanation{
			Code:     code,
			Severity: "info",
			Title:    humanizeReasonCode(code),
			Detail:   "The model emitted this reason code in the latest warning batch.",
		}
	}
}

func hasReason(reasonCodes []string, target string) bool {
	for _, code := range reasonCodes {
		if code == target {
			return true
		}
	}
	return false
}

func humanizeReasonCode(code string) string {
	text := strings.ReplaceAll(strings.TrimSpace(code), "_", " ")
	if text == "" {
		return "Unknown reason code"
	}
	return strings.ToUpper(text[:1]) + text[1:]
}

func analysisLimitations() []string {
	return []string{
		"This is a drawdown-risk warning signal, not investment advice.",
		"When a ticker is missing, the API can trigger a configured on-demand market-data and prediction command before responding.",
		"Outputs depend on the supplied OHLCV data, model bundle, calibration, and thresholds.",
	}
}
