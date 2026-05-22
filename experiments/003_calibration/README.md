# Experiment 003: Calibration

## Purpose

This experiment track evaluates whether calibrated probabilities improve the reliability of stock risk warnings.

## Methods

Candidate methods:

```text
raw probability
Platt scaling
isotonic calibration
```

## Metrics

```text
Brier Score
Expected Calibration Error
Reliability Diagram
Calibration Curve
High-Confidence Precision
```

## Notes

Calibration must be fit on a calibration window that occurs after training and
before testing.

The current codebase supports:

```text
none
Platt scaling
isotonic regression
```

All calibration methods are fit only on the calibration window inside each
walk-forward fold.

## Pilot Run

S&P 100 pilot calibration results from the walk-forward logistic baseline:

| Variant | AUC | Brier | ECE | Prediction Rate at 0.5 |
| --- | ---: | ---: | ---: | ---: |
| Raw logistic | 0.6137 | 0.2321 | 0.3729 | 0.3214 |
| Platt scaling | 0.6064 | 0.0928 | 0.0540 | 0.0010 |
| Isotonic regression | 0.6041 | 0.0925 | 0.0528 | 0.0013 |

Key observation:

- Calibration improved reliability metrics dramatically.
- Discrimination changed only slightly.
- Using the same `0.5` threshold before and after calibration is not valid for
  warning decisions, because the calibrated probability scale becomes much more
  conservative.

Immediate follow-up:

- evaluate calibrated thresholds on validation data only
- define alert/watch/abstain rules instead of a single fixed threshold
