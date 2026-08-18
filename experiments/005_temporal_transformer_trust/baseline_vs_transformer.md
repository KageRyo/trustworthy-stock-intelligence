# Baseline vs Transformer Comparison

This report compares model and decision variants. Interpret calibration metrics separately from
warning-decision metrics: a calibrated model can still need a conservative or recall-oriented
warning policy.

| run                               | model                | variant        | auc    | brier_score | ece    | precision | recall | f1     | alert_precision | false_alarm_rate | coverage |
| --------------------------------- | -------------------- | -------------- | ------ | ----------- | ------ | --------- | ------ | ------ | --------------- | ---------------- | -------- |
| sp100_logistic_platt              | logistic_regression  | raw            | 0.6137 | 0.2321      | 0.3729 | 0.1436    | 0.4494 | 0.2100 |                 | 0.3077           |          |
| sp100_logistic_platt              | logistic_regression  | calibrated     | 0.6064 | 0.0928      | 0.0540 | 0.0589    | 0.0023 | 0.0044 |                 | 0.0008           |          |
| sp100_logistic_platt              | logistic_regression  | tuned          | 0.6064 | 0.0928      | 0.0540 | 0.1435    | 0.4616 | 0.2054 |                 | 0.3416           |          |
| platt_entropy_multiplicative_wr08 | temporal_transformer | raw            | 0.6073 | 0.2126      | 0.2797 | 0.1421    | 0.4624 | 0.2053 |                 | 0.3179           |          |
| platt_entropy_multiplicative_wr08 | temporal_transformer | calibrated     | 0.6022 | 0.0945      | 0.0579 | 0.0000    | 0.0000 | 0.0000 |                 | 0.0000           |          |
| platt_entropy_multiplicative_wr08 | temporal_transformer | tuned          | 0.6022 | 0.0945      | 0.0579 | 0.1533    | 0.4450 | 0.1951 |                 | 0.3229           |          |
| platt_entropy_multiplicative_wr08 | temporal_transformer | trust_decision | 0.6022 | 0.0945      | 0.0579 | 0.1533    | 0.4450 | 0.1951 | 0.1558          | 0.0235           | 0.4954   |

## Reading Notes

- `raw`, `calibrated`, and `tuned` rows are probability-threshold model variants.
- `trust_decision` rows use the warning-level evaluation artifact when present.
- A useful v1 claim is improved reliability or more conservative alerting, not guaranteed drawdown
  prediction.
