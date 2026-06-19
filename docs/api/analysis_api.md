# Ticker Analysis API Contract

The ticker analysis API is a schema-first read model built on top of the
Python-generated warning batch. It does not run synchronous inference. It
converts one `PredictionRecord` from `latest_warnings.json` into a typed,
dashboard-oriented analysis response.

## Endpoint

```text
GET /api/v1/analysis/{ticker}
```

Ticker lookup is case-insensitive. Missing tickers return the standard API error
envelope with `ticker_not_found`.

## Response Schema

### `TickerAnalysisResponse`

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | Analysis response schema version. Current value: `analysis.v1`. |
| `ticker` | string | Requested ticker symbol from the loaded warning batch. |
| `date` | string | Prediction date for the ticker record, formatted as `YYYY-MM-DD`. |
| `run_id` | string | Warning batch run identifier. |
| `data_as_of` | string | Batch-level market data cutoff date. |
| `generated_at` | string | Batch generation timestamp. |
| `warning` | `WarningAnalysis` | Risk warning probability, thresholds, level, and summary. |
| `trust` | `TrustAssessment` | Calibration, uncertainty, trust status, and summary. |
| `model` | `ModelAnalysis` | Model name and model bundle path used for the prediction. |
| `data_freshness` | `DataFreshness` | Serving freshness metadata from the loaded warning file. |
| `reasons` | `ReasonExplanation[]` | Typed explanations derived from reason codes. |
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
| `last_loaded_at` | string | API load timestamp for the warning file. |
| `file_modified_at` | string | Filesystem modification timestamp for the warning file. |
| `record_count` | integer | Number of records in the loaded batch. |

### `ReasonExplanation`

| Field | Type | Description |
| --- | --- | --- |
| `code` | string | Original reason code from the prediction record. |
| `severity` | string | One of `info`, `watch`, or `alert`. |
| `title` | string | Short human-readable reason title. |
| `detail` | string | Reason detail suitable for dashboard display. |

## Error Schema

Errors use the shared typed envelope from the warning API:

| Field | Type | Description |
| --- | --- | --- |
| `error.code` | string | Stable machine-readable error code. |
| `error.message` | string | Human-readable error message. |

Known analysis endpoint errors:

| HTTP Status | Code | Meaning |
| --- | --- | --- |
| `404` | `ticker_not_found` | The ticker is missing from the latest loaded warning batch. |

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
