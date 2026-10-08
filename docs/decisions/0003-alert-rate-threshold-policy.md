# 0003: Alert Thresholds Use Calibration-Window Alert-Rate Policies

- Status: Accepted
- Date: 2026-10-07 (v0.6.0, pull request #132)
- Evidence: [Experiment 016](../../experiments/016_alert_policy/README.md); rechecked with range
  features in [Experiment 017](../../experiments/017_feature_sets/README.md)

## Context

Choosing the alert threshold by maximizing F1 put about 32% of rows on alert, with a false-discovery
rate near 0.84. Precision targets chosen on the calibration window did not transfer to later test
windows.

## Decision

- `--alert-policy alert_rate:0.05` alerts on the top 5% of calibration-window risk.
- `--watch-policy alert_rate:0.2` puts the top 20% on watch or alert.
- Every batch records `alert_policy` metadata. Calibration windows with fewer than 20 alert rows are
  flagged as noisy, and the dashboard shows this.
- `--alert-policy objective --watch-policy ratio` restores the F1 thresholds.

## Consequences

With the v0.7.0 features on S&P 100, alert precision is 0.279 and recall is 0.220. Alerts cover 1.70
days per ticker-month, against 6.13 under F1 thresholds with the same features. Recall is traded for
fewer, more precise alerts, and the watch tier carries more of the recall.

## Revisit when

A model or feature change moves the precision-recall frontier enough that another cap wins in most
folds, or cross-sectional top-K serving becomes possible.
