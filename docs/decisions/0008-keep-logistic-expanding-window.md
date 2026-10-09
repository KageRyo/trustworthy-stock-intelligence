# 0008: Keep the Logistic Model and the Expanding Training Window

- Status: Accepted
- Date: 2026-10-09
- Evidence: [Experiment 019](../../experiments/019_nonlinear_models/README.md)

## Context

The served model is a logistic regression on 12 `technical_range` features. Experiment 013 preferred it over tree models and a Transformer, but with older features, default tree settings, and a 252-date training window. Serving does not use that window: it trains on every labeled date before the calibration window.

## Decision

- Serving keeps the logistic regression.
- Serving keeps training on every earlier labeled date. `--train-size` stays unset by default.
- The research scripts keep their 252-date schedule so earlier experiments stay comparable, and reports state that it understates the served model.

## Consequences

- Quadratic logistic regression, regularized gradient boosting, and a GPU-trained MLP did not raise uncalibrated AUC by 0.005 with an interval above zero on both US samples. At the served window, gradient boosting moved AUC by at most 0.0023, quadratic logistic regression was worse on the S&P 500 holdout, and the MLP lost alert precision there.
- The expanding window ranks better than 252 dates by 0.018 (S&P 100), 0.012 (S&P 500 holdout), and 0.012 (Taiwan), all with intervals above zero.
- The model card's walk-forward numbers come from the 252-date schedule, so they are conservative for ranking.

## Revisit when

- A nonlinear model gains on both US samples and the Taiwan holdout. The Taiwan MLP gain of +0.0048 is a candidate to recheck.
- A new label (for example a market-relative drawdown) or a new information source changes what the features can express.
