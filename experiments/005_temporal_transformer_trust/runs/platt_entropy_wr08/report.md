# Temporal Transformer Trust Experiment Report

## Overview

This report summarizes a Temporal Transformer risk model with calibration, uncertainty scoring,
trust scoring, and warning-level decisions.

## Model Config

```json
{
  "d_model": 64,
  "num_heads": 4,
  "num_layers": 2,
  "dim_feedforward": 128,
  "dropout": 0.1
}
```

## Training Config

```json
{
  "epochs": 30,
  "batch_size": 512,
  "learning_rate": 0.0001,
  "weight_decay": 0.0001,
  "num_workers": 0,
  "device": "cuda",
  "max_gpu_count": 2,
  "used_data_parallel": true
}
```

## Trust Config

```json
{
  "calibration_method": "platt",
  "threshold_objective": "f1",
  "uncertainty_method": "entropy",
  "uncertainty_penalty": 0.5,
  "trust_threshold": 0.5,
  "uncertainty_threshold": 0.8,
  "watch_threshold_ratio": 0.8,
  "min_watch_threshold": 0.05
}
```

## Raw / Calibrated / Tuned Metrics

| Metric        |    Raw | Calibrated |  Tuned |
| ------------- | -----: | ---------: | -----: |
| `auc`         | 0.6073 |     0.6022 | 0.6022 |
| `f1`          | 0.2053 |     0.0000 | 0.1951 |
| `brier_score` | 0.2126 |     0.0945 | 0.0945 |
| `ece`         | 0.2797 |     0.0579 | 0.0579 |
| `precision`   | 0.1421 |     0.0000 | 0.1533 |
| `recall`      | 0.4624 |     0.0000 | 0.4450 |

## Warning-Level Distribution

| Metric           |       Value |
| ---------------- | ----------: |
| `alert_count`    |      0.0000 |
| `watch_count`    | 124067.0000 |
| `abstain_count`  |      0.0000 |
| `no_alert_count` | 126357.0000 |
| `alert_rate`     |      0.0000 |
| `watch_rate`     |      0.4954 |
| `abstain_rate`   |      0.0000 |
| `no_alert_rate`  |      0.5046 |

## Warning Quality

| Metric                          |  Value |
| ------------------------------- | -----: |
| `alert_precision`               | 0.0000 |
| `alert_recall`                  | 0.0000 |
| `alert_false_alarm_rate`        | 0.0000 |
| `alert_miss_rate`               | 1.0000 |
| `coverage`                      | 0.4954 |
| `selective_risk`                | 0.1227 |
| `alert_only_selective_risk`     | 0.1227 |
| `alert_or_watch_selective_risk` | 0.8773 |

## Threshold Sweep Candidates

| Policy       | trust_score_method | watch_threshold_ratio | trust_threshold | uncertainty_threshold | uncertainty_penalty | coverage | selective_risk | alert_or_watch_selective_risk | alert_precision | alert_false_alarm_rate | watch_rate | no_alert_rate |
| ------------ | -----------------: | --------------------: | --------------: | --------------------: | ------------------: | -------: | -------------: | ----------------------------: | --------------: | ---------------------: | ---------: | ------------: |
| balanced     |     multiplicative |                0.8000 |          0.2000 |                0.5000 |              0.5000 |   0.4954 |         0.1574 |                        0.8773 |          0.1558 |                 0.0235 |     0.4705 |        0.4865 |
| conservative |     multiplicative |                0.6000 |          0.2000 |                0.5000 |              0.5000 |   0.6287 |         0.1403 |                        0.8870 |          0.1558 |                 0.0235 |     0.6038 |        0.3682 |
| broad        |     multiplicative |                0.6000 |          0.1000 |                0.5000 |              0.5000 |   0.6287 |         0.3202 |                        0.8870 |          0.1475 |                 0.1756 |     0.4439 |        0.3682 |

## Observations

- Interpret `alert` as the strongest warning and `watch` as lower-intensity monitoring.

- The current subtractive trust score is overly conservative under entropy uncertainty when trust
  thresholds are high; compare multiplicative trust scoring before dashboard presentation.

- Use threshold sweep candidates to choose a policy before dashboard presentation.

- Compare calibrated metrics against raw metrics before making warning policy claims.

## Limitations

- This is a risk-event warning experiment, not investment advice or an automated trading system.

- Threshold policies should be validated across more folds and market regimes.

- Watch decisions are weaker than alerts and should not be interpreted as positive predictions
  without context.
