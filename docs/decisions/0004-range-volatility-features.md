# 0004: Serve Range-Volatility Features; Reject Market-Regime Features

- Status: Accepted
- Date: 2026-10-07 (v0.7.0, pull request #134)
- Evidence: [Experiment 017](../../experiments/017_feature_sets/README.md)

## Context

The v0.6.0 baseline used 7 close-to-close technical features. Candidate additions were range-based volatility from each ticker's own OHLC bars, returns relative to the market and sector ETFs, beta, and market-regime series (SPY return and drawdown, VIX).

## Decision

- Serving defaults to `--feature-set technical_range`: the 7 technical features plus Parkinson and Garman-Klass volatility, ATR(14), 20-day volatility, and drawdown from the 20-day high.
- The batch `model_bundle` records the feature set.
- Market-regime features are not served.
- Beta stays experimental because serving has no reference-data path.

## Consequences

- AUC rose by 0.023 to 0.029 on S&P 100, on a 402-ticker S&P 500 holdout, and on 53 Taiwan large caps. Serving needs no new provider dependency.
- Regime features lowered AUC by about 0.02, and their coefficients flipped sign across folds.

## Revisit when

- Serving gains a validated SPY and TAIEX reference path with staleness checks, which would make the beta gain (0.005 to 0.010 AUC in the US) available.
- A nonlinear model can use regime features without linear extrapolation.
