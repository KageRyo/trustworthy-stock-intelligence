# Ticker Analysis API Contract

The ticker analysis API is a schema-first read model built on top of the
Python-generated warning records in PostgreSQL. When configured, the API can
delegate a missing ticker to the Python on-demand analysis command, refresh the
store, and then convert the resulting PostgreSQL `warning_records` row into a
typed, dashboard-oriented analysis response.

JSON examples and field tables in this document describe the owned response
schema. They should stay aligned with Go structs, OpenAPI, and frontend Zod
schemas.

## Endpoint

```text
GET /api/v1/analysis/{ticker}
```

Ticker lookup is case-insensitive. Missing tickers trigger on-demand analysis
when `TSI_ON_DEMAND_ANALYSIS_COMMAND` is configured. If the provider or model
pipeline cannot produce a record, the endpoint returns the standard API error
envelope.

If market data exists but the ticker does not have enough labeled history for a
calibrated prediction, the endpoint returns an `abstain` analysis with the
`insufficient_history` reason code. This keeps the response schema stable while
making the trust limitation explicit.

Taiwan local tickers are string symbols. Numeric and alphanumeric inputs such
as `0050`, `2330`, `00981A`, `02001L`, and TPEx emerging symbols such as `5240`
should not be coerced to numbers.

## Response Schema

### `TickerAnalysisResponse`

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | Analysis response schema version. Current value: `analysis.v1`. |
| `ticker` | string | Requested ticker symbol from PostgreSQL warning records. |
| `date` | string | Prediction date for the ticker record, formatted as `YYYY-MM-DD`. |
| `run_id` | string | Warning batch run identifier. |
| `data_as_of` | string | Batch-level market data cutoff date. |
| `generated_at` | string | Batch generation timestamp. |
| `warning` | `WarningAnalysis` | Risk warning probability, thresholds, level, and summary. |
| `trust` | `TrustAssessment` | Calibration, uncertainty, trust status, and summary. |
| `model` | `ModelAnalysis` | Model name and model bundle path used for the prediction. |
| `data_freshness` | `DataFreshness` | Serving freshness metadata from the loaded DB warning batch. |
| `calibration_drift` | `CalibrationDriftMetadata` | Chronological calibration-drift status, signals, deltas, and trust multiplier for the batch. |
| `reasons` | `ReasonExplanation[]` | Typed explanations derived from reason codes. |
| `feature_attributions` | `FeatureAttribution[]` | Top model-specific feature contributions when the model supports them. |
| `limitations` | `string[]` | Fixed limitations shown by clients. |

### `WarningAnalysis`

| Field | Type | Description |
| --- | --- | --- |
| `level` | string | One of `alert`, `watch`, `abstain`, or `no_alert`. |
| `risk_probability` | number | Raw model risk probability in `[0, 1]`. |
| `calibrated_risk_probability` | number | Calibrated risk probability in `[0, 1]`. |
| `alert_threshold` | number | Alert probability threshold used by the warning policy. |
| `watch_threshold` | number | Watch probability threshold used by the warning policy. |
| `summary` | string | Human-readable warning-level summary. |

### `TrustAssessment`

| Field | Type | Description |
| --- | --- | --- |
| `trust_score` | number | Trust score in `[0, 1]`. |
| `uncertainty_score` | number | Uncertainty score in `[0, 1]`. |
| `calibration_method` | string | Calibration method used by the model bundle. |
| `trust_status` | string | Derived trust status, for example `trusted_for_alert` or `limited_trust`. |
| `uncertainty_status` | string | Derived uncertainty status, for example `acceptable_uncertainty` or `high_uncertainty`. |
| `summary` | string | Human-readable trust assessment. |

### `CalibrationDriftMetadata`

The serving command compares the fitted calibration reference window with a
later labeled window when enough history exists. Drift detection does not fit
on the later window. A degraded assessment reduces trust; two or more signals
trigger `abstain`. If no later labeled window is available, the response marks
the gate `not_evaluated` and emits a reason code rather than presenting the
prediction as equally trustworthy.

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `not_evaluated`, `stable`, or `degraded`. |
| `method` | string | Versioned gate implementation name. |
| `event_rate_delta` | number or null | Later labeled positive-rate minus reference positive-rate. |
| `ece_delta` | number or null | Later expected calibration error minus reference ECE. |
| `brier_delta` | number or null | Later Brier score minus reference Brier score. |
| `signals` | `string[]` | Thresholds crossed by the later window. |
| `degraded` | boolean | Whether at least one drift signal crossed threshold. |
| `abstain` | boolean | Whether enough simultaneous signals force abstention. |
| `trust_multiplier` | number | Multiplier applied to trust score when degraded. |
| `calibration_rows` | integer | Rows in the reference calibration window. |
| `recent_rows` | integer | Rows in the later labeled evaluation window. |
| `note` | string | Evaluation or non-evaluation explanation. |

### `ModelAnalysis`

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Model family, for example `temporal_transformer`. |
| `model_bundle` | string | Model bundle path from the prediction record. |

### `DataFreshness`

| Field | Type | Description |
| --- | --- | --- |
| `data_as_of` | string | Batch-level market data cutoff date. |
| `generated_at` | string | Batch generation timestamp. |
| `last_loaded_at` | string | API load timestamp for the DB warning batch. |
| `file_modified_at` | string | Empty for DB-backed serving; retained for schema compatibility. |
| `record_count` | integer | Number of records in the loaded batch. |

### `ReasonExplanation`

| Field | Type | Description |
| --- | --- | --- |
| `code` | string | Original reason code from the prediction record. |
| `severity` | string | One of `info`, `watch`, or `alert`. |
| `title` | string | Short human-readable reason title. |
| `detail` | string | Reason detail suitable for dashboard display. |

### `FeatureAttribution`

| Field | Type | Description |
| --- | --- | --- |
| `feature` | string | Input feature name. |
| `value` | number or null | Input value used for the prediction, when available. |
| `contribution` | number | Standardized log-odds contribution for the supported model. |
| `direction` | string | `positive`, `negative`, or `neutral` relative to drawdown-risk log-odds. |
| `method` | string | Versioned attribution method identifier. |

The current logistic baseline emits `standardized_logit_v1`: the fitted
positive-class coefficient multiplied by the imputed and standardized feature
value. This is a reproducible model diagnostic, not a causal explanation and
not investment advice. Tree and deep model attribution methods remain separate
because their stability and semantics differ.

## Error Schema

Errors use the shared typed envelope from the warning API:

| Field | Type | Description |
| --- | --- | --- |
| `error.code` | string | Stable machine-readable error code. |
| `error.message` | string | Human-readable error message. |

Known analysis endpoint errors:

| HTTP Status | Code | Meaning |
| --- | --- | --- |
| `404` | `ticker_not_found` | The ticker is missing and was not produced by on-demand analysis. |
| `503` | `on_demand_analysis_failed` | The configured on-demand analysis command failed or timed out. |

## Schema Ownership

The schema is implemented by Go structs in:

```text
services/api-gateway-go/internal/http/analysis.go
```

Frontend clients should validate this response with a runtime schema before
rendering. The TypeScript dashboard uses Zod schemas under:

```text
frontend/stock-dashboard/src/lib/schemas.ts
```
