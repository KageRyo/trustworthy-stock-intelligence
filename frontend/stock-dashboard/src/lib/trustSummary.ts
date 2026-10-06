import type { DashboardCopy } from "./i18n";

type ReasonCarrier = { reasons: ReadonlyArray<{ code: string }> };

export function hasReason(analysis: ReasonCarrier, code: string): boolean {
  return analysis.reasons.some((reason) => reason.code === code);
}

export function localizedTrustSummary(analysis: ReasonCarrier, copy: DashboardCopy): string {
  if (hasReason(analysis, "insufficient_history")) {
    return copy.trustSummaries.insufficientHistory;
  }
  if (hasReason(analysis, "calibration_drift_abstain")) {
    return copy.trustSummaries.calibrationDriftAbstain;
  }
  if (hasReason(analysis, "calibration_drift_detected")) {
    return copy.trustSummaries.calibrationDriftDetected;
  }
  if (hasReason(analysis, "calibration_drift_not_evaluated")) {
    return copy.trustSummaries.calibrationDriftNotEvaluated;
  }
  if (hasReason(analysis, "reliability_unavailable")) {
    return copy.trustSummaries.reliabilityUnavailable;
  }
  if (hasReason(analysis, "stale_ticker_data") || hasReason(analysis, "limited_data_quality")) {
    return copy.trustSummaries.limitedDataQuality;
  }
  if (hasReason(analysis, "uncertainty_above_threshold")) {
    return copy.trustSummaries.highUncertainty;
  }
  if (hasReason(analysis, "trust_above_alert_threshold")) {
    return copy.trustSummaries.trustedForAlert;
  }
  if (hasReason(analysis, "trust_below_alert_threshold")) {
    return copy.trustSummaries.limitedTrust;
  }
  return copy.trustSummaries.default;
}
