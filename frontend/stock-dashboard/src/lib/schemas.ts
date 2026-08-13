import { z } from "zod";

export const warningLevelSchema = z.enum(["alert", "watch", "abstain", "no_alert"]);

export const calibrationDriftSchema = z
  .object({
    status: z.enum(["not_evaluated", "stable", "degraded"]),
    method: z.string(),
    event_rate_delta: z.number().nullable(),
    ece_delta: z.number().nullable(),
    brier_delta: z.number().nullable(),
    signals: z.array(z.string()),
    degraded: z.boolean(),
    abstain: z.boolean(),
    trust_multiplier: z.number().min(0).max(1),
    calibration_rows: z.number().int().nonnegative(),
    recent_rows: z.number().int().nonnegative(),
    note: z.string()
  })
  .strict();

export const reasonExplanationSchema = z
  .object({
    code: z.string(),
    severity: z.enum(["info", "watch", "alert"]),
    title: z.string(),
    detail: z.string()
  })
  .strict();

export const featureAttributionSchema = z
  .object({
    feature: z.string(),
    value: z.number().nullable(),
    contribution: z.number(),
    direction: z.enum(["positive", "negative", "neutral"]),
    method: z.string()
  })
  .strict();

export const warningAnalysisSchema = z
  .object({
    level: warningLevelSchema,
    risk_probability: z.number().min(0).max(1),
    calibrated_risk_probability: z.number().min(0).max(1),
    alert_threshold: z.number().min(0).max(1),
    watch_threshold: z.number().min(0).max(1),
    summary: z.string()
  })
  .strict();

export const trustAssessmentSchema = z
  .object({
    trust_score: z.number().min(0).max(1),
    uncertainty_score: z.number().min(0).max(1),
    calibration_method: z.string(),
    trust_status: z.string(),
    uncertainty_status: z.string(),
    summary: z.string()
  })
  .strict();

export const modelAnalysisSchema = z
  .object({
    name: z.string(),
    model_bundle: z.string()
  })
  .strict();

export const freshnessAssessmentSchema = z
  .object({
    schema_version: z.literal("freshness.v1"),
    market: z.string(),
    interval: z.enum(["1m", "5m", "1d"]),
    data_as_of: z.string(),
    evaluated_at: z.string(),
    age_seconds: z.number().nonnegative().optional(),
    fresh_within_seconds: z.number().int().nonnegative(),
    stale_within_seconds: z.number().int().nonnegative(),
    state: z.enum(["fresh", "stale", "unusable"]),
    action: z.enum(["allow", "downgrade", "block"]),
    reason_code: z.enum([
      "freshness_fresh",
      "freshness_stale",
      "freshness_unusable",
      "freshness_missing_data_as_of",
      "freshness_future_data_as_of"
    ]),
    warning_level_override: z.literal("abstain").optional(),
    message: z.string()
  })
  .strict();

export const dataFreshnessSchema = z
  .object({
    data_as_of: z.string(),
    generated_at: z.string(),
    last_loaded_at: z.string(),
    file_modified_at: z.string(),
    record_count: z.number().int().nonnegative(),
    freshness: freshnessAssessmentSchema
  })
  .strict();

export const tickerAnalysisSchema = z
  .object({
    schema_version: z.literal("analysis.v1"),
    ticker: z.string(),
    date: z.string(),
    run_id: z.string(),
    data_as_of: z.string(),
    generated_at: z.string(),
    warning: warningAnalysisSchema,
    trust: trustAssessmentSchema,
    model: modelAnalysisSchema,
    data_freshness: dataFreshnessSchema,
    calibration_drift: calibrationDriftSchema,
    reasons: z.array(reasonExplanationSchema),
    feature_attributions: z.array(featureAttributionSchema).optional(),
    limitations: z.array(z.string())
  })
  .strict();

export const warningHistoryRecordSchema = z
  .object({
    run_id: z.string(),
    data_as_of: z.string(),
    generated_at: z.string(),
    date: z.string(),
    ticker: z.string(),
    model: z.string(),
    model_bundle: z.string(),
    risk_probability: z.number().min(0).max(1),
    calibrated_risk_probability: z.number().min(0).max(1),
    calibration_method: z.string(),
    uncertainty_score: z.number().min(0).max(1),
    trust_score: z.number().min(0).max(1),
    alert_threshold: z.number().min(0).max(1),
    watch_threshold: z.number().min(0).max(1),
    warning_level: warningLevelSchema,
    reason_codes: z.array(z.string())
  })
  .strict();

export const warningHistorySchema = z
  .object({
    schema_version: z.literal("warning_history.v1"),
    ticker: z.string(),
    record_count: z.number().int().nonnegative(),
    records: z.array(warningHistoryRecordSchema)
  })
  .strict();

export const warningTransitionTypeSchema = z.enum([
  "new_watch",
  "new_alert",
  "upgraded",
  "downgraded",
  "resolved",
  "persistent_alert",
  "low_trust_warning"
]);

export const warningTransitionSchema = z
  .object({
    schema_version: z.literal("warning_transition.v1"),
    id: z.string(),
    ticker: z.string(),
    transition_type: warningTransitionTypeSchema,
    previous_warning_level: warningLevelSchema.optional(),
    current_warning_level: warningLevelSchema,
    previous_run_id: z.string().optional(),
    current_run_id: z.string(),
    previous_batch_id: z.string().optional(),
    current_batch_id: z.string(),
    detected_at: z.string(),
    deduplication_key: z.string()
  })
  .strict();

export const warningTransitionsSchema = z
  .object({
    schema_version: z.literal("warning_transition.v1"),
    ticker: z.string(),
    record_count: z.number().int().nonnegative(),
    transitions: z.array(warningTransitionSchema)
  })
  .strict();

export const predictionRecordSchema = z
  .object({
    date: z.string(),
    ticker: z.string(),
    model: z.string(),
    model_bundle: z.string(),
    risk_probability: z.number().min(0).max(1),
    calibrated_risk_probability: z.number().min(0).max(1),
    calibration_method: z.string(),
    uncertainty_score: z.number().min(0).max(1),
    trust_score: z.number().min(0).max(1),
    alert_threshold: z.number().min(0).max(1),
    watch_threshold: z.number().min(0).max(1),
    warning_level: warningLevelSchema,
    reason_codes: z.array(z.string()),
    feature_attributions: z.array(featureAttributionSchema).optional()
  })
  .strict();

export const predictionBatchSchema = z
  .object({
    schema_version: z.string(),
    run_id: z.string(),
    data_as_of: z.string(),
    generated_at: z.string(),
    feature_interval: z.enum(["1m", "5m", "1d"]).optional(),
    record_count: z.number().int().nonnegative(),
    calibration_drift: calibrationDriftSchema,
    records: z.array(predictionRecordSchema)
  })
  .strict();

export const tickerSummarySchema = z
  .object({
    ticker: z.string(),
    market: z.enum(["us", "taiwan", "unknown"]),
    date: z.string(),
    warning_level: warningLevelSchema,
    calibrated_risk_probability: z.number().min(0).max(1),
    trust_score: z.number().min(0).max(1)
  })
  .strict();

export const tickerListSchema = z
  .object({
    schema_version: z.literal("ticker_list.v1"),
    run_id: z.string(),
    data_as_of: z.string(),
    generated_at: z.string(),
    record_count: z.number().int().nonnegative(),
    tickers: z.array(tickerSummarySchema)
  })
  .strict();

export const watchlistLatestWarningSchema = z
  .object({
    date: z.string(),
    warning_level: warningLevelSchema,
    calibrated_risk_probability: z.number().min(0).max(1),
    trust_score: z.number().min(0).max(1)
  })
  .strict();

export const watchlistTickerSchema = z
  .object({
    ticker: z.string(),
    query_symbol: z.string(),
    market: z.enum(["us", "twse", "tpex", "emerging", "taiwan", "unknown"]),
    added_at: z.string(),
    notes: z.string(),
    has_latest_warning: z.boolean(),
    latest_warning: watchlistLatestWarningSchema.optional()
  })
  .strict();

export const watchlistSchema = z
  .object({
    schema_version: z.literal("watchlist.v1"),
    name: z.string(),
    record_count: z.number().int().nonnegative(),
    updated_at: z.string(),
    tickers: z.array(watchlistTickerSchema)
  })
  .strict();

export const statusSchema = z
  .object({
    warnings_path: z.string(),
    warnings_loaded: z.boolean(),
    schema_version: z.string(),
    run_id: z.string(),
    data_as_of: z.string(),
    generated_at: z.string(),
    record_count: z.number().int().nonnegative(),
    last_loaded_at: z.string(),
    file_modified_at: z.string(),
    last_error: z.string().optional()
  })
  .strict();

export const currentModelSchema = z
  .object({
    schema_version: z.string(),
    run_id: z.string(),
    data_as_of: z.string(),
    model: z.string(),
    model_bundle: z.string(),
    generated_at: z.string(),
    record_count: z.number().int().nonnegative()
  })
  .strict();

export const providerHealthStatusSchema = z.enum(["healthy", "degraded", "unavailable"]);
export const providerCoverageStatusSchema = z.enum(["available", "partial", "unavailable", "unknown"]);

export const providerHealthRecordSchema = z
  .object({
    schema_version: z.literal("provider_health.v1"),
    provider: z.string(),
    market: z.string(),
    ticker: z.string(),
    query_symbol: z.string(),
    status: providerHealthStatusSchema,
    coverage: providerCoverageStatusSchema,
    attempt_count: z.number().int().nonnegative(),
    success_count: z.number().int().nonnegative(),
    failure_count: z.number().int().nonnegative(),
    consecutive_failures: z.number().int().nonnegative(),
    last_success_at: z.string().optional(),
    last_failure_at: z.string().optional(),
    last_latency_ms: z.number().nonnegative().optional(),
    last_error_code: z.string().optional(),
    last_error_message: z.string().optional(),
    observed_at: z.string()
  })
  .strict();

export const providerHealthResponseSchema = z
  .object({
    schema_version: z.literal("provider_health.v1"),
    generated_at: z.string(),
    record_count: z.number().int().nonnegative(),
    records: z.array(providerHealthRecordSchema)
  })
  .strict();

export const predictionJobStatusSchema = z.enum([
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled"
]);

export const predictionJobFailureCodeSchema = z.enum([
  "provider_unavailable",
  "insufficient_history",
  "prediction_failed",
  "stale_data",
  "unsupported_market",
  "unsupported_interval",
  "database_error",
  "worker_error",
  "unknown"
]);

export const predictionJobSchema = z
  .object({
    schema_version: z.literal("prediction_job.v1"),
    id: z.string(),
    idempotency_key: z.string(),
    ticker: z.string(),
    market: z.enum(["auto", "us", "twse", "tpex", "emerging"]),
    feature_interval: z.enum(["1m", "5m", "1d"]),
    status: predictionJobStatusSchema,
    attempt_count: z.number().int().nonnegative(),
    max_attempts: z.number().int().positive(),
    available_at: z.string(),
    enqueued_at: z.string(),
    started_at: z.string().optional(),
    completed_at: z.string().optional(),
    worker_id: z.string().optional(),
    locked_at: z.string().optional(),
    prediction_batch_id: z.string().optional(),
    result_run_id: z.string().optional(),
    failure_code: predictionJobFailureCodeSchema.optional(),
    failure_message: z.string().optional(),
    request_payload: z.record(z.string(), z.unknown()).optional(),
    created_at: z.string(),
    updated_at: z.string()
  })
  .strict();

export const predictionJobResponseSchema = z
  .object({
    schema_version: z.literal("prediction_job.v1"),
    job: predictionJobSchema
  })
  .strict();

export const apiErrorSchema = z
  .object({
    error: z
      .object({
        code: z.string(),
        message: z.string()
      })
      .strict()
  })
  .strict();

export type WarningLevel = z.infer<typeof warningLevelSchema>;
export type CalibrationDriftMetadata = z.infer<typeof calibrationDriftSchema>;
export type ReasonExplanation = z.infer<typeof reasonExplanationSchema>;
export type FeatureAttribution = z.infer<typeof featureAttributionSchema>;
export type FreshnessAssessment = z.infer<typeof freshnessAssessmentSchema>;
export type TickerAnalysis = z.infer<typeof tickerAnalysisSchema>;
export type WarningHistory = z.infer<typeof warningHistorySchema>;
export type WarningHistoryRecord = z.infer<typeof warningHistoryRecordSchema>;
export type WarningTransition = z.infer<typeof warningTransitionSchema>;
export type WarningTransitions = z.infer<typeof warningTransitionsSchema>;
export type PredictionRecord = z.infer<typeof predictionRecordSchema>;
export type PredictionBatch = z.infer<typeof predictionBatchSchema>;
export type TickerSummary = z.infer<typeof tickerSummarySchema>;
export type TickerList = z.infer<typeof tickerListSchema>;
export type Watchlist = z.infer<typeof watchlistSchema>;
export type WatchlistTicker = z.infer<typeof watchlistTickerSchema>;
export type APIStatus = z.infer<typeof statusSchema>;
export type CurrentModel = z.infer<typeof currentModelSchema>;
export type ProviderHealthRecord = z.infer<typeof providerHealthRecordSchema>;
export type ProviderHealthResponse = z.infer<typeof providerHealthResponseSchema>;
export type PredictionJob = z.infer<typeof predictionJobSchema>;
export type PredictionJobResponse = z.infer<typeof predictionJobResponseSchema>;
export type APIError = z.infer<typeof apiErrorSchema>;
