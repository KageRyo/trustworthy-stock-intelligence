import { describe, expect, it } from "vitest";
import {
  analysisDataState,
  analysisTrustState,
  coverageStateForTicker,
  isPendingPredictionJob,
  providerStateForTicker
} from "./dashboardState";
import type { PredictionJob, ProviderHealthRecord, TickerAnalysis } from "./schemas";

function analysis(overrides: Partial<TickerAnalysis> = {}): TickerAnalysis {
  return {
    schema_version: "analysis.v1",
    ticker: "NVDA",
    date: "2026-08-13",
    run_id: "run-1",
    data_as_of: "2026-08-13T00:00:00Z",
    generated_at: "2026-08-13T00:01:00Z",
    warning: {
      level: "watch",
      risk_probability: 0.4,
      calibrated_risk_probability: 0.3,
      alert_threshold: 0.5,
      watch_threshold: 0.2,
      summary: "watch"
    },
    trust: {
      trust_score: 0.8,
      uncertainty_score: 0.2,
      calibration_method: "platt",
      trust_status: "trusted_for_alert",
      uncertainty_status: "acceptable_uncertainty",
      summary: "trusted"
    },
    model: { name: "baseline", model_bundle: "bundle" },
    data_freshness: {
      data_as_of: "2026-08-13T00:00:00Z",
      generated_at: "2026-08-13T00:01:00Z",
      last_loaded_at: "2026-08-13T00:01:00Z",
      file_modified_at: "2026-08-13T00:01:00Z",
      record_count: 1,
      freshness: {
        schema_version: "freshness.v1",
        market: "us",
        interval: "1d",
        data_as_of: "2026-08-13T00:00:00Z",
        evaluated_at: "2026-08-13T00:01:00Z",
        age_seconds: 60,
        fresh_within_seconds: 86400,
        stale_within_seconds: 172800,
        state: "fresh",
        action: "allow",
        reason_code: "freshness_fresh",
        message: "fresh"
      }
    },
    calibration_drift: {
      status: "stable",
      method: "gate",
      event_rate_delta: null,
      ece_delta: null,
      brier_delta: null,
      signals: [],
      degraded: false,
      abstain: false,
      trust_multiplier: 1,
      calibration_rows: 1,
      recent_rows: 1,
      note: "stable"
    },
    reasons: [],
    feature_attributions: [],
    limitations: [],
    ...overrides
  };
}

function health(status: ProviderHealthRecord["status"], coverage: ProviderHealthRecord["coverage"]): ProviderHealthRecord {
  return {
    schema_version: "provider_health.v1",
    provider: "twse",
    market: "taiwan",
    ticker: "2330",
    query_symbol: "2330.TW",
    status,
    coverage,
    attempt_count: 1,
    success_count: status === "healthy" ? 1 : 0,
    failure_count: status === "healthy" ? 0 : 1,
    consecutive_failures: status === "healthy" ? 0 : 1,
    observed_at: "2026-08-13T00:00:00Z"
  };
}

function job(status: PredictionJob["status"]): PredictionJob {
  return {
    schema_version: "prediction_job.v1",
    id: "job-1",
    idempotency_key: "key-1",
    ticker: "NVDA",
    market: "auto",
    feature_interval: "1d",
    status,
    attempt_count: 0,
    max_attempts: 3,
    available_at: "2026-08-13T00:00:00Z",
    enqueued_at: "2026-08-13T00:00:00Z",
    created_at: "2026-08-13T00:00:00Z",
    updated_at: "2026-08-13T00:00:00Z"
  };
}

describe("dashboard operational state helpers", () => {
  it("distinguishes fresh, stale, and unusable data", () => {
    expect(analysisDataState(analysis())).toBe("fresh");
    expect(analysisDataState(analysis({
      data_freshness: {
        ...analysis().data_freshness,
        freshness: { ...analysis().data_freshness.freshness, state: "stale", action: "downgrade", reason_code: "freshness_stale" }
      }
    }))).toBe("stale");
    expect(analysisDataState(analysis({
      data_freshness: {
        ...analysis().data_freshness,
        freshness: { ...analysis().data_freshness.freshness, state: "unusable", action: "block", reason_code: "freshness_unusable" }
      }
    }))).toBe("unusable");
  });

  it("makes limited trust and abstention explicit", () => {
    expect(analysisTrustState(analysis())).toBe("trusted");
    expect(analysisTrustState(analysis({ trust: { ...analysis().trust, trust_status: "limited_trust" } }))).toBe("limited");
    expect(analysisTrustState(analysis({ warning: { ...analysis().warning, level: "abstain" } }))).toBe("abstain");
  });

  it("selects the worst provider and coverage state for a ticker", () => {
    const records = [health("healthy", "available"), health("degraded", "partial")];
    expect(providerStateForTicker(records, "2330")).toBe("degraded");
    expect(coverageStateForTicker(records, "2330")).toBe("partial");
    expect(providerStateForTicker(records, "NVDA")).toBe("unknown");
  });

  it("recognizes queued and running jobs as pending", () => {
    expect(isPendingPredictionJob(job("queued"))).toBe(true);
    expect(isPendingPredictionJob(job("running"))).toBe(true);
    expect(isPendingPredictionJob(job("completed"))).toBe(false);
    expect(isPendingPredictionJob(null)).toBe(false);
  });
});
