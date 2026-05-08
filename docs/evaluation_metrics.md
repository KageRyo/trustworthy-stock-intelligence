# Evaluation Metrics

## Why Accuracy Is Not Enough

Stock risk early-warning is class-imbalanced, noisy, and asymmetric. A model can have high accuracy by predicting no risk most of the time while still missing important risk events.

The first milestone therefore evaluates both classification quality and warning reliability.

## Classification Metrics

Core classification metrics:

```text
Precision
Recall
F1
AUC
```

Interpretation:

```text
Precision: among issued risk predictions, how many were real risk events?
Recall: among real risk events, how many were detected?
F1: balance between precision and recall
AUC: ranking quality across risk thresholds
```

## Warning Metrics

Risk warning requires additional metrics:

```text
False Alarm Rate
Miss Rate
Lead Time
```

Suggested definitions:

```text
False Alarm Rate = false alerts / all alerts
Miss Rate = missed risk events / all risk events
Lead Time = number of trading days between the first warning and the realized risk event
```

False alarm and miss rate should be reported together. A model that never alerts has low false alarms but unacceptable misses.

## Calibration Metrics

Trustworthy warnings require reliable probabilities.

Core calibration metrics:

```text
Brier Score
Expected Calibration Error
Reliability Diagram
Calibration Curve
```

Interpretation:

```text
Brier Score: mean squared error of predicted probability
ECE: gap between predicted confidence and empirical event frequency
Reliability Diagram: visual check of probability calibration
```

## Selective Prediction Metrics

If the model can abstain, evaluation must include coverage and selective risk.

```text
Coverage = fraction of samples where the model issues a decision
Selective Risk = error rate on non-abstained samples
High-Confidence Precision = precision among warnings above a trust threshold
```

The expected tradeoff:

```text
lower coverage
lower false alert rate
lower selective risk
```

This tradeoff should be measured explicitly rather than hidden.

## Alert Levels

Milestone 1 can use four warning states:

```text
Alert
Watch
Abstain
No Alert
```

Binary classification metrics should be computed on risk predictions. Selective metrics should be computed after applying the alert/watch/abstain decision rule.

## Reporting Requirements

Each experiment should report:

- metrics by fold
- mean and standard deviation across folds
- class balance per fold
- number of alerts
- number of missed events
- calibration before and after calibration
- threshold settings
- coverage under selective prediction
