# Experiment Comparison Report

This report compares risk-warning experiment runs as a trust-aware conservative alerting demo. It should not be read as an investment recommendation, a precise price forecast, or an automated trading result.

## Runs

| run | trust_score_method | alert_rate | watch_rate | no_alert_rate | alert_precision | alert_recall | alert_false_alarm_rate | coverage | selective_risk | calibrated_ece | calibrated_brier_score | calibrated_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| platt_entropy_wr08 | subtractive | 0.0000 | 0.4954 | 0.5046 | 0.0000 | 0.0000 | 0.0000 | 0.4954 | 0.1227 | 0.0579 | 0.0945 | 0.6022 |
| platt_entropy_multiplicative_wr08 | multiplicative | 0.0249 | 0.4705 | 0.5046 | 0.1558 | 0.0377 | 0.0235 | 0.4954 | 0.1574 | 0.0579 | 0.0945 | 0.6022 |

## Interpretation

- Prefer language such as `trust-aware conservative risk alerting demo` when describing these runs.
- Compare alert precision, false alarm rate, and coverage together; a low alert rate can be useful for triage but usually implies low recall.
- Use calibrated ECE and Brier score to discuss reliability, not directional trading performance.
- In these runs, at least one policy emitted no alerts while another emitted a non-zero alert rate; this supports the subtractive-versus-multiplicative trust-score comparison story.

