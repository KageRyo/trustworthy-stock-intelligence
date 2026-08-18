# Recall-Oriented Trust Policy Candidates

These candidates are selected from an existing threshold sweep. They are policy diagnostics, not new
model-training results.

| trust_score_method | watch_threshold_ratio | trust_threshold | uncertainty_threshold | uncertainty_penalty | alert_rate | watch_rate | coverage | alert_precision | alert_recall | alert_false_alarm_rate | selective_risk |
| ------------------ | --------------------- | --------------- | --------------------- | ------------------- | ---------- | ---------- | -------- | --------------- | ------------ | ---------------------- | -------------- |
| multiplicative     | 0.9000                | 0.1000          | 0.5000                | 0.5000              | 0.1848     | 0.2374     | 0.4222   | 0.1475          | 0.2645       | 0.1756                 | 0.4375         |
| multiplicative     | 0.9000                | 0.1000          | 0.6000                | 0.5000              | 0.1848     | 0.2374     | 0.4222   | 0.1475          | 0.2645       | 0.1756                 | 0.4375         |
| multiplicative     | 0.9000                | 0.1000          | 0.7000                | 0.5000              | 0.1848     | 0.2374     | 0.4222   | 0.1475          | 0.2645       | 0.1756                 | 0.4375         |
| multiplicative     | 0.9000                | 0.1000          | 0.8000                | 0.5000              | 0.1848     | 0.2374     | 0.4222   | 0.1475          | 0.2645       | 0.1756                 | 0.4375         |
| multiplicative     | 0.9000                | 0.1000          | 0.9000                | 0.5000              | 0.1848     | 0.2374     | 0.4222   | 0.1475          | 0.2645       | 0.1756                 | 0.4375         |
| multiplicative     | 0.8000                | 0.1000          | 0.5000                | 0.5000              | 0.1848     | 0.3106     | 0.4954   | 0.1475          | 0.2645       | 0.1756                 | 0.3856         |
| multiplicative     | 0.8000                | 0.1000          | 0.6000                | 0.5000              | 0.1848     | 0.3106     | 0.4954   | 0.1475          | 0.2645       | 0.1756                 | 0.3856         |
| multiplicative     | 0.8000                | 0.1000          | 0.7000                | 0.5000              | 0.1848     | 0.3106     | 0.4954   | 0.1475          | 0.2645       | 0.1756                 | 0.3856         |
| multiplicative     | 0.8000                | 0.1000          | 0.8000                | 0.5000              | 0.1848     | 0.3106     | 0.4954   | 0.1475          | 0.2645       | 0.1756                 | 0.3856         |
| multiplicative     | 0.8000                | 0.1000          | 0.9000                | 0.5000              | 0.1848     | 0.3106     | 0.4954   | 0.1475          | 0.2645       | 0.1756                 | 0.3856         |

## Notes

- Use recall-oriented policies to study the cost of catching more risk events.
- Compare alert recall against false alarm rate before presenting a policy as useful.
- Keep the v1 framing conservative: this is risk alerting, not trading advice.
