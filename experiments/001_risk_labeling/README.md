# Experiment 001: Risk Labeling

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

## Label

```text
Risk = 1 if future 5-day max drawdown <= -5%
Risk = 0 otherwise
```

## Leakage Rule

Features may only use information up to day `t`. Labels may only use information from day `t+1` through day `t+H`.

## Split

The main protocol uses walk-forward validation. Random train-test splits are not allowed.

## Preliminary Findings

Not yet available. This directory will record class balance, label stability, and edge cases after the labeling implementation is added.

## Next Steps

- implement drawdown label generation
- test label alignment
- inspect class imbalance
- validate end-of-series handling
