package apihttp

import (
	"strings"

	"github.com/KageRyo/trustworthy-stock-intelligence/services/api-gateway-go/internal/warnings"
)

const analysisSchemaVersion = "analysis.v1"

type TickerAnalysisResponse struct {
	SchemaVersion string              `json:"schema_version"`
	Ticker        string              `json:"ticker"`
	Date          string              `json:"date"`
	RunID         string              `json:"run_id"`
	DataAsOf      string              `json:"data_as_of"`
	GeneratedAt   string              `json:"generated_at"`
	Warning       WarningAnalysis     `json:"warning"`
	Trust         TrustAssessment     `json:"trust"`
	Model         ModelAnalysis       `json:"model"`
	DataFreshness DataFreshness       `json:"data_freshness"`
	Reasons       []ReasonExplanation `json:"reasons"`
	Limitations   []string            `json:"limitations"`
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
	Summary           string  `json:"summary"`
}

type ModelAnalysis struct {
	Name        string `json:"name"`
	ModelBundle string `json:"model_bundle"`
}

type DataFreshness struct {
	DataAsOf       string `json:"data_as_of"`
	GeneratedAt    string `json:"generated_at"`
	LastLoadedAt   string `json:"last_loaded_at"`
	FileModifiedAt string `json:"file_modified_at"`
	RecordCount    int    `json:"record_count"`
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
) TickerAnalysisResponse {
	runID := valueOrDefault(record.RunID, status.RunID)
	dataAsOf := valueOrDefault(record.DataAsOf, status.DataAsOf)
	generatedAt := valueOrDefault(record.GeneratedAt, status.GeneratedAt)
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
			Summary:           trustSummary(record),
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
		},
		Reasons:     explainReasonCodes(record.ReasonCodes),
		Limitations: analysisLimitations(),
	}
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
		return "Model uncertainty is too high for a confident warning decision."
	case "no_alert":
		return "No material drawdown-risk warning in the latest precomputed batch."
	default:
		return "Warning level is unknown for the latest precomputed batch."
	}
}

func trustSummary(record warnings.PredictionRecord) string {
	if hasReason(record.ReasonCodes, "uncertainty_above_threshold") {
		return "Uncertainty is above the configured threshold, so the model output should be treated cautiously."
	}
	if hasReason(record.ReasonCodes, "trust_above_alert_threshold") {
		return "Trust score is above the configured alert threshold for this batch."
	}
	if hasReason(record.ReasonCodes, "trust_below_alert_threshold") {
		return "Trust score is below the configured alert threshold for this batch."
	}
	return "Trust assessment is based on calibrated probability and uncertainty for this batch."
}

func trustStatus(reasonCodes []string) string {
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
