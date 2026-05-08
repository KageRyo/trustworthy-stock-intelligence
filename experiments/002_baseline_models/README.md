# Experiment 002: Baseline Models

## Dataset

```text
S&P 100 pilot
Daily OHLCV
Technical indicators
Market index features
```

## Task

```text
5-day drawdown risk warning
```

## Models

```text
Logistic Regression
Random Forest
XGBoost
```

## Evaluation

```text
walk-forward split
no random split
Precision
Recall
F1
AUC
False Alarm Rate
Miss Rate
Brier Score
ECE
Lead Time
```

## Preliminary Findings

Not yet available. This report will compare baseline models before and after probability calibration.

## Next Steps

- implement baseline training entry point
- implement alert-oriented metrics
- add calibration comparison
- write fold-level result tables
