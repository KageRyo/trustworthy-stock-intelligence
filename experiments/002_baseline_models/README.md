# Experiment 002: Baseline Models

## Historical Status

This document records the original preliminary pilot. Its fold boundaries did
not purge the five-day label horizon and it is no longer the primary
calibration claim. Use `experiments/007_research_evidence/README.md` for the
current purged result. The historical numbers remain here for provenance.

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

## Pilot Run

Local artifact run completed on the S&P 100 pilot dataset downloaded on
2026-05-08. Configuration:

```text
Input rows: 283,289 raw OHLCV rows
Rows after feature/label filtering: 281,774
Universe size: 101 tickers
Train window: 252 trading days
Calibration window: 63 trading days
Test window: 63 trading days
Fold count: 40
Test coverage: 2016-04-19 through 2026-04-27
```

## Preliminary Findings

Mean fold-level results for the logistic baseline:

| Variant | Precision | Recall | F1 | AUC | False Alarm Rate | Miss Rate | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw logistic | 0.1436 | 0.4494 | 0.2100 | 0.6137 | 0.3077 | 0.5506 | 0.2321 | 0.3729 |
| Logistic + Platt at 0.5 | 0.0589 | 0.0023 | 0.0044 | 0.6064 | 0.0008 | 0.9977 | 0.0928 | 0.0540 |
| Logistic + Platt tuned on calibration | 0.1429 | 0.4594 | 0.2030 | 0.6064 | 0.3433 | 0.5406 | 0.0928 | 0.0540 |
| Logistic + Isotonic at 0.5 | 0.1545 | 0.0036 | 0.0069 | 0.6041 | 0.0010 | 0.9964 | 0.0925 | 0.0528 |
| Logistic + Isotonic tuned on calibration | 0.1435 | 0.4610 | 0.2055 | 0.6041 | 0.3399 | 0.5390 | 0.0925 | 0.0528 |

Additional class-rate context:

```text
Average test positive rate: 0.1029
Raw logistic prediction rate at threshold 0.5: 0.3214
Platt prediction rate at threshold 0.5: 0.0010
Isotonic prediction rate at threshold 0.5: 0.0013
Platt tuned prediction rate: 0.3554
Isotonic tuned prediction rate: 0.3524
Mean tuned Platt threshold: 0.1034
Mean tuned Isotonic threshold: 0.1231
```

Interpretation:

- The raw logistic model is moderately discriminative but badly overconfident.
- Probability calibration sharply improves Brier Score and ECE.
- A fixed alert threshold of 0.5 becomes too conservative after calibration.
- Re-tuning the alert threshold on the calibration window restores useful recall and F1.
- Calibration quality and warning decision quality must be evaluated separately.

## Current Pipeline

The baseline pipeline now supports:

```text
technical feature generation
future 5-day drawdown labeling
walk-forward train/calibration/test splits
logistic regression baseline
sklearn tree baselines
Platt scaling
isotonic calibration
fold-level alert-oriented metrics
```

The first comparison to run on real pilot data is:

```text
logistic regression raw probabilities
logistic regression + Platt scaling
logistic regression + isotonic calibration
```

Tree-based baselines use sklearn built-ins first, avoiding optional XGBoost or
LightGBM dependencies in the core workflow:

```bash
python -m scripts.train \
  --input data/raw/sp100/ohlcv.csv \
  --model-type random_forest \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --calibration-method platt \
  --output data/artifacts/sp100_random_forest_summary.json \
  --predictions-output data/artifacts/sp100_random_forest_predictions.csv
```

## Next Steps

- add threshold sweeps or warning-rule tuning on validation data only
- compare calibrated high-confidence precision under selective alerting
- add tree-based baselines against the logistic reference
- write fold-level result tables and failure-case notes
