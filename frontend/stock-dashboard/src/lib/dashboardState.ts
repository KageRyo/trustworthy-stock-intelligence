import type {
  PredictionJob,
  ProviderHealthRecord,
  TickerAnalysis
} from "./schemas";

export type AnalysisDataState = "fresh" | "stale" | "unusable" | "unknown";
export type TrustState = "trusted" | "limited" | "abstain" | "unknown";
export type ProviderState = "healthy" | "degraded" | "unavailable" | "unknown";
export type CoverageState = "available" | "partial" | "unavailable" | "unknown";

export function analysisDataState(analysis: TickerAnalysis | null): AnalysisDataState {
  return analysis?.data_freshness.freshness.state ?? "unknown";
}

export function analysisTrustState(analysis: TickerAnalysis | null): TrustState {
  if (!analysis) {
    return "unknown";
  }
  if (analysis.warning.level === "abstain" || analysis.data_freshness.freshness.action === "block") {
    return "abstain";
  }
  if (analysis.trust.trust_status === "limited_trust" || analysis.trust.uncertainty_status === "high_uncertainty") {
    return "limited";
  }
  if (analysis.trust.trust_status === "trusted_for_alert") {
    return "trusted";
  }
  return "unknown";
}

const providerStateRank: Record<ProviderState, number> = {
  unknown: 0,
  healthy: 1,
  degraded: 2,
  unavailable: 3
};

const coverageStateRank: Record<CoverageState, number> = {
  unknown: 0,
  available: 1,
  partial: 2,
  unavailable: 3
};

export function providerStateForTicker(
  records: ProviderHealthRecord[],
  ticker?: string
): ProviderState {
  const matching = recordsForTicker(records, ticker);
  return matching.reduce<ProviderState>(
    (worst, record) =>
      providerStateRank[record.status] > providerStateRank[worst] ? record.status : worst,
    "unknown"
  );
}

export function coverageStateForTicker(
  records: ProviderHealthRecord[],
  ticker?: string
): CoverageState {
  const matching = recordsForTicker(records, ticker);
  return matching.reduce<CoverageState>(
    (worst, record) =>
      coverageStateRank[record.coverage] > coverageStateRank[worst] ? record.coverage : worst,
    "unknown"
  );
}

export function recordsForTicker(records: ProviderHealthRecord[], ticker?: string): ProviderHealthRecord[] {
  const normalizedTicker = ticker?.trim().toUpperCase();
  if (!normalizedTicker) {
    return records;
  }
  return records.filter((record) => record.ticker.trim().toUpperCase() === normalizedTicker);
}

export function isPendingPredictionJob(job: PredictionJob | null): boolean {
  return job?.status === "queued" || job?.status === "running";
}
