# Experiment Protocol

## Goal

The experiment protocol defines how to evaluate stock risk early-warning models without leakage and without relying on random splits that violate temporal order.

The first milestone is:

```text
TSI-Risk-v0
```

## Dataset

Primary v0 dataset:

```text
Universe: S&P 100
Frequency: Daily
Data: OHLCV + technical indicators + market index features
Label: future 5-day max drawdown <= -5%
```

Pilot data source:

```text
Yahoo Finance
```

Formal research data sources preferred:

```text
WRDS/CRSP
Polygon
Tiingo
official exchange data
```

## Pipeline

The expected research pipeline is:

```text
download
preprocess
feature generation
risk labeling
walk-forward split
train baseline model
calibrate probabilities
estimate uncertainty
generate warning level
evaluate
write experiment report
```

## Splitting Protocol

The main protocol must use walk-forward validation. Random train-test splits are not allowed because they can leak future market regimes into training.

Each walk-forward fold should define:

```text
training window
purge gap of at least the label horizon
calibration or validation window
purge gap of at least the label horizon
test window
```

The calibration window must occur after the training window and before the test window.
For the five-day future drawdown label, exclude at least five trading dates at
both boundaries. This prevents a label in the earlier window from reading
prices that belong to the next model-selection or evaluation window. Also
record each row's actual label end date and remove any row whose outcome window
reaches the next split; this second check handles mixed-market calendars.

## Model Families

Milestone 1 uses simple baselines:

```text
Logistic Regression
Random Forest
XGBoost
```

Deep sequence models, image models, LLMs, and multimodal fusion are deferred until the baseline and trust layer are stable.

## Trust Layer

The trust layer should evaluate whether the model's risk probability is reliable enough to issue a warning.

First version:

```text
raw probability
calibrated probability
uncertainty score
warning level
```

Candidate warning decision:

```text
Alert: high calibrated risk and low uncertainty
Watch: moderate risk or moderate uncertainty
Abstain: unreliable confidence or high uncertainty
No Alert: low calibrated risk
```

## Experiment Comparisons

The first experiment report should compare:

```text
baseline model
baseline model + calibration
baseline model + calibration + selective warning
baseline model + calibration + uncertainty-aware warning
```

The goal is not only to improve predictive metrics. The key question is whether warnings become more reliable under calibration and selective decision rules.

## Reporting Template

Each experiment report should include:

```text
Dataset
Date range
Universe
Feature set
Label definition
Split protocol
Models
Calibration method
Warning decision rule
Metrics
Main findings
Limitations
Reproducibility notes
```

## Prohibited Shortcuts

The main protocol must not use:

- random train-test split
- future returns as features
- future volatility as features
- normalization fit on the full dataset
- calibration fit on test data
- threshold tuning on the test window
- label horizons that overlap the following calibration or test window
- survivorship assumptions without documentation
