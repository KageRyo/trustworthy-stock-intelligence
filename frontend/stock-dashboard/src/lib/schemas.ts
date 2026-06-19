import { z } from "zod";

export const warningLevelSchema = z.enum(["alert", "watch", "abstain", "no_alert"]);

export const reasonExplanationSchema = z
  .object({
    code: z.string(),
    severity: z.enum(["info", "watch", "alert"]),
    title: z.string(),
    detail: z.string()
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

export const dataFreshnessSchema = z
  .object({
    data_as_of: z.string(),
    generated_at: z.string(),
    last_loaded_at: z.string(),
    file_modified_at: z.string(),
    record_count: z.number().int().nonnegative()
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
    reasons: z.array(reasonExplanationSchema),
    limitations: z.array(z.string())
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
    reason_codes: z.array(z.string())
  })
  .strict();

export const predictionBatchSchema = z
  .object({
    schema_version: z.string(),
    run_id: z.string(),
    data_as_of: z.string(),
    generated_at: z.string(),
    record_count: z.number().int().nonnegative(),
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
export type ReasonExplanation = z.infer<typeof reasonExplanationSchema>;
export type TickerAnalysis = z.infer<typeof tickerAnalysisSchema>;
export type PredictionRecord = z.infer<typeof predictionRecordSchema>;
export type PredictionBatch = z.infer<typeof predictionBatchSchema>;
export type TickerSummary = z.infer<typeof tickerSummarySchema>;
export type TickerList = z.infer<typeof tickerListSchema>;
export type APIStatus = z.infer<typeof statusSchema>;
export type CurrentModel = z.infer<typeof currentModelSchema>;
export type APIError = z.infer<typeof apiErrorSchema>;
